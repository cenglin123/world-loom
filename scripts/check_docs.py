#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""文档体系检查——防死文档与占位符滞留。

两类失效，都是"没人会主动发现"的那种：

1. **孤儿文档**：写了但没有任何文件引用它。它不会报错、不会被看见，
   只是慢慢过期，然后误导下一个读到它的人。
2. **占位符滞留**：正文都写了几章，`简介.md` / `核心设定.md` 还停在"待填写"。
   说明创作跑在了设定前面——不一定错，但必须是知情的。

归档目录（completed/ 的计划、converge 过程记录）天然无人引用，白名单豁免。

CLI：
    python scripts/check_docs.py            # 全查
    python scripts/check_docs.py --orphans  # 只查孤儿
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# 孤儿检查只管**文档**——位置由导航链接决定的东西。
# **制品**（正文、人物卡、过程文件）的位置由命名约定和专门的登记表决定，
# 且各有专门检查器；在这里重复检查只会给出错误的修复指引
# （"接进导航或删掉" vs 正确的 "跑 check_tags.py _index"）。
EXEMPT_PATTERNS: tuple[str, ...] = (
    # —— 归档：本职即写完存档，无人引用是常态 ——
    "docs/plans/completed/",     # 已完成计划
    "docs/plans/deferred/",      # 由 docs/plans/README.md 索引（索引本身受检）
    "05_复盘/20",                 # converge 过程记录，日期开头
    "05_复盘/第",                 # 卷复盘
    # —— 镜像：由各自的机制统一登记 ——
    "_模板/",                     # 骨架，由 _模板/README.md 登记
    "_分发/",                     # 分发源，由 publish.py 的 DIST_MAP 引用
    "example_world/",            # 教学演示
    # —— 制品：位置由约定承载，登记完整性另有检查器 ——
    "03_正文/",                   # 章节 → check_maintenance.py 场景清单比对
                                 # 过程文件 → pre-commit 工作流留痕检查
)

# 会话入口——agent/用户直接打开，不需要被别处链接
ENTRY_DOCS: tuple[str, ...] = (
    "AGENTS.md", "CLAUDE.md", "GEMINI.md", "README.md",
    "使用手册.md", "简介.md",
)

PLACEHOLDER_RE = re.compile(r"[（(]待填写|[（(]待填|[（(]待选择")

# 有正文之后就该填好的文件
SHOULD_BE_FILLED: tuple[str, ...] = (
    "简介.md",
    "00_世界观/核心设定.md",
    "01_大纲/主线.md",
    "docs/style-locked.md",
)


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", "-c", "core.quotepath=false", *args],
        cwd=str(ROOT), capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    ).stdout


def _tracked_md() -> list[str]:
    return [f for f in _git("ls-files").splitlines() if f.endswith(".md")]


# 人物卡：由 02_人物/_索引.md 登记，check_tags.py 负责完整性
_CHAR_DOCS = {"README.md", "_索引.md", "人物模板.md"}


def _exempt(rel: str) -> bool:
    if rel in ENTRY_DOCS or any(rel.startswith(p) for p in EXEMPT_PATTERNS):
        return True
    # 02_人物/<角色名>.md 是制品，不是文档
    p = Path(rel)
    return str(p.parent) == "02_人物" and p.name not in _CHAR_DOCS


def _strip_code_blocks(text: str) -> str:
    """去掉围栏代码块——目录示例树里的文件名不算真引用。

    `03_正文/README.md` 的示例树里写着「第1章.md」，若算作引用，
    第 1、2 章会侥幸通过而第 3 章报错——这种偶然豁免比不检查更坏。
    """
    return re.sub(r"```.*?```", "", text, flags=re.DOTALL)


def _all_text_except(skip: str) -> str:
    """除 skip 外全部 md/py/hook 的正文，用于反查引用。"""
    buf = []
    for f in _git("ls-files").splitlines():
        if f == skip:
            continue
        if not (f.endswith(".md") or f.endswith(".py") or "githooks" in f):
            continue
        p = ROOT / f
        try:
            raw = p.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        buf.append(_strip_code_blocks(raw) if f.endswith(".md") else raw)
    return "\n".join(buf)


def _is_referenced(rel: str, corpus: str) -> bool:
    """路径、无扩展名路径、纯文件名——任一形式出现即算被引用。"""
    stem_path = rel[:-3] if rel.endswith(".md") else rel
    name = Path(rel).name
    stem_name = Path(rel).stem
    for form in (rel, stem_path, name):
        if form in corpus:
            return True
    # [[wikilink]] 常只写文件名主干
    return bool(re.search(r"\[\[[^\]]*" + re.escape(stem_name) + r"[^\]]*\]\]", corpus))


def check_orphans() -> list[str]:
    issues = []
    for rel in _tracked_md():
        if _exempt(rel):
            continue
        corpus = _all_text_except(rel)
        if not _is_referenced(rel, corpus):
            issues.append(
                f"孤儿文档：{rel}\n"
                f"    没有任何文件引用它——要么接进导航，要么删掉"
            )
    return issues


def check_placeholders() -> list[str]:
    text_dir = ROOT / "03_正文"
    chapters = [
        p for p in text_dir.rglob("第*章.md")
        if not p.name.startswith("_") and p.parent.name != "_工作"
    ] if text_dir.is_dir() else []
    if not chapters:
        return []

    issues = []
    for rel in SHOULD_BE_FILLED:
        p = ROOT / rel
        if not p.is_file():
            continue
        try:
            txt = p.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if PLACEHOLDER_RE.search(txt):
            issues.append(
                f"占位符滞留：{rel} 仍含「待填写」，但已有 {len(chapters)} 章正文"
            )
    return issues


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="文档体系检查")
    ap.add_argument("--orphans", action="store_true", help="只查孤儿文档")
    args = ap.parse_args(argv)

    issues = check_orphans()
    if not args.orphans:
        issues += check_placeholders()

    if issues:
        print(f"[FAIL] 文档体系 {len(issues)} 项：")
        for i in issues:
            print(f"  {i}")
        return 1

    print("[PASS] 无孤儿文档，无占位符滞留")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main(sys.argv[1:]))
