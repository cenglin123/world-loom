#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""开发侧发版——打 GitHub release（含 zip asset）。

仅开发仓用，不分发（layers.py 把本文件划入内容层）。

发版是一次端到端的对外发布。本脚本串起四步：
  A. 写 VERSION 并提交
  B. publish.py --force  → 把含新 VERSION 的分发树推到 origin/main
  C. git archive template-dist → 打 zip（template-dist 已是最新分发快照）
  D. gh release create → 挂 zip 到 GitHub release，tag 指向 template-dist
     （--target template-dist 让 tag 落在分发 commit 上，GitHub 自动 Source code 才干净）

release notes 是诚实说明（已知边界、方法论来源等判断），由人准备 --notes-file，
脚本不自动生成。

用法：
    python scripts/release.py 0.2.0 --notes-file <草稿>
    python scripts/release.py 0.2.0 --notes-file <草稿> --skip-checks  # 跳过 check_all
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OWNER_REPO = "cenglin123/world-loom"
VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")


def _run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    kw.setdefault("cwd", ROOT)
    kw.setdefault("capture_output", True)
    kw.setdefault("text", True)
    kw.setdefault("encoding", "utf-8")
    kw.setdefault("errors", "replace")
    return subprocess.run(cmd, **kw)


def stage_preflight(skip_checks: bool) -> int | None:
    st = _run(["git", "status", "--porcelain"])
    if st.stdout.strip():
        print("[FAIL] 工作区不干净，先提交或暂存：")
        print(st.stdout)
        return 1
    if not skip_checks:
        chk = _run([sys.executable, "scripts/check_all.py", "--quiet", "--runslow"])
        out = (chk.stdout + chk.stderr).strip()
        if out:
            print("[FAIL] check_all 有输出（章节 FAIL 在未写作仓正常，其它项请修复）：")
            print(out)
            print("    确认仅章节 FAIL，可重跑加 --skip-checks")
            return 1
    if _run(["gh", "--version"]).returncode != 0:
        print("[FAIL] 找不到 gh CLI：https://cli.github.com/")
        return 1
    print("[OK] 前置检查通过")
    return None


def stage_commit(version: str) -> int | None:
    (ROOT / "VERSION").write_text(version + "\n", encoding="utf-8", newline="\n")
    _run(["git", "add", "VERSION"])
    r = _run(["git", "commit", "-m", f"release: v{version}"])
    if r.returncode != 0:
        # 续跑：VERSION 可能已是该版本并已提交（发版中断后重跑）
        if _run(["git", "show", f"HEAD:VERSION"]).stdout.strip() == version:
            print(f"[OK] 阶段 A：VERSION={version} 已在 HEAD（续跑跳过）")
            return None
        print("[FAIL] VERSION 提交失败：")
        print(r.stdout + r.stderr)
        return 1
    print(f"[OK] 阶段 A：VERSION={version} 已提交")
    return None


