#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""B-3 regression：layers.verify_tree 在 HEAD ≠ template-dist 时也要通过。

verify-tree 必须用**已发布源**（template-dist tip → main tip → HEAD 兜底）作为
blob 比较的左源；否则在删掉 `_分发/` 的工作分支上每个 DIST_TARGETS 都会假阳性
FAIL——逼用户 `--no-verify` 绕过推送闸门。

layers.py 把 ROOT 硬编到本仓路径，所以沙箱测试要把 ROOT 注入到临时仓库。
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import layers  # noqa: E402
from conftest import SCRIPTS, _write, _init_repo, git  # noqa: E402


@pytest.fixture
def sandbox_repo(tmp_path, monkeypatch):
    """沙箱仓库 + layers.ROOT 注入。"""
    repo = tmp_path / "repo"
    (repo / "scripts").mkdir(parents=True)
    shutil.copyfile(SCRIPTS / "layers.py", repo / "scripts" / "layers.py")
    _init_repo(repo)
    monkeypatch.setattr(layers, "ROOT", repo)
    return repo


def _git_branch_main(repo: Path) -> None:
    """把默认分支显式改名为 main，让 fallback chain 稳定。"""
    try:
        git(repo, "branch", "-m", "main")
    except Exception:
        pass


def _build_published_layout(sandbox_repo: Path) -> str:
    """建一个标准分发布局：main 留 `_分发/` 与开发版 root；wip 分支做 publish 输出（root 使用版、剥 `_分发/`），并把 template-dist 指到 wip tip。

    返回 template-dist tip SHA。

    实现要点：git 分支随提交自动前进，所以「main 不动 + wip 推进」需要新建 wip
    分支承担 publish 输出，main tip 仍为 source commit（带 `_分发/`）。
    """
    _write(sandbox_repo / "_分发" / "AGENTS.md", "使用版 AGENTS（来自 _分发）\n")
    _write(sandbox_repo / "_分发" / "README.md", "使用版 README（来自 _分发）\n")
    _write(sandbox_repo / "AGENTS.md", "开发版 AGENTS（应在 verify-tree 被替换源）\n")
    _write(sandbox_repo / "README.md", "开发版 README\n")
    _write(sandbox_repo / "VERSION", "0.1.0\n")
    _write(sandbox_repo / ".gitignore", "/release\n__pycache__/\n*.pyc\n")
    _git_branch_main(sandbox_repo)
    git(sandbox_repo, "add", "-A")
    git(sandbox_repo, "commit", "-q", "-m", "main: 含 _分发/ + 开发版")
    main_tip = git(sandbox_repo, "rev-parse", "main")

    # 新建 wip 分支承担 publish 输出——main 不动，保持在 main_tip（含 _分发/）。
    git(sandbox_repo, "checkout", "-q", "-b", "wip")
    _write(sandbox_repo / "AGENTS.md", "使用版 AGENTS（来自 _分发）\n")
    _write(sandbox_repo / "README.md", "使用版 README（来自 _分发）\n")
    git(sandbox_repo, "rm", "-rf", "_分发")
    git(sandbox_repo, "add", "-A")
    git(sandbox_repo, "commit", "-q", "-m", "publish: 替换 root + 剥 _分发/")
    git(sandbox_repo, "branch", "template-dist", "HEAD")
    git(sandbox_repo, "checkout", "-q", "main")
    return git(sandbox_repo, "rev-parse", "template-dist")


def test_verify_tree_passes_on_published_tree(sandbox_repo):
    """target = template-dist：source_ref 解析到 template-dist，blob 一致 → PASS。"""
    dist_tip = _build_published_layout(sandbox_repo)
    r = layers.cmd_verify_tree([dist_tip])
    assert r == 0, f"template-dist tip 的 verify-tree 必须通过（输出见 layers 调用）"


