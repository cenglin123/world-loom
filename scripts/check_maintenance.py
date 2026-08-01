#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""维护待办检测——把"记得回写"从 agent 的记忆里搬进脚本。

写完一章之后要做的维护工作（记忆回写 / 关系更新 / 演化记载 / 场景清单对齐）
原先全靠主 agent 记得。本脚本把这些**结构性信号**检测出来，让主 agent 只需
派发和验收，不必兼任盯梢。

设计边界（三分判据）：
    ① 机制不执行任务本身——只检测缺失，不代写记忆/关系/演化
    ② 不收窄编排空间——"是否真的需要更新"仍由 agent 判断
    ③ 契约违反 fail-closed，判断分歧 fail-open
       结构性缺失（记忆没回写）阻断；语义判断（演化算不算发生）只提醒

豁免：章节 frontmatter 声明
    maintenance_skip: [memory, evolution, relations, scenelist]
带上理由写在 maintenance_skip_reason，脚本认标记放行。

CLI：
    python scripts/check_maintenance.py           # 全仓：结构缺失即阻断（完工必检）
    python scripts/check_maintenance.py --staged  # 暂存区：全部降级为提醒（hook 用）
    python scripts/check_maintenance.py --chapter <路径>   # 只查单章
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEXT_DIR = ROOT / "03_正文"
WORK_DIR = "_工作"          # 各卷的过程文件子目录，与 check_chapters.py 一致
CHAR_DIR = ROOT / "02_人物"
OUTLINE_DIR = ROOT / "01_大纲"
REL_JSON = CHAR_DIR / "relationships.json"

NON_CHARACTER = {"_索引", "人物模板", "README", "relationships"}

SKIP_KEYS = {"memory", "evolution", "relations", "scenelist"}


# ---------- 基础工具 ----------

def _git(*args: str) -> str:
    proc = subprocess.run(
        ["git", "-c", "core.quotepath=false", *args],
        cwd=str(ROOT), capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )
    return proc.stdout if proc.returncode == 0 else ""


def _staged_files() -> set[str]:
    return {ln for ln in _git("diff", "--cached", "--name-only").splitlines() if ln}


def _last_commit_ts(path: str) -> int:
    """文件最后一次提交的时间戳；未入库返回 0。"""
    out = _git("log", "-1", "--format=%ct", "--", path).strip()
    return int(out) if out.isdigit() else 0


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def _frontmatter(text: str) -> dict[str, str]:
    """极简 frontmatter 解析——只取 key: value 与 key: [a, b] 形式。"""
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    fm: dict[str, str] = {}
    for line in text[3:end].splitlines():
        m = re.match(r"^([A-Za-z_][\w-]*)\s*:\s*(.*)$", line)
        if m:
            fm[m.group(1)] = m.group(2).strip()
    return fm


def _list_field(raw: str) -> list[str]:
    """解析 `[a, b]` 或 `a, b` 为列表。"""
    raw = raw.strip().strip("[]")
    return [x.strip().strip("\"'") for x in raw.split(",") if x.strip()]


def _chapters() -> list[Path]:
    if not TEXT_DIR.is_dir():
        return []
    return sorted(
        p for p in TEXT_DIR.rglob("第*章.md")
        if not p.name.startswith("_")
    )


def _known_characters() -> set[str]:
    if not CHAR_DIR.is_dir():
        return set()
    return {
        p.stem for p in CHAR_DIR.glob("*.md")
        if p.stem not in NON_CHARACTER
    }


def _rel_key(a: str, b: str) -> str:
    return ":".join(sorted([a, b]))


def _relation_pairs() -> set[str]:
    if not REL_JSON.is_file():
        return set()
    try:
        data = json.loads(_read(REL_JSON) or "{}")
    except json.JSONDecodeError:
        return set()
    return set(data.get("pairs", {}).keys())


# ---------- 各项检测 ----------

def _check_memory(ch: Path, chars: list[str], staged: set[str] | None) -> list[str]:
    """在场角色的人物卡是否随本章更新过。"""
    issues = []
    ch_rel = ch.relative_to(ROOT).as_posix()
    for name in chars:
        card = CHAR_DIR / f"{name}.md"
        if not card.is_file():
            issues.append(f"{ch.name}: 在场角色「{name}」没有人物卡")
            continue
        card_rel = card.relative_to(ROOT).as_posix()
        if staged is not None:
            # 暂存区模式：本章在暂存区而角色卡不在 → 疑似漏回写
            if ch_rel in staged and card_rel not in staged:
                issues.append(f"{ch.name}: 「{name}」的人物卡未随本次提交更新")
        else:
            # 全仓模式：角色卡的最后提交早于本章 → 记忆没跟上
            if _last_commit_ts(card_rel) < _last_commit_ts(ch_rel):
                issues.append(f"{ch.name}: 「{name}」的人物卡早于本章，L2 记忆未回写")
    return issues


