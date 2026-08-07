#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""跨版本自举回归测试——守护「旧版 update.py 能应用新版 zip」这条隐性承诺。

v0.2.0 release notes 明确写过「从 v0.2.0 起自举——之后的更新用 update.py」。
本测试把这个承诺固化下来：从 v0.2.0 的源码提交（852ef74，VERSION=0.2.0 在
那里写入）提取旧版 update.py / template.py，下载最新发布的 zip，让旧
update.py 去跑，断言关键不变量——任何人将来重构 update.py / template.py
的 importlib.reload 逻辑，都会立刻被这条测试抓住。

慢测试：需联网下载最新 release zip（默认 gh 已认证）。默认跳过，
加 --runslow 启用。
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from conftest import REAL_ROOT, SCRIPTS
from update import parse_version

# v0.2.0 的真实 release commit——VERSION=0.2.0 在这里写入并打 tag。
# 选 v0.2.0 作「老版」是因为它是首个带 update.py 的 release。
V0200_SRC_REF = "852ef74"


def _git_show_blob(ref: str, path: str) -> str:
    r = subprocess.run(
        ["git", "show", f"{ref}:{path}"],
        cwd=str(REAL_ROOT), capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )
    if r.returncode != 0:
        pytest.skip(f"无法读取 {ref}:{path}（ref 不存在？）")
    return r.stdout


@pytest.mark.slow
def test_v0200_update_can_apply_latest_zip(tmp_path: Path):
    sim = tmp_path / "olduser"
    sim.mkdir()

    # 1. 从 v0.2.0 源码提交还原「老用户」：VERSION + update.py + template.py
    old_ver = _git_show_blob(V0200_SRC_REF, "VERSION").strip()
    (sim / "VERSION").write_text(old_ver + "\n", encoding="utf-8", newline="\n")

    scripts_dir = sim / "scripts"
    scripts_dir.mkdir()
    (scripts_dir / "update.py").write_text(
        _git_show_blob(V0200_SRC_REF, "scripts/update.py"),
        encoding="utf-8", newline="\n",
    )
    # 同步放旧 template.py，让 _post_update_init 走 importlib.reload 分支
    # （更贴近真实用户场景——更新时 template 已在内存）
    (scripts_dir / "template.py").write_text(
        _git_show_blob(V0200_SRC_REF, "scripts/template.py"),
        encoding="utf-8", newline="\n",
    )

    # 用户已有内容层文件——升级后必须保留（content-layer 不在合法分发里）
    user_content = (
        "USER-MARKER: 这是用户的核心设定，不应被覆盖——"
        "DISTINCTIVE-MARKER-A1B2C3\n"
    )
    (sim / "00_世界观").mkdir(parents=True)
    (sim / "00_世界观" / "核心设定.md").write_text(
        user_content, encoding="utf-8", newline="\n",
    )

    # 2. 确定目标 release zip
    candidate = os.environ.get("WL_UPDATE_CANDIDATE_ZIP")
    if candidate:
        zip_path = Path(candidate)
        if not zip_path.is_file():
            raise RuntimeError(
                f"WL_UPDATE_CANDIDATE_ZIP={candidate} 不存在或不是文件"
            )
    else:
        # 下载最新 release zip（gh release download 无 tag = latest）
        r = subprocess.run(
            ["gh", "release", "download", "-D", str(sim),
             "--pattern", "world-loom-v*.zip"],
            capture_output=True, text=True, encoding="utf-8", errors="replace"
        )
        if r.returncode != 0:
            pytest.skip(
                "下载最新 release zip 失败："
                + (r.stderr.strip() or r.stdout.strip() or "gh 未认证或无 release")
            )

        zips = sorted(sim.glob("world-loom-v*.zip"))
        if not zips:
            pytest.skip("未在最新 release 中找到 zip asset")
        zip_path = zips[-1]  # 文件名排序后取最大 = 最新版本号


    # 从 zip 里读 VERSION 与 update.py，供后续字节比较
    with zipfile.ZipFile(zip_path) as z:
        zip_ver = z.read("VERSION").decode("utf-8").strip()
        zip_update_py = z.read("scripts/update.py")

    # 3. 用旧版 update.py 升级
    env = {**os.environ,
           "PYTHONDONTWRITEBYTECODE": "1",
           "PYTHONIOENCODING": "utf-8"}
    r = subprocess.run(
        [sys.executable, "scripts/update.py", str(zip_path)],
        cwd=str(sim), capture_output=True, text=True,
        encoding="utf-8", errors="replace", env=env,
    )
    assert r.returncode == 0, (
        f"update.py 失败（rc={r.returncode}）:\n{r.stdout}\n--- stderr ---\n{r.stderr}"
    )

    # 4. 关键不变量——这五条全过 = 自举机制没坏 + 内容层保护生效
    new_ver = (sim / "VERSION").read_text(encoding="utf-8").strip()
    assert new_ver == zip_ver, (
        f"VERSION 应等于 zip 内版本 {zip_ver!r}，实为 {new_ver!r}"
    )
    assert parse_version(new_ver) > parse_version(old_ver), (
        f"新版本 {new_ver} 不大于旧版本 {old_ver}——升级未生效"
    )

    backup = sim / f".backup-{old_ver}"
    assert backup.is_dir(), f"未创建备份目录 {backup}"

    # _分发/ 不应出现：publish 已剥，update.py 不应再产生它
    assert not (sim / "_分发").exists(), (
        "_分发/ 残留（publish 已剥，update.py 不应再产生它）"
    )

    # 用户内容层文件必须保留——publish.py 应不把内容层放进 zip
    assert (sim / "00_世界观" / "核心设定.md").read_text(
        encoding="utf-8"
    ) == user_content, (
        "用户的 00_世界观/核心设定.md 被覆盖——publish.py 漏剥或 update.py"
        "第二道闸门失效"
    )

    # D1 自举：sim/scripts/update.py 必须被 zip 内的新版 update.py 字节级覆盖
    sandbox_update_py = (sim / "scripts" / "update.py").read_bytes()
    assert sandbox_update_py == zip_update_py, (
        "scripts/update.py 未被 zip 覆盖——D1 自举失败"
    )


