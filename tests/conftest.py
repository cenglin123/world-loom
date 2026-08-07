#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""publish / release 管线测试的公共基建。

运行：
    python -m pytest tests/ -v

设计要点（改这里之前先读）：

1. **为什么用沙箱**：`publish.py` / `release.py` 把 ROOT 硬编为
   `Path(__file__).parent.parent`，import 后直接调用会作用到真仓库。
   所以集成测试把被测脚本**拷进临时 git 仓**、以子进程方式运行。
2. **不触网**："远端"是本地 bare 仓库；`gh` 用替身（见 install_fake_gh）。
3. **环境隔离**：GIT_CONFIG_GLOBAL 指向空文件，隔离用户全局 git 配置
   （签名、全局 hooksPath 等）；沙箱内再显式设置本地 user/autocrlf/hooksPath。
4. **分层**：tests/ 本身在 scripts/layers.py 里划为开发层，不进分发树。
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

# 真仓库根目录与脚本目录；把 scripts/ 加进 sys.path，
# 让纯函数测试能 `from layers import ...` / `from update import ...`
REAL_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REAL_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

# 沙箱需要的被测脚本（release 依赖 publish，publish 依赖 layers）
PIPELINE_SCRIPTS = ("layers.py", "publish.py", "release.py")

# 空的 git 全局配置文件——隔离用户全局配置，保证沙箱行为确定
_EMPTY_GITCONFIG = Path(tempfile.gettempdir()) / "wloom-test-gitconfig-empty"
_EMPTY_GITCONFIG.write_text("", encoding="utf-8")


# ── 基础工具 ────────────────────────────────────────────────

def _clean_env(extra: dict | None = None) -> dict:
    """隔离全局 git 配置；extra 用于注入 PATH / FAKE_GH_LOG 等。

    PYTHONDONTWRITEBYTECODE 从源头不产生 __pycache__，避免弄脏沙箱工作区
    （真仓库靠 .gitignore 忽略，沙箱里双保险）。
    """
    env = {**os.environ,
           "GIT_CONFIG_GLOBAL": str(_EMPTY_GITCONFIG),
           "PYTHONDONTWRITEBYTECODE": "1"}
    if extra:
        env.update(extra)
    return env


def git(cwd: Path, *args: str, check: bool = True) -> str:
    """在 cwd 跑 git，返回去掉首尾空白的 stdout（UTF-8）。"""
    proc = subprocess.run(
        ["git", "-c", "core.quotepath=false", *args],
        cwd=str(cwd), capture_output=True, text=True,
        encoding="utf-8", errors="replace", env=_clean_env(),
    )
    if check and proc.returncode != 0:
        raise AssertionError(
            f"git {' '.join(args)} 失败（rc={proc.returncode}）:\n"
            f"{proc.stdout}\n{proc.stderr}")
    return proc.stdout.strip()


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


def run_script(repo: Path, script: str, *args: str,
               extra_env: dict | None = None) -> subprocess.CompletedProcess:
    """在沙箱里以子进程方式运行 scripts/<script>。"""
    return subprocess.run(
        [sys.executable, f"scripts/{script}", *args],
        cwd=str(repo), capture_output=True, text=True,
        encoding="utf-8", errors="replace", env=_clean_env(extra_env),
    )


# ── 沙箱仓库 ────────────────────────────────────────────────

def _init_repo(repo: Path) -> None:
    git(repo, "init", "-q")
    git(repo, "config", "user.email", "test@example.com")
    git(repo, "config", "user.name", "Test")
    git(repo, "config", "core.autocrlf", "false")
    git(repo, "config", "commit.gpgsign", "false")
    # 显式指向沙箱自己的（空）hooks 目录，屏蔽任何全局 hooksPath
    git(repo, "config", "core.hooksPath", str(repo / ".git" / "hooks"))


