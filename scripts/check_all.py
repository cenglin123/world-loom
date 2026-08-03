#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""机械校验总入口——完工时跑一次，**无输出 = 全部通过**。

设计原则：高频机械检查不应占用 agent 注意力——通过时静默，失败时才说话；
每条失败信息本身包含修复指引，agent 不需要额外记忆修复步骤。

    python scripts/check_all.py            # 全量输出（复盘中用）
    python scripts/check_all.py --quiet    # 无输出 = 通过（完工清单默认模式）

远端更新提醒：每次运行末尾检查 GitHub 上游有无新提交，有则打印 [提醒]——
脚本只提醒、不自动更新，是否 `git pull` 由 agent 判断。离线/无上游分支时静默。
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def check_remote_updates() -> str | None:
    """远端上游有新提交 → 提醒文案；无上游/离线/无更新 → None（全程 fail-open）。"""
    try:
        # fetch 失败（离线等）不阻断——仍可用上次 fetch 的远端跟踪分支比较
        subprocess.run(
            ["git", "fetch", "--quiet"],
            cwd=ROOT, capture_output=True, timeout=10,
            text=True, encoding="utf-8", errors="replace",
        )
        proc = subprocess.run(
            ["git", "rev-list", "--count", "HEAD..@{u}"],
            cwd=ROOT, capture_output=True, timeout=10,
            text=True, encoding="utf-8", errors="replace",
        )
        if proc.returncode != 0:
            return None
        n = int(proc.stdout.strip() or "0")
    except (subprocess.TimeoutExpired, ValueError, OSError):
        return None
    if n <= 0:
        return None
    return (
        f"[提醒] 远端上游有 {n} 个新提交（本项目可能已更新）。"
        f"脚本不自动更新——先 git pull 或人工判断后再开始工作"
    )

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
        "方法",
        ["scripts/method.py", "check"],
        "索引过期 → python scripts/method.py index"
        "；缺 症状 字段 → 补上求助者会用的原话，否则这张卡搜不到"
        "；近重复 → 合并，或让两张卡的一句话与落点明确分开",
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
        reminder = check_remote_updates()
        if reminder:
            print(f"\n{reminder}")
        return 0

    # 失败时：汇总 + 逐条给出修复命令
    print(f"\n{'=' * 50}")
    print(f"共 {len(failed)} 项未通过，修复后重跑：")
    for name, guide in failed:
        print(f"  [{name}] → {guide}")
    print(f"{'=' * 50}")
    reminder = check_remote_updates()
    if reminder:
        print(f"\n{reminder}")
    return 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