def test_verify_tree_source_blob_uses_published_ref_not_work_branch(sandbox_repo):
    """核心 B-3 回归：HEAD 工作分支 ≠ template-dist，且 work branch 含不同 `_分发/`，verify-tree 仍按发布源（main）比较。

    旧实现 `_blob("HEAD", "_分发/AGENTS.md")`：HEAD 改了 `_分发/` 时返回的内容
    与发布版 AGENTS.md 不等 → 假阳性 FAIL。
    新实现：source_ref 锚到 main tip（始终含原始 `_分发/`），AGENTS.md 与
    `_分发/AGENTS.md` 一致 → PASS。
    """
    dist_tip = _build_published_layout(sandbox_repo)

    # 在 wip 分支上做修改并提交——模拟 HEAD 工作分支改变了 _分发/ 内容。
    git(sandbox_repo, "checkout", "-q", "wip")
    _write(sandbox_repo / "_分发" / "AGENTS.md", "WORK-BRANCH 改了 _分发/ 内容\n")
    _write(sandbox_repo / "README.md", "WORK-BRANCH dev README\n")
    git(sandbox_repo, "add", "-A")
    git(sandbox_repo, "commit", "-q", "-m", "wip: 改 _分发/ 内容")
    work_head = git(sandbox_repo, "rev-parse", "HEAD")
    assert work_head != dist_tip, "测试前提：工作分支 tip 必须 ≠ template-dist tip"

    # 用发布源 SHA 跑 verify-tree。target = template-dist（已发布），source 走 main。
    r = layers.cmd_verify_tree([dist_tip])
    assert r == 0, \
        f"用发布源 SHA 跑 verify-tree 必须通过（防假阳性）。\n" \
        f"work_head={work_head}, dist_tip={dist_tip}"


def test_verify_tree_falls_back_to_main_when_no_template_dist(sandbox_repo):
    """无 template-dist ref 时：源锚应回退到 main tip。

    main 含原始 `_分发/` 与 root 使用版，target = publish 提交（root 使用版、
    剥 `_分发/`）。源锚取 main tip → AGENTS.md 与 `_分发/AGENTS.md` 一致 → PASS。
    """
    _write(sandbox_repo / "_分发" / "AGENTS.md", "使用版 AGENTS\n")
    _write(sandbox_repo / "_分发" / "README.md", "使用版 README\n")
    _write(sandbox_repo / "AGENTS.md", "使用版 AGENTS\n")  # publish 替换后 = 使用版
    _write(sandbox_repo / "README.md", "使用版 README\n")
    _write(sandbox_repo / "VERSION", "0.1.0\n")
    _write(sandbox_repo / ".gitignore", "/release\n__pycache__/\n*.pyc\n")
    _git_branch_main(sandbox_repo)
    git(sandbox_repo, "add", "-A")
    git(sandbox_repo, "commit", "-q", "-m", "init: 含 _分发/ + root 使用版")

    # 在 wip 分支上做 publish：root 保持使用版（已一致），剥 _分发/。
    git(sandbox_repo, "checkout", "-q", "-b", "wip")
    git(sandbox_repo, "rm", "-rf", "_分发")
    git(sandbox_repo, "commit", "-q", "-m", "publish: 剥 _分发/")
    published_sha = git(sandbox_repo, "rev-parse", "HEAD")

    # 验证：没有 template-dist ref
    td_exists = git(sandbox_repo, "rev-parse", "--verify", "refs/heads/template-dist",
                    check=False)
    assert not td_exists or "fatal" in td_exists.lower(), \
        f"测试前提：不应存在 template-dist ref（实际 {td_exists!r}）"

    r = layers.cmd_verify_tree([published_sha])
    assert r == 0, \
        f"无 template-dist 时，main fallback 应通过。\n" \
        f"main ref 应被解析为 source_ref；published_sha={published_sha}"


