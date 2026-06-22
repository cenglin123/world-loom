#!/usr/bin/env python
"""章节 + 人物时空一致性校验。
检查项：
  - 章节 frontmatter 字段完整性
  - characters_present 引用的角色都在 02_人物/ 下有文件
  - status=dead 的角色不出现在 characters_present 中
  - 同一 in_world_date 下角色不出现于两个不同 location
  - 就绪自检：世界观/大纲/人物非空才能提交正文
用法: python scripts/check_chapters.py [--staged] [--readiness]
"""

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHAR_DIR = ROOT / "02_人物"
TEXT_DIR = ROOT / "03_正文"
WORLD_FILE = ROOT / "00_世界观" / "核心设定.md"
OUTLINE_FILE = ROOT / "01_大纲" / "主线.md"
INDEX_FILE = CHAR_DIR / "_索引.md"

# ── helpers ──────────────────────────────────────────────

def _parse_frontmatter(path: Path) -> dict | None:
    """解析 markdown 文件 YAML frontmatter。"""
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return None
    end = text.find("---", 3)
    if end == -1:
        return None
    raw = text[3:end].strip()
    fm = {}
    for line in raw.split("\n"):
        line = line.strip()
        if ":" in line and not line.startswith("#"):
            key, _, val = line.partition(":")
            fm[key.strip()] = val.strip()
    return fm

def _list_character_files() -> dict[str, Path]:
    """返回 {角色名: 文件路径}，排除模板和索引。"""
    chars = {}
    for f in CHAR_DIR.glob("*.md"):
        name = f.stem
        if name in ("_索引", "人物模板", "README"):
            continue
        chars[name] = f
    return chars

def _parse_characters_present(raw: str | list | None) -> list[str]:
    """解析 characters_present：YAML 列表字符串或已解析的 list。"""
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(c).strip() for c in raw if str(c).strip()]
    # YAML 字符串: "['沈照影', '顾寒枝']" 或 "沈照影, 顾寒枝"
    s = raw.strip().strip("'\"")
    if s.startswith("[") and s.endswith("]"):
        s = s[1:-1]
    return [c.strip().strip("'\"") for c in s.split(",") if c.strip()]

# ── checks ────────────────────────────────────────────────

def check_readiness(issues: list):
    """H1: 就绪自检——世界观/大纲/人物非空才允许提交正文。"""
    # 检查世界观
    if WORLD_FILE.exists():
        text = WORLD_FILE.read_text(encoding="utf-8")
        if "待填写" in text[text.find("## 世界法则"):text.find("## 善恶观") if "## 善恶观" in text else len(text)] if "## 世界法则" in text else True:
            issues.append("[H1-BLOCK] 世界观/核心设定.md 世界法则段仍为'待填写'")
    else:
        issues.append("[H1-BLOCK] 世界观/核心设定.md 不存在")

    # 检查大纲主线
    if OUTLINE_FILE.exists():
        text = OUTLINE_FILE.read_text(encoding="utf-8")
        m = re.search(r"## 主线（一句话）\n\n(.*?)\n", text)
        if m and ("待填写" in m.group(1) or not m.group(1).strip()):
            issues.append("[H1-BLOCK] 大纲/主线.md 主线一句话仍为'待填写'")
    else:
        issues.append("[H1-BLOCK] 大纲/主线.md 不存在")

    # 检查至少一个角色
    chars = _list_character_files()
    if not chars:
        issues.append("[H1-BLOCK] 02_人物/ 下无任何实际角色文件（仅有模板/索引）")

def check_chapters(chapter_files: list[Path], issues: list):
    """D3: 章节 frontmatter 完整性 + 时空一致性。"""
    chars = _list_character_files()
    # 构建角色 status 映射
    char_status = {}
    for name, fpath in chars.items():
        fm = _parse_frontmatter(fpath)
        if fm:
            char_status[name] = fm.get("status", "alive")

    # {in_world_date: {角色: location}}
    spacetime: dict[str, dict[str, str]] = defaultdict(dict)

    for cf in sorted(chapter_files):
        fm = _parse_frontmatter(cf)
        if fm is None:
            issues.append(f"[WARN] {cf.relative_to(ROOT)}: 缺少 YAML frontmatter")
            continue

        # 必填字段
        for field in ("volume", "chapter", "characters_present", "location"):
            if field not in fm or not fm[field]:
                issues.append(f"[WARN] {cf.relative_to(ROOT)}: 缺少必填字段 '{field}'")
        if "word_count" not in fm:
            issues.append(f"[INFO] {cf.relative_to(ROOT)}: 建议填写 word_count")

        # 解析出场角色
        present = _parse_characters_present(fm.get("characters_present"))
        if not present:
            continue

        # 检查角色是否存在
        for c in present:
            if c not in chars:
                issues.append(f"[WARN] {cf.relative_to(ROOT)}: characters_present 引用 '{c}'，但无对应角色文件")

        # 死角色复活检测
        for c in present:
            if c in char_status and char_status[c] == "dead":
                issues.append(f"[BLOCK] {cf.relative_to(ROOT)}: status=dead 的角色 '{c}' 出现在 characters_present 中")

        # 时空检测
        loc = fm.get("location", "")
        date = fm.get("in_world_date", "")
        if date and loc:
            for c in present:
                if c in spacetime[date] and spacetime[date][c] != loc:
                    issues.append(
                        f"[BLOCK] {cf.relative_to(ROOT)}: 角色 '{c}' 在同一天({date})"
                        f" 出现在两个地点: '{spacetime[date][c]}' 和 '{loc}'"
                    )
                spacetime[date][c] = loc

def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--staged", action="store_true", help="仅检查 git staged 章节")
    ap.add_argument("--readiness", action="store_true", help="仅检查就绪自检")
    ap.add_argument("files", nargs="*", help="指定章节文件（缺省扫描全部）")
    args = ap.parse_args()

    issues = []

    # H1: 就绪自检
    if args.readiness or not args.files:
        check_readiness(issues)

    # 收集章节文件
    if args.files:
        chapter_files = [Path(f) for f in args.files if Path(f).exists()]
    elif args.staged:
        import subprocess
        result = subprocess.run(
            ["git", "-c", "core.quotepath=false", "diff", "--cached", "--name-only"],
            capture_output=True, text=True, cwd=str(ROOT)
        )
        staged = result.stdout.strip().split("\n")
        chapter_files = [
            ROOT / f for f in staged
            if f.startswith("03_正文/") and f.endswith(".md")
            and not "_准备_" in f and not "_审查_" in f
        ]
    else:
        chapter_files = sorted(
            p for p in TEXT_DIR.rglob("第*章.md")
            if "_准备_" not in p.name and "_审查_" not in p.name
        )

    if chapter_files:
        check_chapters(chapter_files, issues)

    # 输出
    blocks = [i for i in issues if "[BLOCK]" in i or "[H1-BLOCK]" in i]
    warns = [i for i in issues if "[WARN]" in i]
    infos = [i for i in issues if "[INFO]" in i]

    if blocks:
        for b in blocks:
            print(b)
        print(f"\n[FAIL] {len(blocks)} 阻断项")
    if warns:
        for w in warns:
            print(w)
    if infos:
        for i in infos:
            print(i)

    if not issues:
        print(f"[PASS] 章节检查 OK（{len(chapter_files)} 个章节文件）")

    return 1 if blocks else 0

if __name__ == "__main__":
    sys.exit(main())