@pytest.mark.slow
def test_update_rejects_content_layer_in_zip(tmp_path: Path):
    """投毒测试：含内容层文件的 zip 必须被 fail-closed 拒绝。

    模拟 publish.py 漏剥 / 包被篡改：合法 VERSION + 恶意覆盖用户的内容层文件。
    第二道闸门（update.py 的 is_content 复核）必须阻止覆盖、保留用户内容。
    """
    sim = tmp_path / "user"
    sim.mkdir()

    # 用户已有内容层文件
    user_content = (
        "USER-CONTROL-001: 用户创作内容——不可被覆盖\n"
    )
    (sim / "00_世界观").mkdir(parents=True)
    (sim / "00_世界观" / "核心设定.md").write_text(
        user_content, encoding="utf-8", newline="\n",
    )

    # 把 update.py + layers.py 放进去（layers 是 update.py 的依赖）
    (sim / "scripts").mkdir()
    shutil.copyfile(SCRIPTS / "layers.py", sim / "scripts" / "layers.py")
    shutil.copyfile(SCRIPTS / "update.py", sim / "scripts" / "update.py")
    (sim / "VERSION").write_text("0.1.0\n", encoding="utf-8", newline="\n")

    # 构造「被投毒」的 zip：合法 VERSION + 恶意内容层文件
    poison_zip = tmp_path / "poison.zip"
    with zipfile.ZipFile(poison_zip, "w") as z:
        z.writestr("VERSION", "9.9.9\n")
        z.writestr("scripts/update.py", "# poisoned update.py (should never run)\n")
        z.writestr("00_世界观/核心设定.md", "POISONED CONTENT — MUST NOT REACH USER\n")

    env = {**os.environ,
           "PYTHONDONTWRITEBYTECODE": "1",
           "PYTHONIOENCODING": "utf-8"}
    r = subprocess.run(
        [sys.executable, "scripts/update.py", str(poison_zip)],
        cwd=str(sim), capture_output=True, text=True,
        encoding="utf-8", errors="replace", env=env,
    )

    # fail-closed：拒绝含内容层的 zip
    assert r.returncode != 0, (
        f"update.py 应拒绝含内容层的 zip 但成功（rc={r.returncode}）:\n"
        f"{r.stdout}\n--- stderr ---\n{r.stderr}"
    )

    # 用户内容必须保留——第二道闸门在覆盖之前阻断
    assert (sim / "00_世界观" / "核心设定.md").read_text(
        encoding="utf-8"
    ) == user_content, (
        "用户内容层文件被覆盖——第二道闸门失效"
    )