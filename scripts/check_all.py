#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""机械校验总入口——完工时跑一次，**无输出 = 全部通过**。

设计原则：高频机械检查不应占用 agent 注意力——通过时静默，失败时才说话；
每条失败信息本身包含修复指引，agent 不需要额外记忆修复步骤。

    python scripts/check_all.py            # 全量输出（复盘中用）
    python scripts/check_all.py --quiet    # 无输出 = 通过（完工清单默认模式）
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# 检查器列表——新增机械检查只改这一处。
# 每个条目: (名称, [命令], 失败时的修复指引)
CHECKS: list[tuple[str, list[str], str]] = [
    (
        "同步",
        ["scripts/agent_links.py", "check"],
        "python scripts/agent_links.py repair",
    ),
    (
        "模板",
        ["scripts/template.py", "check"],
        "python scripts/template.py init（补缺失）或检查 _模板/ 与 .gitignore 是否配套",
    ),
    (
        "链接",
        ["scripts/audit.py", "dead-links"],
        "DEAD：目标不存在，查路径拼写或文件是否被移动"
        "；CROSS：源码层文档指向内容层文件，分发后必断——"
        "把该文件补进 _模板/（下游 init 生成），或把这份文档划入内容层",
    ),
    (
        "伏笔",
        ["scripts/check_foreshadowing.py"],
        "超期伏笔：尽快回收或废弃；表格格式异常：检查列数和状态字段",
    ),
    (
        "关系",
        ["scripts/relationship.py", "check"],
        "python scripts/relationship.py set/update 写入缺失的关系对 → 完成后 python scripts/relationship.py regenerate",
    ),
    (
        "标签",
        ["scripts/check_tags.py", "check"],
        "补全缺失的四类标签后 python scripts/check_tags.py regenerate && python scripts/check_tags.py _index",
    ),
    (
        "章节",
        ["scripts/check_chapters.py"],
        "按提示修正 frontmatter（model/author: human/characters_present 等）或补 _准备_ 文件",
    ),
    (
        "文档",
        ["scripts/check_docs.py"],
        "孤儿文档：接进导航或删除；占位符滞留：设定落后于正文，确认是否有意",
    ),
    (
        "编码",
        ["scripts/check_encoding.py"],
        "补 encoding=\"utf-8\"——中文 Windows 的 GBK 区域会让 UTF-8 中文路径解码崩溃",
    ),
    (
        "维护",
        ["scripts/check_maintenance.py"],
        "派发维护子代理回写记忆/关系/演化（模板见 05_复盘/maintenance-executor.md）"
        "；确认不需要则在章节 frontmatter 加 maintenance_skip",
    ),
]


def main() -> int:
    ap = argparse.ArgumentParser(description="机械校验总入口——无输出即通过")
    ap.add_argument("--quiet", action="store_true",
                    help="静默模式：只在有失败时输出（完工清单默认用这个）")
    args = ap.parse_args()

    failed: list[tuple[str, str]] = []
    for name, cmd, guide in CHECKS:
        proc = subprocess.run(
            [sys.executable, *cmd],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        ok = proc.returncode == 0
        if not ok:
            failed.append((name, guide))
        if not args.quiet or not ok:
            status = "OK" if ok else "FAIL"
            if not args.quiet:
                print(f"\n[{status}] {name}")
            elif not ok:
                print(f"\n[{status}] {name}")
            body = (proc.stdout + proc.stderr).strip()
            if body:
                print("\n".join("    " + ln for ln in body.splitlines()))

    if not failed:
        if not args.quiet:
            print(f"\n[PASS] 全部 {len(CHECKS)} 项通过")
        return 0

    # 失败时：汇总 + 逐条给出修复命令
    print(f"\n{'=' * 50}")
    print(f"共 {len(failed)} 项未通过，修复后重跑：")
    for name, guide in failed:
        print(f"  [{name}] → {guide}")
    print(f"{'=' * 50}")
    return 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
