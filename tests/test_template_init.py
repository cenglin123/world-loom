#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""template.py init 的 git init 强制前置——enforcement 层从源头兜底。

release zip 由 `git archive template-dist` 产生，不含 .git/。如果 init 不强制
git init，钩子挂载（`git config core.hooksPath .githooks`）就是空操作——
pre-commit / commit-msg / pre-push 三个闸门都不会跑，整个 enforcement 层裸奔。

这是从源头关掉 enforcement，比 update 漏洞都更基础。
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from conftest import SCRIPTS


def _setup_release_sandbox(tmp_path: Path) -> Path:
    """Build a tmp dir mimicking an unzipped release: scripts/, _模板/, .githooks/."""
    sim = tmp_path / "release"
    (sim / "scripts").mkdir(parents=True)
    (sim / "_模板" / "00_世界观").mkdir(parents=True)
    (sim / ".githooks").mkdir(parents=True)
    shutil.copy(SCRIPTS / "template.py", sim / "scripts" / "template.py")
    shutil.copy(SCRIPTS / "layers.py", sim / "scripts" / "layers.py")
    (sim / "_模板" / "00_世界观" / "核心设定.md").write_text(
        "# 世界法则\n（待填写）\n", encoding="utf-8"
    )
    return sim


def _run_init(sim: Path) -> subprocess.CompletedProcess:
    env = {**os.environ,
           "PYTHONDONTWRITEBYTECODE": "1",
           "PYTHONIOENCODING": "utf-8"}
    return subprocess.run(
        [sys.executable, "scripts/template.py", "init"],
        cwd=str(sim), capture_output=True, text=True,
        encoding="utf-8", errors="replace", env=env,
    )


def _hooks_path(sim: Path) -> str:
    r = subprocess.run(
        ["git", "config", "--local", "core.hooksPath"],
        cwd=str(sim), capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )
    return r.stdout.strip() if r.returncode == 0 else ""


def test_init_git_inits_when_no_dotgit(tmp_path: Path):
    """无 .git/ 跑 init：必须 git init、生成产物、挂载钩子——enforcement 不能空转。"""
    sim = _setup_release_sandbox(tmp_path)
    assert not (sim / ".git").exists(), "测试前提：裸目录"

    r = _run_init(sim)

    assert r.returncode == 0, f"init 失败：\n{r.stdout}\n{r.stderr}"
    assert (sim / ".git").exists(), "init 必须在无 .git/ 时执行 git init"
    assert (sim / "00_世界观" / "核心设定.md").exists(), \
        "init 应生成内容骨架产物"
    assert _hooks_path(sim) == ".githooks", \
        f"core.hooksPath 应挂载到 .githooks，实为 {_hooks_path(sim)!r}"
    # stdout 应明示 git init 发生过
    assert "已 git init" in r.stdout, \
        f"stdout 应告知用户发生了 git init：{r.stdout}"


def test_init_skips_git_init_when_already_repo(tmp_path: Path):
    """已是 git 仓库时跑 init：不重复 init、但仍挂载钩子。"""
    sim = _setup_release_sandbox(tmp_path)
    subprocess.run(["git", "init", "-q"], cwd=str(sim), check=True)

    r = _run_init(sim)

    assert r.returncode == 0, f"已 init 的仓库再跑 init 应成功：\n{r.stdout}\n{r.stderr}"
    assert _hooks_path(sim) == ".githooks", \
        "已 init 的仓库跑 init，钩子仍应被挂载"
    # 不应再提示「已 git init」
    assert "已 git init" not in r.stdout, \
        f"已 init 仓库不应再次触发 git init 提示：{r.stdout}"


def test_init_refuses_when_git_unavailable(tmp_path: Path, monkeypatch):
    """git 不在 PATH 中时 init 必须 fail——enforcement 失败不能沉默继续。"""
    sim = _setup_release_sandbox(tmp_path)
    monkeypatch.setenv("PATH", "")  # 让 git 找不到

    r = _run_init(sim)

    assert r.returncode != 0, \
        f"git 不可用时 init 必须返回非 0；stdout={r.stdout!r}"
    assert "git 未安装" in r.stdout or "git init 失败" in r.stdout, \
        f"应给出明确错误：{r.stdout}"
    # 不应生成产物——enforcement 失败时沉默继续比直接报错更危险
    assert not (sim / "00_世界观" / "核心设定.md").exists(), \
        "git init 失败时不应继续生成产物"


def test_init_reports_hook_mount_failure_when_config_fails(tmp_path: Path, monkeypatch):
    """init 必须 write-then-verify：git config 失败时不能静默继续。"""
    sim = _setup_release_sandbox(tmp_path)
    subprocess.run(["git", "init", "-q"], cwd=str(sim), check=True)
    # 通过 stub 化 git，让 core.hooksPath 的写与复核返回 0 但输出垃圾——
    # 实际场景下用户改写 PATH / 仓库损坏了 git config，write 与 verify 不一致。
    # 这里我们用把 .git 改成普通文件来触发 write 失败。
    # （更稳妥的 monkeypatch 路径见下个测试——这里覆盖最坏场景）
    from pathlib import Path as _P
    # 模拟「git config 之后没生效」：删掉 .git/config 再触发写，
    # 让 enable_git_hooks 内部 verify 失败（write 写入但 .git/config 不存在）
    cfg = sim / ".git" / "config"
    # 把 config 替换成 directory，git config 会因路径冲突失败
    cfg.rename(cfg.with_suffix(".config-bak"))
    (sim / ".git" / "config").mkdir()
    try:
        r = _run_init(sim)
        # 即便 enable_git_hooks 写失败，cmd_init 必须把失败明面化
        assert "[FAIL] 钩子挂载失败" in r.stdout, \
            f"hook mount 失败必须明示（防 enforcement 裸奔）：stdout={r.stdout!r}"
        assert r.returncode != 0, \
            f"init 必须以非 0 退出：stdout={r.stdout!r}"
    finally:
        # 还原沙箱以利调试
        import shutil as _sh
        _sh.rmtree(sim / ".git" / "config", ignore_errors=True)
        cfg.with_suffix(".config-bak").rename(cfg)