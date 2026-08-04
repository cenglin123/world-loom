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

检查分两个层面：

**源码**（静态扫 scripts/*.py，防新脚本引入）：
    1. subprocess.run/Popen/check_output 带 text=True 但无 encoding=
    2. open() / read_text() / write_text() 文本模式但无 encoding=（二进制模式豁免）
    3. write_text() / open() 写模式无 newline=（二进制模式豁免）

**仓库状态**（git ls-files --eol，防已有 CRLF 滞留）：
    4. 已跟踪文本文件在工作区里是 CRLF/混合换行

第 4 类不可省：编辑器、PowerShell、别处 clone 同样把 CRLF 带进工作区，
静态扫源码一个都看不见。查源码是防新增，查状态是防存量——两者不互相覆盖。

CLI：
    python scripts/check_encoding.py          # 扫 scripts/ 全部 .py + 仓库换行状态
    python scripts/check_encoding.py <文件…>  # 只静态扫指定文件
"""
from __future__ import annotations

import re
import subprocess
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


def scan_worktree_eol() -> list[str]:
    """已跟踪文本文件在工作区的实际换行——CRLF/混合都算问题。

    .gitattributes 的 eol=lf 只保证入库内容是 LF，管不住工作区：写进来的
    CRLF 会让 git status 把内容没变的文件报成已修改（git diff 却是空的），
    随后 `git add -A` 顺手把它扫进提交。二进制由 git 自行判定，不会命中。
    取不到 git 输出时静默放行（fail-open）。
    """
    try:
        proc = subprocess.run(
            ["git", "-c", "core.quotepath=false", "ls-files", "--eol"],
            cwd=ROOT, capture_output=True, timeout=30,
            text=True, encoding="utf-8", errors="replace",
        )
    except (subprocess.TimeoutExpired, OSError):
        return []
    if proc.returncode != 0:
        return []

    bad: list[str] = []
    for line in proc.stdout.splitlines():
        attrs, _, path = line.partition("\t")
        if not path:
            continue
        if "w/crlf" in attrs or "w/mixed" in attrs:
            bad.append(path.strip())
    if not bad:
        return []

    listed = "\n".join(f"      {p}" for p in bad)
    return [
        f"工作区有 {len(bad)} 个文本文件是 CRLF（入库会被 eol=lf 归一，"
        f"但 git status 会把它们报成已修改而 git diff 为空）：\n"
        f"{listed}\n"
        f"    修复：python scripts/check_encoding.py --fix-eol"
    ]


def fix_worktree_eol() -> int:
    """把工作区里 CRLF 的已跟踪文本文件就地转成 LF。"""
    issues = scan_worktree_eol()
    if not issues:
        print("[PASS] 工作区无 CRLF 文件，无需处理")
        return 0
    paths = [ln.strip() for ln in issues[0].splitlines()
             if ln.startswith("      ")]
    fixed = 0
    for rel in paths:
        p = ROOT / rel
        try:
            data = p.read_bytes()
        except OSError as exc:
            print(f"[SKIP] {rel}：读取失败 {exc}")
            continue
        if b"\r\n" not in data:
            continue
        try:
            p.write_bytes(data.replace(b"\r\n", b"\n"))
        except OSError as exc:
            print(f"[SKIP] {rel}：写入失败 {exc}")
            continue
        print(f"[FIX ] {rel}")
        fixed += 1
    print(f"[OK] 已归一 {fixed} 个文件为 LF")
    return 0


def main(argv: list[str]) -> int:
    if argv and argv[0] == "--fix-eol":
        return fix_worktree_eol()

    targets = [Path(a).resolve() for a in argv] if argv else sorted(SCRIPT_DIR.glob("*.py"))
    targets = [t for t in targets if t.is_file() and t.name != Path(__file__).name]

    all_issues: list[str] = []
    for t in targets:
        all_issues.extend(scan(t))
    # 指定文件时只做静态扫描；全量模式才查仓库状态
    if not argv:
        all_issues.extend(scan_worktree_eol())

    if all_issues:
        print(f"[FAIL] {len(all_issues)} 处文本 IO 问题（编码未显式 → 中文 Windows 解码崩溃；CRLF → 与 eol=lf 相冲）：")
        for i in all_issues:
            print(f"  {i}")
        return 1

    scope = "，工作区换行均为 LF" if not argv else ""
    print(f"[PASS] {len(targets)} 个脚本的编码与换行均已显式指定{scope}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main(sys.argv[1:]))