def stage_publish() -> int | None:
    print("[..] 阶段 B：publish.py --force（更新 origin/main）…")
    r = subprocess.run([sys.executable, "scripts/publish.py", "--force"],
                       cwd=ROOT, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        print("[FAIL] publish 失败（VERSION 已提交，修复后重跑会跳过已变更项）")
        return 1
    print("[OK] 阶段 B 完成")
    return None


def stage_archive(version: str, zip_path: Path) -> int | None:
    r = _run(["git", "archive", "--format=zip", "-o", str(zip_path), "template-dist"])
    if r.returncode != 0:
        print("[FAIL] 打 zip 失败：")
        print(r.stderr)
        return 1
    print(f"[OK] 阶段 C：{zip_path.name}（{zip_path.stat().st_size} 字节）")
    return None


def stage_release(version: str, zip_path: Path, notes_file: Path) -> int | None:
    # tag 落在 template-dist 指向的分发 commit（阶段 B 已推到 origin/main）。
    # 用 SHA 而非分支名：远端没有 template-dist 分支（publish 推到 main），
    # gh 用分支名会 422 target_commitish invalid。
    target = _run(["git", "rev-parse", "template-dist"]).stdout.strip() or "main"
    r = _run([
        "gh", "release", "create", f"v{version}",
        str(zip_path),
        "--target", target,
        "--title", f"world-loom v{version}",
        "--notes-file", str(notes_file.resolve()),
        "--latest",
    ])
    if r.returncode != 0:
        print("[FAIL] gh release create 失败：")
        print(r.stdout + r.stderr)
        print(f"    zip 还在 {zip_path}，可手动重试 gh 命令")
        return 1
    print(f"[OK] 阶段 D：release v{version} 已发布")
    return None


def stage_validate_candidate(zip_path: Path) -> int | None:
    """用 v0.2.0 的 update.py 验证本次候选 zip 能正确应用。

    比 stage_archive 晚、比 stage_release 早——必须通过才能进 release。
    不可跳过：--skip-checks 不影响此 stage（E4 / E5：候选 zip 验证是
    release.py 的独立闸门，不在 check_all 内）。

    沙箱/裸环境里 tests/ 不存在时跳过——与 check_tests.py 策略一致，
    真实发版场景下 tests/ 必然存在（它在仓库里且 release.py 从仓库根跑）。
    """
    candidate_test = ROOT / "tests" / "test_update_cross_version.py"
    if not candidate_test.is_file():
        print(f"[SKIP] 阶段 C-2：{candidate_test} 不存在，跳过候选 zip 验证"
              f"（开发仓发版时该文件必然存在——否则是仓库结构异常）")
        return None
    print("[..] 阶段 C-2：用 v0.2.0 update.py 验证候选 zip…")
    env = {**os.environ, "WL_UPDATE_CANDIDATE_ZIP": str(zip_path)}
    r = subprocess.run(
        [sys.executable, "-m", "pytest",
         "tests/test_update_cross_version.py::test_v0200_update_can_apply_latest_zip",
         "--runslow", "-v", "--tb=short", "-p", "no:cacheprovider"],
        cwd=ROOT, capture_output=True, text=True,
        encoding="utf-8", errors="replace", env=env,
    )
    if r.returncode != 0:
        print("[FAIL] 候选 zip 跨版本回归未通过——中止发版")
        print((r.stdout + r.stderr).strip())
        return 1
    print("[OK] 候选 zip 经 v0.2.0 update.py 应用成功——可发版")
    return None


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="打 GitHub release（开发侧，不分发）")
    p.add_argument("version", help="版本号 X.Y.Z（须大于 0.1.0）")
    p.add_argument("--notes-file", required=True,
                   help="release notes 文件（诚实说明，人工准备）")
    p.add_argument("--skip-checks", action="store_true",
                   help="跳过 check_all（确认仅章节 FAIL 时用）")
    args = p.parse_args(argv)

    if not VERSION_RE.match(args.version):
        sys.exit(f"[FAIL] 版本号格式不对（X.Y.Z）：{args.version}")
    notes = Path(args.notes_file)
    if not notes.is_file():
        sys.exit(f"[FAIL] notes 文件不存在：{notes}")

    print(f"发版 v{args.version}：前置 → 提交 VERSION → publish → archive → release\n")
    for name, fn in (
        ("前置检查", lambda: stage_preflight(args.skip_checks)),
        ("提交 VERSION", lambda: stage_commit(args.version)),
        ("publish", lambda: stage_publish()),
    ):
        if (rc := fn()) is not None:
            return rc

    zip_path = Path(tempfile.gettempdir()) / f"world-loom-v{args.version}.zip"
    if (rc := stage_archive(args.version, zip_path)) is not None:
        return rc
    if (rc := stage_validate_candidate(zip_path)) is not None:
        return rc
    if (rc := stage_release(args.version, zip_path, notes)) is not None:
        return rc

    zip_path.unlink(missing_ok=True)
    print(f"\n完成：https://github.com/{OWNER_REPO}/releases/tag/v{args.version}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
