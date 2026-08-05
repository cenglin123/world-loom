#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""用户侧更新——把当前副本的工具层升到新版，不碰创作内容。

适用场景：你用某个 release 版本写了一段时间，新版出了，想换工具不丢正文/设定。

核心安全：release 包由开发侧的 publish.py 剥过内容层，包里全是源码层文件——
覆盖这些路径天然不碰你的创作内容（00_世界观/核心设定.md、03_正文/章节、
docs/style-locked.md 等根本不在包里）。覆盖前还会全量备份到 .backup-<旧版本>/。

用法：
    python scripts/update.py <zip路径>     用本地 release 包升级
    python scripts/update.py <版本号>       自动从 GitHub 下载该版本（如 0.2.0）
    python scripts/update.py                查看当前/最新版本，提示是否升级

固有边界：如果新版改了某个模板的结构（如核心设定加了新段落），你已填的实例
不会自动长出来——脚本会检测并提示，但合并填写内容是人工判断，不自动做。
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import shutil
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from template import init_missing  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OWNER_REPO = "cenglin123/world-loom"
ASSET_TPL = "https://github.com/{}/releases/download/v{}/world-loom-v{}.zip"
API_LATEST = "https://api.github.com/repos/{}/releases/latest"

VERSION_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")


def parse_version(s: str) -> tuple[int, int, int]:
    m = VERSION_RE.match(s.strip().lstrip("v"))
    if not m:
        raise ValueError(f"版本号格式不对（应为 X.Y.Z）：{s}")
    return tuple(int(x) for x in m.groups())  # type: ignore[return-value]


def read_current_version() -> str:
    """读 ROOT/VERSION；无文件返回 '0.0'（0.1.0 之前的 release 无 VERSION 文件）。"""
    f = ROOT / "VERSION"
    if not f.is_file():
        return "0.0"
    try:
        return f.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeDecodeError):
        return "0.0"


def _http_get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "world-loom-update"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def fetch_latest() -> tuple[str, str] | None:
    """返回 (版本号, zip 下载 URL)；失败返回 None。"""
    try:
        info = json.loads(_http_get(API_LATEST.format(OWNER_REPO)).decode("utf-8"))
        tag = info.get("tag_name", "").lstrip("v")
        if not tag:
            return None
        assets = info.get("assets", [])
        url = next((a["browser_download_url"] for a in assets
                    if a.get("name", "").endswith(".zip")), "")
        if not url:  # 没挂 asset → 回退到 GitHub 自动 source code（带包裹目录）
            url = f"https://github.com/{OWNER_REPO}/archive/refs/tags/v{tag}.zip"
        return tag, url
    except Exception:
        return None


def download_version(version: str) -> bytes:
    try:
        return _http_get(ASSET_TPL.format(OWNER_REPO, version, version))
    except Exception as exc:
        raise SystemExit(
            f"[FAIL] 下载 v{version} 失败：{exc}\n"
            f"    手动从 https://github.com/{OWNER_REPO}/releases 下载 zip，"
            f"再跑 python scripts/update.py <zip路径>"
        )


def detect_prefix(names: list[str]) -> str:
    """GitHub Source code zip 带一层包裹目录，release.py 打的包没有。返回前缀（含尾 /）。"""
    KNOWN_ROOTS = {"scripts", "_模板", "_分发", "docs", ".githooks",
                   "example_world", ".github"}
    with_slash = [n for n in names if "/" in n]
    if not with_slash:
        return ""
    tops = {n.split("/", 1)[0] for n in with_slash}
    if len(tops) != 1:
        return ""
    top = tops.pop()
    if top in KNOWN_ROOTS or top.startswith(".git"):
        return ""
    if f"{top}/VERSION" in names or f"{top}/AGENTS.md" in names or f"{top}/scripts" in names:
        return top + "/"
    return ""


def extract(data: bytes) -> tuple[Path, str]:
    tmp = Path(tempfile.mkdtemp(prefix="wloom-update-"))
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        z.extractall(tmp)
        prefix = detect_prefix(z.namelist())
    return tmp, prefix


def read_zip_version(extract_root: Path, prefix: str) -> str:
    f = extract_root / f"{prefix}VERSION"
    if not f.is_file():
        raise SystemExit("[FAIL] 包里没有 VERSION 文件——这不是有效的 world-loom release 包")
    return f.read_text(encoding="utf-8").strip()


