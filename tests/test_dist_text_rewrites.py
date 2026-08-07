#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""DIST_TEXT_REWRITES 机制端到端守护——publish.py 的 dev/dist 文本重写。

机制：publish.py 在构建分发树时，对 DIST_TEXT_REWRITES 列表中的文件按
`(dev_text → dist_text)` 做文本替换，让开发仓的 dev 行为（如 `--strict`）
与下游用户行为（如无 `--strict`）分离。

守护两类曾发生的 bug：
- **Bug A**：rev-parse 失败时 stdout 是 echo 字符串（如 "HEAD:path"），truthy
  检查不跳过，`cat-file blob<echo>` 抛 SystemExit → 整个 publish 崩溃
- **Bug B**：`update-index --remove path` 从工作区重读 blob，覆盖了
  `--add --cacheinfo` 写入的 rewrite → 改写表面声明成功但实际失效

测试借用 conftest 的 sandbox_with_remote（含 _分发/、PIPELINE_SCRIPTS、远端），
再补一份 dev 版 scripts/check_all.py（含 --strict）以触发 DIST_TEXT_REWRITES
第一条规则。
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import REAL_ROOT, SCRIPTS


def _read_blob(repo: Path, ref_path: str) -> str:
    r = subprocess.run(
        ["git", "-c", "core.quotepath=false", "show", f"{ref_path}"],
        cwd=str(repo), capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )
    assert r.returncode == 0, f"git show {ref_path} 失败：{r.stderr}"
    return r.stdout


@pytest.fixture
def sandbox_with_check_all(sandbox_with_remote):
    """sandbox_with_remote + dev 版 scripts/check_all.py（含 --strict）。"""
    sim, remote = sandbox_with_remote
    shutil.copy(SCRIPTS / "check_all.py", sim / "scripts" / "check_all.py")
    subprocess.run(
        ["git", "add", "scripts/check_all.py"],
        cwd=str(sim), check=True,
    )
    subprocess.run(
        ["git", "commit", "-q", "-m", "add dev check_all"],
        cwd=str(sim), check=True,
    )
    return sim, remote


def test_rewrite_applied_when_dev_text_present(sandbox_with_check_all):
    """dev 版含 --strict → 重写后 dist 不应再含 --strict。守护 Bug B 回归。"""
    sim, _remote = sandbox_with_check_all
    dev_blob = _read_blob(sim, "HEAD:scripts/check_all.py")
    assert "--strict" in dev_blob, "测试前提：dev 版必须含 --strict"

    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "NOVEL_PUBLISH": "1"}
    r = subprocess.run(
        [sys.executable, "scripts/publish.py", "--force"],
        cwd=str(sim), capture_output=True, text=True,
        encoding="utf-8", errors="replace", env=env,
    )
    assert r.returncode == 0, f"publish 失败：\n{r.stdout}\n{r.stderr}"
    assert "B-4" in r.stdout, f"应声明应用了 B-4 重写：{r.stdout}"

    dist_blob = _read_blob(sim, "template-dist:scripts/check_all.py")
    assert "--strict" not in dist_blob, (
        "DIST_TEXT_REWRITE 未生效——dist 的 check_all.py 仍含 --strict。"
        "可能是 Bug B 回归（update-index --remove 反覆盖）。"
    )
    assert '"scripts/check_hooks.py"' in dist_blob, (
        f"重写后应保留 'scripts/check_hooks.py'：{dist_blob[:200]}"
    )


def test_rewrite_silently_skipped_when_path_missing(sandbox_with_remote):
    """scripts/check_all.py 不在 HEAD → publish 必须静默跳过、不能崩。

    守护 Bug A 的回归：路径不存在时 rev-parse 失败，旧实现未 skip 直接
    cat-file 抛 SystemExit。
    """
    sim, _remote = sandbox_with_remote
    # 故意不加 check_all.py——DIST_TEXT_REWRITES 列表里的路径在 HEAD 不存在

    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    r = subprocess.run(
        [sys.executable, "scripts/publish.py", "--force"],
        cwd=str(sim), capture_output=True, text=True,
        encoding="utf-8", errors="replace", env=env,
    )
    assert r.returncode == 0, (
        f"check_all.py 不在 HEAD 时 publish 不应崩：\n{r.stdout}\n{r.stderr}"
    )
    # 应静默跳过——没有任何 "B-4" 重写声明
    assert "B-4" not in r.stdout, (
        f"check_all.py 不存在时不应声明 B-4 重写：{r.stdout}"
    )