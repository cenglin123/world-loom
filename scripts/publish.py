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
from layers import DIST_DIR, DIST_MAP, is_content  # noqa: E402

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
        encoding="utf-8", errors="replace",
    )
    return proc.stdout.strip() or None


def _apply_dist_map(env: dict) -> dict[str, str]:
    """把 `_分发/` 下的使用层文档映射到目标路径，再从树里移除 `_分发/` 本身。

    同一个 blob 映射多个文件名——单一源，天然同步，不存在漂移。
    返回 {目标路径: 来源路径}，供清单打印时说明每个文件从哪来。
    """
    mapped: dict[str, str] = {}
    for src, targets in DIST_MAP.items():
        sha = _git("rev-parse", f"HEAD:{src}", check=False).strip()
        if not sha:
            raise SystemExit(
                f"[FAIL] 分发源 {src} 不存在于 HEAD——使用层治理文档缺失，中止分发"
            )
        for tgt in targets:
            _git("update-index", "--add", "--cacheinfo", f"100644,{sha},{tgt}",
                 env=env)
            mapped[tgt] = src
    _git("rm", "--cached", "-r", "--quiet", "--ignore-unmatch", DIST_DIR, env=env)
    return mapped


# 分发时需要做的**源码层文本替换**——开发仓与下游用户侧行为不同的项。
# 单一源（dev）写明差异，publish.py 推送到下游时抹平。
# 每条：(文件, dev 文本, dist 文本, 用途说明)
DIST_TEXT_REWRITES: tuple[tuple[str, str, str, str], ...] = (
    # B-4：开发仓 check_all 把 check_hooks 当作「不应裸奔」的硬门（--strict）；
    # 下游用户场景可能未跑 init（无 .githooks/），应保持 SKIP 体验，故分发时
    # 把 --strict 替换成空。
    (
        "scripts/check_all.py",
        '["scripts/check_hooks.py", "--strict"]',
        '["scripts/check_hooks.py"]',
        "B-4：开发仓严格 / 下游宽松",
    ),
)


def _apply_dist_rewrites(env: dict) -> list[tuple[str, str]]:
    """按 DIST_TEXT_REWRITES 改写文件内容，再写回暂存区。

    返回 [(文件, 用途)]，供清单打印。

    处理：文件不在 HEAD（首次发版 / 文件被删）→ 跳过；dev 文本不在原 blob
    （上游已修过）→ 跳过；rewrite 后**不再** `update-index --remove`——
    `--remove` 会从工作区重读 blob 覆盖我们刚写入的 cacheinfo，让改写失效。
    `--add --cacheinfo` 本身已替换同名路径的 index 条目，无需 `--remove`。
    """
    import tempfile
    applied: list[tuple[str, str]] = []
    for path, dev_text, dist_text, purpose in DIST_TEXT_REWRITES:
        # 检查文件是否在 HEAD（_git 的 check=False 在 rev-parse 失败时仍返回 stdout echo）
        rev = subprocess.run(
            ["git", "-c", "core.quotepath=false", "rev-parse", f"HEAD:{path}"],
            cwd=ROOT, capture_output=True, text=True,
            encoding="utf-8", errors="replace",
        )
        if rev.returncode != 0 or not rev.stdout.strip():
            continue  # 文件不在 HEAD，跳过（首次发版 / 文件被删）
        sha = rev.stdout.strip()
        blob_proc = subprocess.run(
            ["git", "-c", "core.quotepath=false", "cat-file", "blob", sha],
            cwd=ROOT, capture_output=True, text=True,
            encoding="utf-8", errors="replace",
        )
        if blob_proc.returncode != 0:
            continue  # blob 拿不到（极少见：损坏的仓库），跳过
        blob = blob_proc.stdout
        if dev_text not in blob:
            continue  # dev 文本不在（可能上游已修过），跳过
        new = blob.replace(dev_text, dist_text, 1)
        with tempfile.NamedTemporaryFile("w", encoding="utf-8",
                                         newline=replace_placeholder,
                                         delete=False, suffix=".md") as tmp:
            tmp.write(new)
            tmp_path = tmp.name
        try:
            new_sha = _git("hash-object", "-w", "--path", path, tmp_path)
            _git("update-index", "--add", "--cacheinfo",
                 f"100644,{new_sha},{path}", env=env)
            # 注：不调 update-index --remove——它会从工作区重读 blob 覆盖
            # cacheinfo，让改写失效。--add --cacheinfo 已替换同名路径条目。
            applied.append((path, purpose))
        finally:
            os.unlink(tmp_path)
    return applied


# 用平台无关的换行符常量；publish 树里文本文件应统一 LF。
# 但我们改的是脚本源码（check_all.py），python 源码 LF 即可。
replace_placeholder = "\n"


def build_dist_tree() -> tuple[str, list[str], list[str], dict[str, str], list[tuple[str, str]]]:
    """返回 (tree_sha, 公开文件清单, 被排除的内容层清单, {目标: 来源}, 分发重写列表)。"""
    env = {"GIT_INDEX_FILE": PUBLISH_INDEX}
    _git("read-tree", "HEAD", env=env)

    all_files = [f for f in _git("ls-files", env=env).splitlines() if f]
    content = [f for f in all_files if is_content(f)]
    if content:
        # 分批喂给 git rm，避免 Windows 命令行长度上限
        for i in range(0, len(content), 200):
            _git("rm", "--cached", "-r", "--quiet", "--ignore-unmatch",
                 *content[i:i + 200], env=env)

    mapped = _apply_dist_map(env)
    rewrites = _apply_dist_rewrites(env)

    tree = _git("write-tree", env=env)
    published = [f for f in _git("ls-files", env=env).splitlines() if f]
    return tree, published, content, mapped, rewrites


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

    tree, published, excluded, mapped, rewrites = build_dist_tree()

    # —— 硬复核 1：树里绝不能有内容层/开发层文件 ——
    # 映射产生的路径豁免：它们的内容来自 _分发/（源码层），只是借用了内容层的路径名。
    leaked = [f for f in published if is_content(f) and f not in mapped]
    if leaked:
        print(f"[BLOCK] 分发树里仍有 {len(leaked)} 个内容层文件，已中止：")
        for f in leaked:
            print(f"    {f}")
        print("请检查 scripts/layers.py 的 CONTENT_PATTERNS。")
        return 1

    # —— 硬复核 2：`_分发/` 目录本身不能出现在分发树里 ——
    stray = [f for f in published if f.startswith(f"{DIST_DIR}/")]
    if stray:
        print(f"[BLOCK] 分发树里残留 {len(stray)} 个 {DIST_DIR}/ 文件，已中止：")
        for f in stray:
            print(f"    {f}")
        return 1

    print(f"将公开 {len(published)} 个源码层文件：")
    for f in published:
        tag = f"   ← 由 {mapped[f]} 映射" if f in mapped else ""
        print(f"  + {f}{tag}")
    if rewrites:
        print(f"\n分发时改写 {len(rewrites)} 个文件（dev/dist 行为差异）：")
        for path, purpose in rewrites:
            print(f"  ~ {path}  （{purpose}）")
    print(f"\n已排除 {len(excluded)} 个内容层/开发层文件（正文/角色/世界观填写/"
          f"开发规范等，一个都不会出去）")

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