def _check_evolution(ch: Path, chars: list[str]) -> list[str]:
    """写前准备包里有被动场景决定 → 提醒检查演化记录。"""
    prep = ch.parent / WORK_DIR / f"_准备_{ch.stem}.md"
    if not prep.is_file():
        return []
    body = _read(prep)
    if "被动场景" not in body:
        return []
    # 决定字段非空即为信号
    m = re.search(r"[*\-\s]*\*\*决定\*\*\s*[：:]\s*(.+)", body)
    if not m or not m.group(1).strip():
        return []
    return [
        f"{ch.name}: 写前准备包有被动场景决定「{m.group(1).strip()[:30]}」"
        f"——确认 {'/'.join(chars) or '在场角色'} 的演化记录是否需要追加"
    ]


def _check_relations(ch: Path, chars: list[str], pairs: set[str]) -> list[str]:
    issues = []
    for i, a in enumerate(chars):
        for b in chars[i + 1:]:
            if _rel_key(a, b) not in pairs:
                issues.append(
                    f"{ch.name}: 「{a}」与「{b}」同场但关系 JSON 无此对"
                    f"——python scripts/relationship.py set {a} {b} ..."
                )
    return issues


def _check_scenelist(ch: Path) -> list[str]:
    """本章是否在分卷大纲的场景清单里有对应行。"""
    if not OUTLINE_DIR.is_dir():
        return []
    outlines = list(OUTLINE_DIR.glob("第*卷_大纲.md")) + [OUTLINE_DIR / "主线.md"]
    stem = ch.stem  # 第M章
    for o in outlines:
        if o.is_file() and stem in _read(o):
            return []
    return [f"{ch.name}: 在分卷大纲的场景清单中找不到对应行"]


# ---------- 主流程 ----------

def run(staged_mode: bool, only: Path | None) -> int:
    staged = _staged_files() if staged_mode else None
    chapters = [only] if only else _chapters()
    if not chapters:
        return 0

    known = _known_characters()
    pairs = _relation_pairs()

    blocks: list[str] = []
    reminds: list[str] = []

    for ch in chapters:
        text = _read(ch)
        fm = _frontmatter(text)
        if fm.get("author", "").strip() == "human":
            continue

        skip = set(_list_field(fm.get("maintenance_skip", "")))
        unknown = skip - SKIP_KEYS
        if unknown:
            reminds.append(
                f"{ch.name}: maintenance_skip 含未知项 {sorted(unknown)}"
                f"（可用：{sorted(SKIP_KEYS)}）"
            )

        chars = [c for c in _list_field(fm.get("characters_present", "")) if c]
        chars = [c for c in chars if c in known] or chars

        if "memory" not in skip:
            found = _check_memory(ch, chars, staged)
            (reminds if staged_mode else blocks).extend(found)
        if "evolution" not in skip:
            reminds.extend(_check_evolution(ch, chars))
        if "relations" not in skip:
            reminds.extend(_check_relations(ch, chars, pairs))
        if "scenelist" not in skip:
            reminds.extend(_check_scenelist(ch))

    if blocks:
        print("[BLOCK] 维护待办未完成：")
        for b in blocks:
            print(f"    {b}")
        print("")
        print("  派发维护子代理处理，模板见 05_复盘/maintenance-executor.md")
        print("  确认确实不需要 → 章节 frontmatter 加 maintenance_skip: [memory] + 理由")
    if reminds:
        if blocks:
            print("")
        print("[REMINDER] 建议确认（不阻断）：")
        for r in reminds:
            print(f"    {r}")

    if not blocks and not reminds:
        print(f"[PASS] {len(chapters)} 章维护状态正常")
    return 1 if blocks else 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="章节维护待办检测")
    ap.add_argument("--staged", action="store_true",
                    help="只看暂存区，且全部降级为提醒（pre-commit 用）")
    ap.add_argument("--chapter", type=str, default=None,
                    help="只检查指定章节文件")
    args = ap.parse_args(argv)

    only = None
    if args.chapter:
        only = (ROOT / args.chapter).resolve()
        if not only.is_file():
            print(f"[FAIL] 找不到章节：{args.chapter}")
            return 1
    return run(args.staged, only)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main(sys.argv[1:]))
