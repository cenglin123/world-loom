#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""release.py 发版管线集成测试（沙箱 + 本地 bare 远端 + gh 替身，不触网）。

守护的核心不变量：
1. 端到端发版成功——VERSION 提交、publish 推送、zip 打包、gh release
2. `gh release create --target` 收到的是 **40 位 SHA**，不是分支名
   template-dist（远端没有该分支，用分支名会 422——7a9a8ed 的修复）
3. 续跑幂等——VERSION 已提交则跳过，不产生重复 release commit
   （68cff25 的修复）
"""
from __future__ import annotations

import re
from pathlib import Path

from conftest import git, install_fake_gh, run_script

_SHA = re.compile(r"[0-9a-f]{40}")


def _gh_calls(log: Path) -> list[list[str]]:
    return [ln.split("\t") for ln in
            log.read_text(encoding="utf-8").splitlines() if ln]


def _release_once(repo: Path, env_extra: dict, notes: Path, version: str):
    return run_script(repo, "release.py", version,
                      "--notes-file", str(notes), "--skip-checks",
                      extra_env=env_extra)


def test_release_end_to_end_targets_sha(sandbox_with_remote, tmp_path):
    repo, remote = sandbox_with_remote
    env_extra, gh_log = install_fake_gh(repo, tmp_path)
    notes = tmp_path / "notes.md"
    notes.write_text("release notes\n", encoding="utf-8", newline="\n")

    r = _release_once(repo, env_extra, notes, "0.2.0")
    assert r.returncode == 0, r.stdout + r.stderr

    # VERSION 已提交，且只有一个 release commit
    assert git(repo, "show", "HEAD:VERSION") == "0.2.0"
    assert len(git(repo, "log", "--oneline", "--grep", "release: v0.2.0")
               .splitlines()) == 1

    # gh release create 的 --target 是 40 位 SHA，且等于 template-dist 的 tip
    create = next(c for c in _gh_calls(gh_log) if c[:2] == ["release", "create"])
    target = create[create.index("--target") + 1]
    assert _SHA.fullmatch(target), f"--target 应为 SHA，实为 {target!r}"
    assert target == git(repo, "rev-parse", "template-dist")
    assert target != "template-dist"

    # zip asset 传给了 gh，远端 main 也已更新
    assert any(a.endswith(".zip") for a in create)
    assert git(remote, "rev-parse", "main") == target


def test_release_rerun_is_idempotent(sandbox_with_remote, tmp_path):
    repo, remote = sandbox_with_remote
    env_extra, gh_log = install_fake_gh(repo, tmp_path)
    notes = tmp_path / "notes.md"
    notes.write_text("notes\n", encoding="utf-8", newline="\n")

    for _ in range(2):
        r = _release_once(repo, env_extra, notes, "0.3.0")
        assert r.returncode == 0, r.stdout + r.stderr

    # 两次发版只产生一个 VERSION commit（续跑跳过，不重复提交）
    assert len(git(repo, "log", "--oneline", "--grep", "release: v0.3.0")
               .splitlines()) == 1
