#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""模板分发——把**只含源码层**的快照推送到公开仓。

内容与源码同库同分支；`.githooks/pre-push` 默认拒绝一切推送，对外分发只能走
本脚本。流程：

    1. 以 HEAD 为基础建一个临时索引，删掉全部内容层路径（清单见 scripts/layers.py）
    2. write-tree → commit-tree，落到本地分发分支 `template-dist`
    3. **复核**该树里一个内容层文件都没有（layers.py verify-tree）
    4. 打印将要公开的完整文件清单，等确认
    5. --force 时才真正 push（带 NOVEL_PUBLISH=1 放行 pre-push）

用法：
    python scripts/publish.py                    # 预览：列出将公开的文件，不推送
    python scripts/publish.py --force            # 真的推送到 origin/main
    python scripts/publish.py --force --remote upstream --branch main
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from layers import is_content  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DIST_BRANCH = "template-dist"
PUBLISH_INDEX = ".git/publish-index"


def _git(*args: str, env: dict | None = None, check: bool = True) -> str:
    full_env = {**os.environ, **(env or {})}
    proc = subprocess.run(
        ["git", "-c", "core.quotepath=false", *args],
        cwd=str(ROOT), capture_output=True, text=True,
        encoding="utf-8", errors="replace", env=full_env,
    )
    if check and proc.returncode != 0:
        sys.stderr.write(proc.stdout + proc.stderr)
        raise SystemExit(f"[FAIL] git {' '.join(args)} 失败（{proc.returncode}）")
    return proc.stdout.strip()


def _rev(ref: str) -> str | None:
    proc = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", ref],
        cwd=str(ROOT), capture_output=True, text=True,
    )
    return proc.stdout.strip() or None


def build_dist_tree() -> tuple[str, list[str], list[str]]:
    """返回 (tree_sha, 公开文件清单, 被排除的内容层文件清单)。"""
    env = {"GIT_INDEX_FILE": PUBLISH_INDEX}
    _git("read-tree", "HEAD", env=env)

    all_files = [f for f in _git("ls-files", env=env).splitlines() if f]
    content = [f for f in all_files if is_content(f)]
    if content:
        # 分批喂给 git rm，避免 Windows 命令行长度上限
        for i in range(0, len(content), 200):
            _git("rm", "--cached", "-r", "--quiet", "--ignore-unmatch",
                 *content[i:i + 200], env=env)

    tree = _git("write-tree", env=env)
    published = [f for f in _git("ls-files", env=env).splitlines() if f]
    return tree, published, content


def main() -> int:
    ap = argparse.ArgumentParser(description="把只含源码层的快照推送到公开仓")
    ap.add_argument("--force", action="store_true", help="真正推送（否则只预览）")
    ap.add_argument("--remote", default="origin", help="目标远端，默认 origin")
    ap.add_argument("--branch", default="main", help="目标分支，默认 main")
    ap.add_argument("-m", "--message", default=None, help="分发提交信息")
    args = ap.parse_args()

    head = _rev("HEAD")
    if not head:
        print("[FAIL] 仓库没有提交，无从分发")
        return 1
    dirty = _git("status", "--porcelain")
    if dirty:
        print("[FAIL] 工作区有未提交改动——分发基于 HEAD，请先提交或暂存：")
        print("\n".join("    " + ln for ln in dirty.splitlines()[:15]))
        return 1

    tree, published, excluded = build_dist_tree()

    # —— 硬复核：树里绝不能有内容层文件 ——
    leaked = [f for f in published if is_content(f)]
    if leaked:
        print(f"[BLOCK] 分发树里仍有 {len(leaked)} 个内容层文件，已中止：")
        for f in leaked:
            print(f"    {f}")
        print("请检查 scripts/layers.py 的 CONTENT_PATTERNS。")
        return 1

    print(f"将公开 {len(published)} 个源码层文件：")
    for f in published:
        print(f"  + {f}")
    print(f"\n已排除 {len(excluded)} 个内容层文件（正文/角色/世界观填写等，一个都不会出去）")

    if not args.force:
        print("\n[DRY-RUN] 未创建提交、未推送。确认清单无误后加 --force 执行。")
        return 0

    parent = _rev(f"refs/heads/{DIST_BRANCH}")
    msg = args.message or f"chore(template): 分发源码层快照（源提交 {head[:12]}）"
    cmd = ["commit-tree", tree, "-m", msg]
    if parent:
        cmd += ["-p", parent]
    commit = _git(*cmd)
    _git("update-ref", f"refs/heads/{DIST_BRANCH}", commit)
    print(f"\n[OK] 分发提交 {commit[:12]} → {DIST_BRANCH}")

    _git("push", args.remote, f"{DIST_BRANCH}:{args.branch}",
         env={"NOVEL_PUBLISH": "1"})
    print(f"[OK] 已推送 {DIST_BRANCH} → {args.remote}/{args.branch}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
