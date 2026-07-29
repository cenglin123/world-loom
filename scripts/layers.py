#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""源码层 / 内容层的**唯一权威划分**。

内容与源码同库同分支，全部入库、全部有 git 历史。区别只在**能不能对外分发**：

    源码层  模板、治理机制、脚本、方法文档、示例世界  → 可推送到公开仓
    内容层  世界观填写、大纲、角色、正文、伏笔、复盘   → 只留本地，永不推送

推送闸门（`.githooks/pre-push` + `scripts/publish.py`）都从本文件取路径清单——
新增目录只改这里一处，避免多源漂移。

CLI：
    python scripts/layers.py list-content        列出工作区里的内容层文件
    python scripts/layers.py classify <路径...>  逐个判定属于哪层
    python scripts/layers.py verify-tree <sha>   断言某个 git 树里不含内容层文件
"""
from __future__ import annotations

import fnmatch
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# 内容层：这些路径是"这一本书"的创作产物，不对外分发。
CONTENT_PATTERNS: tuple[str, ...] = (
    "00_世界观/核心设定.md",
    "00_世界观/外围设定.md",
    "01_大纲/*",
    "01_大纲/**/*",
    "02_人物/*",
    "02_人物/**/*",
    "03_正文/*",
    "03_正文/**/*",
    "04_伏笔/*",
    "04_伏笔/**/*",
    "05_复盘/*",
    "05_复盘/**/*",
    "docs/overview.md",
    "docs/CURRENT.md",
    "docs/style-locked.md",
)

# 命中 CONTENT_PATTERNS 但仍属源码层的例外（模板/骨架文件）。
SOURCE_EXCEPTIONS: tuple[str, ...] = (
    "01_大纲/README.md",
    "02_人物/人物模板.md",
    "03_正文/README.md",
    "04_伏笔/README.md",
    "05_复盘/reviewer-protocol.md",
    "05_复盘/reviewer-prompt-template.md",
    "05_复盘/复盘模板.md",
    "05_复盘/README.md",
)

# _模板/ 下的一切恒为源码层——即使其相对路径长得像内容层。
ALWAYS_SOURCE_PREFIXES: tuple[str, ...] = ("_模板/",)


def is_content(path: str) -> bool:
    """给定仓库相对路径（posix 风格），判断是否属于内容层。"""
    p = path.replace("\\", "/").lstrip("./")
    if any(p.startswith(pre) for pre in ALWAYS_SOURCE_PREFIXES):
        return False
    if p in SOURCE_EXCEPTIONS:
        return False
    return any(fnmatch.fnmatch(p, pat) for pat in CONTENT_PATTERNS)


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", "-c", "core.quotepath=false", *args],
        cwd=str(ROOT), capture_output=True, text=True,
        encoding="utf-8", errors="replace", check=True,
    ).stdout


def tracked_files() -> list[str]:
    return [ln for ln in _git("ls-files").splitlines() if ln]


def tree_files(ref: str) -> list[str]:
    return [ln for ln in _git("ls-tree", "-r", "--name-only", ref).splitlines() if ln]


def cmd_list_content(_argv: list[str]) -> int:
    hits = [f for f in tracked_files() if is_content(f)]
    for f in hits:
        print(f)
    print(f"\n[INFO] 内容层文件 {len(hits)} 个（已入库、有 git 历史，但不对外分发）",
          file=sys.stderr)
    return 0


def cmd_classify(argv: list[str]) -> int:
    if not argv:
        print("用法：python scripts/layers.py classify <路径...>")
        return 1
    for p in argv:
        print(f"{'内容层' if is_content(p) else '源码层'}\t{p}")
    return 0


def cmd_verify_tree(argv: list[str]) -> int:
    """断言某个 git 树/提交里不含任何内容层文件——推送闸门的最后一道复核。"""
    if not argv:
        print("用法：python scripts/layers.py verify-tree <sha>")
        return 1
    ref = argv[0]
    leaked = [f for f in tree_files(ref) if is_content(f)]
    if leaked:
        print(f"[BLOCK] {ref[:12]} 的树里含 {len(leaked)} 个内容层文件，拒绝推送：")
        for f in leaked[:20]:
            print(f"    {f}")
        if len(leaked) > 20:
            print(f"    …… 另有 {len(leaked) - 20} 个")
        return 1
    print(f"[OK] {ref[:12]} 无内容层文件泄漏")
    return 0


COMMANDS = {
    "list-content": cmd_list_content,
    "classify": cmd_classify,
    "verify-tree": cmd_verify_tree,
}


def main(argv: list[str]) -> int:
    if not argv or argv[0] not in COMMANDS:
        print(__doc__)
        return 0 if not argv else 1
    return COMMANDS[argv[0]](argv[1:])


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main(sys.argv[1:]))
