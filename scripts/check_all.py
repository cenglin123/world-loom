#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""机械校验总入口——完工时跑一次，**无输出 = 全部通过**。

设计原则：高频机械检查不应占用 agent 注意力——通过时静默，失败时才说话；
每条失败信息本身包含修复指引，agent 不需要额外记忆修复步骤。

    python scripts/check_all.py            # 全量输出（复盘中用）
    python scripts/check_all.py --quiet    # 无输出 = 通过（完工清单默认模式）

远端更新提醒：每 20 次提交查一次 GitHub 上游有无新提交，有则打印 [提醒]——
脚本只提醒、不自动更新，是否 `git pull` 由 agent 判断。离线/无上游分支时静默。
[提醒] 不是 FAIL，不影响退出码。
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# 联网是本脚本唯一的慢操作，而完工必检是高频动作——按提交数节流，
# 只有跨过间隔才 fetch。计数状态放 .git/ 下：不入库、不随分发外泄、
# 全新 clone 自动归零（新 clone 本就该查一次）。
REMOTE_CHECK_INTERVAL = 20
REMOTE_CHECK_STATE = "world-loom-remote-check"


def _git(*args: str, timeout: int = 10) -> str | None:
    """跑一条 git，成功返回 stdout（已 strip）；失败/超时返回 None。"""
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=ROOT, capture_output=True, timeout=timeout,
            text=True, encoding="utf-8", errors="replace",
        )
    except (subprocess.TimeoutExpired, OSError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.strip()


def check_remote_updates() -> str | None:
    """上游有新提交 → 提醒文案；未到间隔/无上游/离线/无更新 → None（全程 fail-open）。"""
    # 无上游（开发仓即如此）→ 一次本地调用就返回，不联网也不动计数
    if _git("rev-parse", "--abbrev-ref", "@{u}") is None:
        return None
    head = _git("rev-list", "--count", "HEAD")
    git_dir = _git("rev-parse", "--git-dir")
    if head is None or git_dir is None:
        return None
    try:
        current = int(head)
    except ValueError:
        return None

    state = ROOT / git_dir / REMOTE_CHECK_STATE
    try:
        last = int(state.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        last = None
    # last 更大 = 历史被改写（reset/rebase）→ 当作到期，重新计数
    if last is not None and 0 <= current - last < REMOTE_CHECK_INTERVAL:
        return None

    # 先记账再联网：离线时也只在下一个间隔重试，不会每次运行都干等 fetch 超时
    try:
        state.write_text(str(current), encoding="utf-8", newline="\n")
    except OSError:
        pass

    # fetch 失败（离线等）不阻断——仍可用上次 fetch 的远端跟踪分支比较
    _git("fetch", "--quiet")
    ahead = _git("rev-list", "--count", "HEAD..@{u}")
    if ahead is None:
        return None
    try:
        n = int(ahead)
    except ValueError:
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
        "钩子",
        ["scripts/check_hooks.py"],
        "git config core.hooksPath .githooks——全新 clone 默认不启用，"
        "提交校验/治理标记/推送闸门会全部失效",
    ),
    (
        "编码",
        ["scripts/check_encoding.py"],
        "源码缺 encoding=/newline= → 按提示补（中文 Windows 会解码崩溃、写出 CRLF）"
        "；工作区有 CRLF → python scripts/check_encoding.py --fix-eol",
    ),
    (
        "测试",
        ["scripts/check_tests.py"],
        "python -m pytest tests/ -v 查看失败详情——管线测试守护分发防泄漏与发版流程，"
        "失败说明 scripts/ 的改动破坏了既有保证（下游无 tests/ 时本项自动跳过）",
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
