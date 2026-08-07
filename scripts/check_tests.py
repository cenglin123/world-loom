#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""测试检查器——把管线测试套件接进 check_all 的完工必检。

本文件属**源码层**、随分发出去；但测试本体 tests/ 是**开发层**、不分发。
所以下游没有 tests/，本检查静默跳过（退出 0）；只在开发仓真正跑测试。

判定与行为：
- tests/ 不存在            → 退出 0（下游/未建测试的环境，无需测试）
- tests/ 存在但无 pytest   → FAIL，给出安装指引（开发环境不完整）
- 否则跑 pytest 并透传退出码与输出

以干净环境跑，避免弄脏工作区：
- PYTHONDONTWRITEBYTECODE=1   不产生 __pycache__
- -p no:cacheprovider         不产生 .pytest_cache

加 --runslow 启用 @pytest.mark.slow 标记的测试（含跨版本 update 回归），
发版前由 release.py 自动传递。
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TESTS_DIR = ROOT / "tests"


def main() -> int:
    ap = argparse.ArgumentParser(description="测试检查器——check_all 完工必检用")
    ap.add_argument("--runslow", action="store_true",
                    help="运行标记为 slow 的测试（默认跳过；含跨版本 update 回归）")
    args = ap.parse_args()

    if not TESTS_DIR.is_dir():
        # 下游分发版没有 tests/（开发层不分发）——无需测试，直接通过
        return 0

    try:
        import pytest  # noqa: F401
    except ImportError:
        print("[FAIL] tests/ 存在但没有 pytest，无法跑管线测试")
        print("    安装：pip install pytest")
        return 1

    env = {**os.environ,
           "PYTHONDONTWRITEBYTECODE": "1",
           "PYTHONIOENCODING": "utf-8"}
    cmd = [sys.executable, "-m", "pytest", "tests/",
           "-q", "--color=no", "-p", "no:cacheprovider"]
    if args.runslow:
        cmd.append("--runslow")
    proc = subprocess.run(
        cmd,
        cwd=str(ROOT), capture_output=True, text=True,
        encoding="utf-8", errors="replace", env=env,
    )
    if proc.stdout:
        print(proc.stdout, end="")
    if proc.stderr:
        print(proc.stderr, end="", file=sys.stderr)
    return proc.returncode


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
