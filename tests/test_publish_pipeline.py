#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""publish.py 分发管线集成测试（沙箱仓库 + 本地 bare 远端，不触网）。

守护的核心不变量：
1. dry-run 零副作用——不建分发分支、不推送
2. --force 后分发树**不含任何内容层/开发层文件**（防泄漏的根本保证）
3. DIST_MAP 映射正确——_分发/AGENTS.md → AGENTS/CLAUDE/GEMINI.md，
   _分发/README.md → README.md，且 _分发/ 本身不出现在分发树
4. blob 一致性——分发树根目录的 AGENTS/README 是**使用版**内容，
   不是开发版（开发版泄漏必须被拦）
"""
from __future__ import annotations

from pathlib import Path

from conftest import git, run_script


def _dist_files(repo: Path) -> list[str]:
    return git(repo, "ls-tree", "-r", "--name-only", "template-dist").splitlines()


def test_dry_run_has_no_side_effects(sandbox_with_remote):
    repo, remote = sandbox_with_remote
    r = run_script(repo, "publish.py")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "[DRY-RUN]" in r.stdout

    # 未创建分发分支
    assert git(repo, "rev-parse", "--verify", "--quiet",
               "refs/heads/template-dist", check=False) == ""
    # 远端没有任何 ref
    assert git(remote, "for-each-ref") == ""


def test_force_strips_content_and_maps_dist(sandbox_with_remote):
    repo, remote = sandbox_with_remote
    r = run_script(repo, "publish.py", "--force")
    assert r.returncode == 0, r.stdout + r.stderr

    files = _dist_files(repo)

    # —— 不变量 2：内容层/开发层全部被剥掉 ——
    for leaked in ("00_世界观/核心设定.md", "03_正文/第1卷/第1章.md",
                   "docs/CURRENT.md", "简介.md", "scripts/release.py"):
        assert leaked not in files, f"内容/开发层文件泄漏进分发树：{leaked}"

    # —— 不变量 3：DIST_MAP 映射 + _分发/ 本身被移除 ——
    for mapped in ("AGENTS.md", "CLAUDE.md", "GEMINI.md", "README.md"):
        assert mapped in files, f"映射目标缺失：{mapped}"
    assert not any(f.startswith("_分发/") for f in files), "_分发/ 残留"

    # 源码层保留
    for kept in ("scripts/layers.py", "scripts/publish.py", "VERSION",
                 "_模板/README.md"):
        assert kept in files, f"源码层文件丢失：{kept}"

    # —— 不变量 4：blob 一致性（根目录文档是使用版，不是开发版）——
    assert git(repo, "show", "template-dist:AGENTS.md") == "使用版 AGENTS"
    assert git(repo, "show", "template-dist:README.md") == "使用版 README"
    # AGENTS/CLAUDE/GEMINI 三者同一 blob（单一源，天然同步）
    assert (git(repo, "rev-parse", "template-dist:AGENTS.md")
            == git(repo, "rev-parse", "template-dist:CLAUDE.md")
            == git(repo, "rev-parse", "template-dist:GEMINI.md"))

    # 远端 main 拿到的是同一棵干净的分发树
    remote_files = git(remote, "ls-tree", "-r", "--name-only", "main").splitlines()
    assert "00_世界观/核心设定.md" not in remote_files
    assert "AGENTS.md" in remote_files
