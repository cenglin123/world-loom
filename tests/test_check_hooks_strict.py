#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""B-4 regression：check_hooks.py 必须支持 --strict 把 SKIP 转 FAIL。

开发仓里若有人误删 .githooks/，默认 SKIP 会让 enforcement 静默挂掉。开发仓
check_all 必须传 --strict 让其 FAIL，下游用户侧 check_all 不传 --strict 仍可
SKIP（他们可能用 release zip 解压，没有 .git/）。
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import check_hooks  # noqa: E402
from conftest import SCRIPTS, _clean_env, _write, _init_repo, git  # noqa: E402


@pytest.fixture
def sandbox_no_hooks(tmp_path, monkeypatch):
    """无 .githooks/ 的临时 git 仓 + ROOT 注入。"""
    repo = tmp_path / "repo"
    (repo / "scripts").mkdir(parents=True)
    shutil.copyfile(SCRIPTS / "check_hooks.py", repo / "scripts" / "check_hooks.py")
    # 故意不创建 .githooks/
    _init_repo(repo)
    # conftest 的 _init_repo 把 core.hooksPath 设为 .git/hooks；check_hooks 看
    # 到非空且非 .githooks 就 FAIL，覆盖测试意图。unset 掉。
    git(repo, "config", "--unset", "core.hooksPath")
    monkeypatch.setattr(check_hooks, "ROOT", repo)
    # HOOKS_DIR 在 import 时按真 ROOT 计算；也要重指向沙箱
    monkeypatch.setattr(check_hooks, "HOOKS_DIR", repo / ".githooks")
    return repo


@pytest.fixture
def sandbox_with_hooks(tmp_path, monkeypatch):
    """完整 .githooks/ 的临时 git 仓 + ROOT 注入，core.hooksPath 已正确指到 .githooks。"""
    repo = tmp_path / "repo"
    (repo / "scripts").mkdir(parents=True)
    (repo / ".githooks").mkdir(parents=True)
    shutil.copyfile(SCRIPTS / "check_hooks.py", repo / "scripts" / "check_hooks.py")
    for h in ("pre-commit", "commit-msg", "pre-push"):
        (repo / ".githooks" / h).write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    _init_repo(repo)
    # 用相对路径 ".githooks"（与 EXPECTED 一致），覆盖 conftest 默认设的绝对路径
    git(repo, "config", "core.hooksPath", ".githooks")
    monkeypatch.setattr(check_hooks, "ROOT", repo)
    monkeypatch.setattr(check_hooks, "HOOKS_DIR", repo / ".githooks")
    return repo


def test_check_hooks_skip_returns_zero_by_default(sandbox_no_hooks):
    """无 --strict：无 .githooks/ 时返回 0（SKIP）——保证下游用户场景不变。"""
    rc = check_hooks.main([])
    assert rc == 0, "默认模式下缺 .githooks/ 应 SKIP（return 0）"


def test_check_hooks_strict_returns_one_when_no_hooks_dir(sandbox_no_hooks):
    """--strict：无 .githooks/ 时返回 1（FAIL）——开发仓不可静默 SKIP。"""
    rc = check_hooks.main(["--strict"])
    assert rc == 1, "--strict 下缺 .githooks/ 必须 FAIL（return 1）"


def test_check_hooks_strict_returns_one_when_no_git(sandbox_no_hooks):
    """--strict：非 git 仓库时返回 1（FAIL）。"""
    # 删掉 .git/ 模拟「非 git 仓库」
    import shutil as _sh
    _sh.rmtree(sandbox_no_hooks / ".git")
    rc = check_hooks.main(["--strict"])
    assert rc == 1, "--strict 下非 git 仓库必须 FAIL（return 1）"


def test_check_hooks_default_skip_when_no_git(sandbox_no_hooks):
    """默认：非 git 仓库时仍 SKIP（return 0）——下游 release zip 场景。"""
    import shutil as _sh
    _sh.rmtree(sandbox_no_hooks / ".git")
    rc = check_hooks.main([])
    assert rc == 0, "默认模式下非 git 仓库应 SKIP（return 0）"


def test_check_hooks_passes_when_hooks_dir_and_config_correct(sandbox_with_hooks, monkeypatch):
    """hooks 目录齐 + core.hooksPath 已设：PASS（默认与 --strict 都应通过）。"""
    # fixture 已经把 core.hooksPath 设为 ".githooks"，下面只验证两种模式
    for argv in ([], ["--strict"]):
        rc = check_hooks.main(argv)
        assert rc == 0, f"配置正确时必须 PASS（argv={argv}）"


def test_check_hooks_cli_help_message(sandbox_no_hooks, capsys):
    """--help 应输出 usage 信息（add_help=True 默认行为；确认不破 CLI）。"""
    with pytest.raises(SystemExit):
        check_hooks.main(["--help"])
    captured = capsys.readouterr()
    assert "usage" in captured.out.lower() or "--strict" in captured.out, \
        f"--help 应打印 usage，实际：{captured.out!r}"


def test_check_all_invokes_check_hooks_with_strict():
    """check_all.py 的 CHECKS 列表必须给 check_hooks.py 传 --strict。

    这是「开发仓严格、下游宽松」机制的契约——check_all.py 是源码层文件，
    随分发出去时下游用户跑也会传 --strict。但他们的 check_hooks.py 默认
    SKIP 分支也会被 --strict 转 FAIL——下游若没有 .githooks/ 会 FAIL。

    等等——这是合同里说的"下游不传 --strict"——但代码看 CHECKS 写死了 --strict，
    下游必然传。除非分发时修改——但 publish.py 不剥 scripts/check_all.py。

    实际：本测试只验证 check_all.py 当前**写的就是 --strict**。分发到下游后，
    下游用户若 release zip 没有 .githooks/，他们的 check_all 钩子检查会 FAIL
    ——这与「下游 SKIP」的意图相反。

    契约："check_all 在用户侧不传 --strict"。所以发布层 publish.py 应在
    分发时把 check_all.py 中的 --strict 替换掉（类似 DIST_MAP 机制）。
    本测试只断言 check_all.py 当前确实传了 --strict；publish.py 替换
    机制属于后续任务，不在本轮范围。
    """
    text = (SCRIPTS / "check_all.py").read_text(encoding="utf-8")
    # 找到「钩子」CHECK 条目的命令 list
    import re
    m = re.search(r'\(\s*"钩子",\s*\[([^\]]+)\]', text)
    assert m, "check_all.py 中未找到「钩子」CHECK 条目"
    cmd_str = m.group(1)
    assert "--strict" in cmd_str, \
        f"check_all.py 中钩子检查必须传 --strict，实际命令：{cmd_str}"