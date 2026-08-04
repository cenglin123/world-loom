#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""钩子生效性检查——防"机制在仓库里，但一次都没跑过"。

`.githooks/` 里的三个钩子是本仓治理的机械底座：

    pre-commit   提交前机械校验、工作流留痕
    commit-msg   受保护文档的 [governance] 标记
    pre-push     推送闸门（默认拒绝，防创作内容外泄）

但 git 只认 `core.hooksPath`，而**全新 clone 的这项是空的**——三个钩子文件
明明在仓库里躺着，却一个都不执行。文档同时又按"生效"在引用它们
（AGENTS.md 的受保护文档清单、_模板/README 的闸门说明），于是形成最坏的一种
状态：以为有保护，实际裸奔。

`template.py init` 会设置它，本检查兜住没跑过 init、或配置被改掉的情况。

CLI：
    python scripts/check_hooks.py
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOOKS_DIR = ROOT / ".githooks"
EXPECTED = ".githooks"
REQUIRED_HOOKS = ("pre-commit", "commit-msg", "pre-push")


def _git(*args: str) -> str | None:
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=ROOT, capture_output=True, timeout=10,
            text=True, encoding="utf-8", errors="replace",
        )
    except (subprocess.TimeoutExpired, OSError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.strip()


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")

    if not HOOKS_DIR.is_dir():
        print("[SKIP] 无 .githooks/ 目录")
        return 0
    if _git("rev-parse", "--git-dir") is None:
        print("[SKIP] 不是 git 仓库（或 git 不可用）")
        return 0

    missing = [h for h in REQUIRED_HOOKS if not (HOOKS_DIR / h).is_file()]
    if missing:
        print(f"[FAIL] .githooks/ 缺少钩子：{'、'.join(missing)}")
        print("    修复：从上游取回——git checkout origin/main -- .githooks/")
        return 1

    current = _git("config", "--local", "core.hooksPath") or ""
    if current == EXPECTED:
        print(f"[PASS] 钩子已生效（core.hooksPath → {EXPECTED}）")
        return 0

    if current:
        print(f"[FAIL] core.hooksPath 指向 {current}，本仓的三个钩子不会执行")
    else:
        print("[FAIL] core.hooksPath 未设置——.githooks/ 里的钩子一个都不会执行")
        print("    全新 clone 默认就是这个状态：提交校验、治理标记、推送闸门全部形同虚设")
    print(f"    修复：git config core.hooksPath {EXPECTED}"
          f"（或跑 python scripts/template.py init）")
    return 1


if __name__ == "__main__":
    sys.exit(main())