def do_update(extract_root: Path, prefix: str, new_ver: str, old_ver: str) -> int:
    src_root = extract_root / prefix
    rels = [p.relative_to(src_root) for p in src_root.rglob("*") if p.is_file()]

    backup_dir = ROOT / f".backup-{old_ver}"
    overwritten: list[str] = []
    new_files: list[str] = []

    # 先全量备份 + 覆盖
    for rel in rels:
        rel_posix = rel.as_posix()
        target = ROOT / rel
        src = src_root / rel
        if target.exists():
            b = backup_dir / rel
            b.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(target, b)
            if target.read_bytes() != src.read_bytes():
                overwritten.append(rel_posix)
        else:
            new_files.append(rel_posix)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, target)

    # 补新版新增的模板实例（已有不覆盖）
    created_tpl = init_missing()

    # 结构变更提示：对比备份的旧 _模板/ 与覆盖后的新 _模板/
    structural: list[str] = []
    for rel in rels:
        rel_posix = rel.as_posix()
        if not rel_posix.startswith("_模板/"):
            continue
        instance_rel = rel_posix[len("_模板/"):]
        old_tpl = backup_dir / "_模板" / instance_rel
        new_tpl = ROOT / "_模板" / instance_rel
        instance = ROOT / instance_rel
        if not (old_tpl.is_file() and instance.is_file()):
            continue
        try:
            if old_tpl.read_text(encoding="utf-8") != new_tpl.read_text(encoding="utf-8"):
                structural.append(instance_rel)
        except (OSError, UnicodeDecodeError):
            continue

    (ROOT / "VERSION").write_text(new_ver + "\n", encoding="utf-8", newline="\n")

    print(f"[OK] 已从 {old_ver if old_ver != '0.0' else '(0.1.0 前)'} 升级到 {new_ver}")
    if new_files:
        print(f"\n新增工具文件 {len(new_files)} 个：")
        for f in sorted(new_files)[:20]:
            print(f"  + {f}")
        if len(new_files) > 20:
            print(f"  … 还有 {len(new_files) - 20} 个")
    if overwritten:
        print(f"\n更新工具文件 {len(overwritten)} 个（旧版备份在 {backup_dir.name}/）")
    if created_tpl:
        print(f"\n补建的新模板 {len(created_tpl)} 个（已有未动）：")
        for c in created_tpl:
            print(f"  + {c}")
    if structural:
        print("\n[需手动] 以下模板结构有变，你的实例可能要对照 _模板/ 补填：")
        for s in structural:
            print(f"  ! {s}  →  对照 _模板/{s}")
        print("    （脚本不自动合并填写内容——这是人工判断）")
    print(f"\n旧版工具文件备份在 {backup_dir}/，确认升级无误后可删。")
    return 0


def resolve_data(target: str | None) -> bytes | None:
    """三种来源解析为 zip 字节；用户在交互分支取消时返回 None。"""
    if target is None:
        latest = fetch_latest()
        if latest is None:
            raise SystemExit(f"[FAIL] 无法查询 GitHub 最新版（网络？）。\n"
                             f"    手动查看 https://github.com/{OWNER_REPO}/releases，"
                             f"下载 zip 后跑 python scripts/update.py <zip路径>")
        tag, url = latest
        old_ver = read_current_version()
        print(f"最新版本：{tag}")
        if old_ver != "0.0":
            try:
                if parse_version(tag) <= parse_version(old_ver):
                    print("[OK] 已是最新，无需升级")
                    return None
            except ValueError:
                pass
        try:
            ans = input(f"升级到 {tag}？[y/N] ").strip().lower()
        except EOFError:
            print("[INFO] 非交互环境，已取消。带版本号重跑：python scripts/update.py "
                  f"{tag}")
            return None
        if ans != "y":
            print("已取消")
            return None
        print("下载中…")
        try:
            return _http_get(url)
        except Exception as exc:
            raise SystemExit(f"[FAIL] 下载失败：{exc}")

    if os.path.isfile(target):
        print(f"使用本地包：{target}")
        return Path(target).read_bytes()
    cleaned = target.strip().lstrip("v")
    if VERSION_RE.match(cleaned):
        print(f"从 GitHub 下载 v{cleaned}…")
        return download_version(cleaned)
    raise SystemExit(f"[FAIL] 无法识别参数：{target}（给 zip 路径或版本号如 0.2.0）")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="把当前副本的工具层升到新版，不碰创作内容")
    parser.add_argument("target", nargs="?",
                        help="release zip 路径或版本号；省略则查看最新版")
    args = parser.parse_args(argv)

    old_ver = read_current_version()
    print(f"当前版本：{old_ver if old_ver != '0.0' else '未知（0.1.0 前，无 VERSION 文件）'}")

    data = resolve_data(args.target)
    if data is None:
        return 0
    extract_root, prefix = extract(data)
    try:
        new_ver = read_zip_version(extract_root, prefix)
        if old_ver != "0.0":
            try:
                if parse_version(new_ver) < parse_version(old_ver):
                    print(f"[警告] 新版 {new_ver} 低于当前 {old_ver}——降级，"
                          f"仍继续（备份在 .backup-{old_ver}/）")
            except ValueError:
                pass
        return do_update(extract_root, prefix, new_ver, old_ver)
    finally:
        shutil.rmtree(extract_root, ignore_errors=True)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