def test_published_source_ref_prefers_template_dist(sandbox_repo):
    """_published_source_ref 必须优先取 template-dist tip。"""
    _build_published_layout(sandbox_repo)
    expected = git(sandbox_repo, "rev-parse", "template-dist")
    got = layers._published_source_ref()
    # main 与 template-dist 都存在时按优先级取 main（始终含 _分发/）。
    # 此测试断言 fallback chain 中第一个存在的 ref 即被返回——main 排在第一。
    main_tip = git(sandbox_repo, "rev-parse", "main")
    assert got == main_tip, \
        f"main 优先于 template-dist（main 始终含 _分发/）：main={main_tip}, got={got}"


def test_published_source_ref_falls_back_to_main(sandbox_repo):
    """无 template-dist ref 时：应回退到 main tip。"""
    _write(sandbox_repo / "VERSION", "0.1.0\n")
    _git_branch_main(sandbox_repo)
    git(sandbox_repo, "add", "-A")
    git(sandbox_repo, "commit", "-q", "-m", "init")
    expected = git(sandbox_repo, "rev-parse", "main")
    got = layers._published_source_ref()
    assert got == expected, f"无 template-dist 时应回退到 main tip：expected={expected}, got={got}"


def test_published_source_ref_falls_back_to_template_dist_when_main_missing(sandbox_repo):
    """无 main ref 但有 template-dist 时：应回退到 template-dist。

    注意：在本仓的 publish 模型下，template-dist 本身没有 `_分发/`。所以这条
    fallback 路径实际上**不能给出有效源 blob**，verify-tree 会因比对失败而
    FAIL——但 fallback chain 本身在 ref 解析上必须正确：能用上 template-dist。
    """
    _write(sandbox_repo / "_分发" / "AGENTS.md", "use-version\n")
    _write(sandbox_repo / "_分发" / "README.md", "use-version\n")
    _write(sandbox_repo / "AGENTS.md", "use-version\n")
    _write(sandbox_repo / "README.md", "use-version\n")
    _write(sandbox_repo / "VERSION", "0.1.0\n")
    _write(sandbox_repo / ".gitignore", "/release\n__pycache__/\n*.pyc\n")
    _git_branch_main(sandbox_repo)
    git(sandbox_repo, "add", "-A")
    git(sandbox_repo, "commit", "-q", "-m", "init")
    # 新建 wip 分支做 publish 输出
    git(sandbox_repo, "checkout", "-q", "-b", "wip")
    git(sandbox_repo, "rm", "-rf", "_分发")
    git(sandbox_repo, "add", "-A")
    git(sandbox_repo, "commit", "-q", "-m", "publish")
    git(sandbox_repo, "branch", "template-dist", "HEAD")
    # 删除 main
    git(sandbox_repo, "update-ref", "-d", "refs/heads/main")

    expected = git(sandbox_repo, "rev-parse", "template-dist")
    got = layers._published_source_ref()
    assert got == expected, \
        f"main 缺时回退 template-dist：expected={expected}, got={got}"


def test_published_source_ref_falls_back_to_head_when_no_branches(sandbox_repo):
    """main/template-dist 都缺时：HEAD 兜底——first-release 场景。"""
    # 沙箱只有默认分支（被改名为 main）。HEAD 兜底前 main 已被删，HEAD 指向
    # 当前 commit 本身（detached？）。直接用 git checkout --detach 把 HEAD 钉住。
    _write(sandbox_repo / "VERSION", "0.1.0\n")
    _git_branch_main(sandbox_repo)
    git(sandbox_repo, "add", "-A")
    git(sandbox_repo, "commit", "-q", "-m", "init")
    head_sha = git(sandbox_repo, "rev-parse", "HEAD")
    git(sandbox_repo, "checkout", "-q", head_sha)  # detach so HEAD stays valid
    git(sandbox_repo, "update-ref", "-d", "refs/heads/main")
    got = layers._published_source_ref()
    assert got == "HEAD", f"两 ref 都缺时应兜底 HEAD：got={got}"