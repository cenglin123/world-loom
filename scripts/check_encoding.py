#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""编码显式性检查——防中文 Windows 上的解码崩溃。

背景：Python 的 `subprocess.run(text=True)` 和 `open()` 在不指定 encoding 时，
按**系统区域**解码。中文 Windows 的区域是 GBK，而 git 输出的路径、仓库里的
文档全是 UTF-8——一旦内容含中文，解码就炸：

    subprocess 读取线程 UnicodeDecodeError → stdout 变 None → 调用方 AttributeError

这类崩溃只在中文路径出现时才触发，本机不测中文就发现不了，且每写一个新的
subprocess 调用都可能重新引入。所以用脚本兜，不靠记性。

同理，文本写入不指定 newline 时，Windows 会把 "\n" 翻成 "\r\n"，而本仓
.gitattributes 规定 eol=lf——于是每次脚本改文件都让工作区与索引抖一轮
CRLF/LF。写入一律 newline="\n"（读取不用管，通用换行本就该照单全收）。

检查三类：
    1. subprocess.run/Popen/check_output 带 text=True 但无 encoding=
    2. open() / read_text() / write_text() 文本模式但无 encoding=（二进制模式豁免）
    3. write_text() / open() 写模式无 newline=（二进制模式豁免）

CLI：
    python scripts/check_encoding.py          # 扫 scripts/ 全部 .py
    python scripts/check_encoding.py <文件…>  # 只扫指定文件
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT_DIR = ROOT / "scripts"

PAT_SUBPROCESS = re.compile(r"subprocess\.(run|Popen|check_output)\s*\(")
PAT_OPEN = re.compile(r"(?<![\w.])open\s*\(")
PAT_READ_WRITE = re.compile(r"\.(read_text|write_text)\s*\(")
PAT_WRITE_TEXT = re.compile(r"\.write_text\s*\(")
BINARY_MODES = ('"rb"', "'rb'", '"wb"', "'wb'", '"ab"', "'ab'", '"r+b"', "'r+b'")
# open() 的写模式——只有写才需要 newline=
WRITE_MODES = ('"w"', "'w'", '"a"', "'a'", '"x"', "'x'", '"w+"', "'w+'",
               '"a+"', "'a+'", '"r+"', "'r+'", '"x+"', "'x+'")


def _call_block(src: str, open_paren_idx: int) -> str:
    """从左括号位置取到配对的右括号，返回整个调用文本。"""
    depth, i = 0, open_paren_idx
    while i < len(src):
        if src[i] == "(":
            depth += 1
        elif src[i] == ")":
            depth -= 1
            if depth == 0:
                return src[open_paren_idx:i + 1]
        i += 1
    return src[open_paren_idx:]


def scan(path: Path) -> list[str]:
    try:
        src = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return [f"{path.name}: 读取失败 {exc}"]

    issues: list[str] = []
    rel = path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else str(path)

    for m in PAT_SUBPROCESS.finditer(src):
        blk = _call_block(src, m.end() - 1)
        if ("text=True" in blk or "universal_newlines=True" in blk) \
                and "encoding=" not in blk:
            line = src[:m.start()].count("\n") + 1
            issues.append(
                f"{rel}:{line}  subprocess 带 text=True 但无 encoding\n"
                f"    修复：补 encoding=\"utf-8\", errors=\"replace\""
            )

    for m in list(PAT_OPEN.finditer(src)) + list(PAT_READ_WRITE.finditer(src)):
        blk = _call_block(src, m.end() - 1)
        if any(b in blk for b in BINARY_MODES):
            continue
        if "encoding=" not in blk:
            line = src[:m.start()].count("\n") + 1
            issues.append(
                f"{rel}:{line}  文本读写未指定 encoding\n"
                f"    修复：补 encoding=\"utf-8\"（二进制请显式用 rb/wb）"
            )

    writes = list(PAT_WRITE_TEXT.finditer(src))
    writes += [m for m in PAT_OPEN.finditer(src)
               if any(w in _call_block(src, m.end() - 1) for w in WRITE_MODES)]
    for m in sorted(writes, key=lambda x: x.start()):
        blk = _call_block(src, m.end() - 1)
        if any(b in blk for b in BINARY_MODES):
            continue
        if "newline=" not in blk:
            line = src[:m.start()].count("\n") + 1
            issues.append(
                f"{rel}:{line}  文本写入未指定 newline\n"
                f"    修复：补 newline=\"\\n\"（Windows 默认会写成 CRLF，与 eol=lf 相冲）"
            )

    return issues


def main(argv: list[str]) -> int:
    targets = [Path(a).resolve() for a in argv] if argv else sorted(SCRIPT_DIR.glob("*.py"))
    targets = [t for t in targets if t.is_file() and t.name != Path(__file__).name]

    all_issues: list[str] = []
    for t in targets:
        all_issues.extend(scan(t))

    if all_issues:
        print(f"[FAIL] {len(all_issues)} 处文本 IO 未显式指定（中文 Windows 上解码崩溃 / 写出 CRLF）：")
        for i in all_issues:
            print(f"  {i}")
        return 1

    print(f"[PASS] {len(targets)} 个脚本的编码与换行均已显式指定")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main(sys.argv[1:]))