@pytest.fixture
def sandbox(tmp_path: Path) -> Path:
    """mimic 真仓库三层结构的临时 git 仓，已提交初始快照。

    内容/开发层（分发时必须被剥掉）：
        00_世界观/核心设定.md、03_正文/第1卷/第1章.md、docs/CURRENT.md、
        简介.md、AGENTS.md(开发版)、README.md(开发版)、scripts/release.py
    源码层（分发时保留）：
        scripts/layers.py、scripts/publish.py、VERSION、_模板/、_分发/、.gitignore

    _分发/ 里的使用版文档与开发版**故意不同**，便于断言分发树拿到的是使用版。
    """
    repo = tmp_path / "repo"
    (repo / "scripts").mkdir(parents=True)
    for name in PIPELINE_SCRIPTS:
        shutil.copyfile(SCRIPTS / name, repo / "scripts" / name)

    # 内容层 / 开发层
    _write(repo / "00_世界观" / "核心设定.md", "# 核心设定\n\n世界法则：测试法则。\n")
    _write(repo / "03_正文" / "第1卷" / "第1章.md",
           "---\nvolume: 1\nchapter: 1\nmodel: test-model\n---\n\n正文内容。\n")
    _write(repo / "docs" / "CURRENT.md", "# 当前任务\n")
    _write(repo / "简介.md", "这是一本书的简介。\n")
    _write(repo / "AGENTS.md", "开发版 AGENTS（不应被分发）\n")
    _write(repo / "README.md", "开发版 README（不应被分发）\n")

    # 源码层
    _write(repo / "VERSION", "0.1.0\n")
    _write(repo / "_模板" / "README.md", "模板说明\n")
    _write(repo / "_分发" / "AGENTS.md", "使用版 AGENTS\n")
    _write(repo / "_分发" / "README.md", "使用版 README\n")
    # /release 是 Windows 下 gh 替身的分发脚本（见 install_fake_gh），不入库；
    # __pycache__/*.pyc 与真仓库 .gitignore 一致
    _write(repo / ".gitignore", "/release\n__pycache__/\n*.pyc\n")

    _init_repo(repo)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "init")
    return repo


@pytest.fixture
def sandbox_with_remote(sandbox: Path, tmp_path: Path) -> tuple[Path, Path]:
    """沙箱 + 本地 bare 远端（origin）。返回 (repo, remote_git_dir)。"""
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "--bare", "-q", str(remote)],
                   check=True, capture_output=True, env=_clean_env())
    git(sandbox, "remote", "add", "origin", str(remote))
    return sandbox, remote


# ── gh 替身 ─────────────────────────────────────────────────

# Windows：subprocess.run(["gh", ...]) 走 CreateProcess 只认 .exe（.cmd 会被
# 跳过，实测会命中真 gh）。所以把 python.exe 拷成 gh.exe——
#   `gh release create ...` → `python.exe release create ...`
# 会执行 cwd 下名为 release 的分发脚本，由它记录 argv。
# `gh --version` 由 python 自身短路（打印 Python 版本、退出 0）。
_FAKE_GH_DISPATCHER = (
    "import os, sys\n"
    "with open(os.environ['FAKE_GH_LOG'], 'a', encoding='utf-8') as f:\n"
    "    f.write('\\t'.join(sys.argv) + '\\n')\n"
)

# POSIX：gh 直接是个 shell 脚本，参数原样落日志
_FAKE_GH_POSIX = (
    "#!/bin/sh\n"
    "printf '%s\\t' \"$@\" >> \"$FAKE_GH_LOG\"\n"
    "printf '\\n' >> \"$FAKE_GH_LOG\"\n"
    "exit 0\n"
)


def install_fake_gh(repo: Path, tmp_path: Path) -> tuple[dict, Path]:
    """造一个 gh 替身并返回 (额外环境变量, 调用日志路径)。

    日志每行是一次 gh 调用的 argv，tab 分隔。
    """
    stub = tmp_path / "gh-stub"
    stub.mkdir(exist_ok=True)
    log = tmp_path / "gh_calls.log"
    if os.name == "nt":
        shutil.copyfile(sys.executable, stub / "gh.exe")
        _write(repo / "release", _FAKE_GH_DISPATCHER)  # 已被沙箱 .gitignore 忽略
    else:
        gh = stub / "gh"
        gh.write_text(_FAKE_GH_POSIX, encoding="utf-8", newline="\n")
        gh.chmod(0o755)
    env = {"PATH": f"{stub}{os.pathsep}{os.environ['PATH']}",
           "FAKE_GH_LOG": str(log)}
    return env, log


# ── 慢测试机制 ─────────────────────────────────────────────

# slow 测试（需联网/重资源）默认跳过，加 --runslow 启用。
# 守护的是「跨版本自举」等关键回归——不该每次完工必检都跑，
# 但发版前/重构 update.py 后值得显式跑一遍。

def pytest_addoption(parser):
    parser.addoption(
        "--runslow", action="store_true", default=False,
        help="运行标记为 slow 的测试（默认跳过；含跨版本 update 回归）",
    )


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (use --runslow to run)"
    )


def pytest_collection_modifyitems(config, items):
    if config.getoption("--runslow"):
        return
    skip_slow = pytest.mark.skip(reason="slow test, use --runslow to enable")
    for item in items:
        if "slow" in item.keywords:
            item.add_marker(skip_slow)
