#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""机械校验总入口——完工检查清单 / 卷末复盘的"机械层"一键执行。

pre-commit 只在提交那一刻扫**暂存区**；本脚本扫**全仓当前状态**，把所有检查器
串起来跑，任一失败即返回非零。完工清单必检项。

    python scripts/check_all.py            # 全部检查
    python scripts/check_all.py --quiet    # 只打印失败项与总结
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

CHECKS: list[tuple[str, list[str]]] = [
    ("AGENTS 三文件同步", ["scripts/agent_links.py", "check"]),
    ("模板层完整性", ["scripts/template.py", "check"]),
    ("文档内链无死链", ["scripts/audit.py", "dead-links"]),
    ("伏笔状态机", ["scripts/check_foreshadowing.py"]),
    ("关系数据一致", ["scripts/relationship.py", "check"]),
    ("标签四类完整", ["scripts/check_tags.py", "check"]),
    ("章节时空一致 + 就绪自检", ["scripts/check_chapters.py"]),
]


def main() -> int:
    ap = argparse.ArgumentParser(description="内容层机械校验总入口")
    ap.add_argument("--quiet", action="store_true", help="只打印失败项与总结")
    args = ap.parse_args()

    failed: list[str] = []
    for name, cmd in CHECKS:
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
            failed.append(name)
        if not args.quiet or not ok:
            print(f"\n{'[PASS]' if ok else '[FAIL]'} {name}")
            body = (proc.stdout + proc.stderr).strip()
            if body:
                print("\n".join("    " + ln for ln in body.splitlines()))

    print("\n" + "=" * 60)
    if failed:
        print(f"[FAIL] {len(failed)}/{len(CHECKS)} 项未通过：" + "、".join(failed))
        print("修复后重跑；无法机械修复的项在完工检查清单里人工裁决。")
        return 1
    print(f"[PASS] {len(CHECKS)} 项机械检查全部通过")
    print("注意：机械层通过 ≠ 语义一致——人设/记忆/世界观漂移仍需复盘 converge。")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
