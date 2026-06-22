#!/usr/bin/env python
"""人物标签完整性校验。
检查项：
  - 每个角色文件是否包含五类必填标签（门派/功法/等级/擅用/关系）
  - 标签格式合法性（以 门派/ 功法/ 等级/ 擅用/ 关系/ 开头）
  - 标签值是否与角色文件中的 faction 字段一致
  - 生成标签索引视图

用法:
  python scripts/check_tags.py check              # 校验
  python scripts/check_tags.py list               # 列出所有标签
  python scripts/check_tags.py show 门派           # 按类别列出
  python scripts/check_tags.py regenerate          # 重建 _索引.md 的标签汇总段
"""

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHAR_DIR = ROOT / "02_人物"
INDEX_FILE = CHAR_DIR / "_索引.md"

REQUIRED_CATEGORIES = ["门派", "功法", "等级", "擅用", "关系"]

def _parse_frontmatter(path: Path) -> dict | None:
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
    current_key = None
    in_list = False
    list_values = []
    for line in raw.split("\n"):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        # YAML list continuation
        if stripped.startswith("- ") and in_list:
            list_values.append(stripped[2:].strip())
            continue
        # New key
        if ":" in stripped:
            if in_list and current_key:
                fm[current_key] = list_values
                in_list = False
                list_values = []
            key, _, val = stripped.partition(":")
            key = key.strip()
            val = val.strip()
            if val == "":
                in_list = True
                current_key = key
                list_values = []
            else:
                fm[key] = val
                in_list = False
    if in_list and current_key:
        fm[current_key] = list_values
    return fm

def _list_character_files() -> dict[str, Path]:
    chars = {}
    for f in sorted(CHAR_DIR.glob("*.md")):
        name = f.stem
        if name in ("_索引", "人物模板", "README"):
            continue
        chars[name] = f
    return chars

def _parse_tags(tags_raw) -> list[str]:
    """解析 YAML tags: 可能是 ['门派/xxx', ...] 或 [门派/xxx, ...]"""
    if tags_raw is None:
        return []
    if isinstance(tags_raw, list):
        return [str(t).strip().strip("'\"") for t in tags_raw if str(t).strip()]
    # 字符串形式
    s = str(tags_raw).strip().strip("[]'\"")
    return [t.strip().strip("'\"") for t in s.split(",") if t.strip()]

def check(issues: list) -> int:
    chars = _list_character_files()
    if not chars:
        print("[SKIP] 无角色文件")
        return 0

    all_tags: dict[str, set[str]] = defaultdict(set)
    errors = 0

    for name, fpath in chars.items():
        fm = _parse_frontmatter(fpath)
        if fm is None:
            issues.append(f"[WARN] {name}: 缺少 frontmatter")
            errors += 1
            continue

        tags = _parse_tags(fm.get("tags", []))
        if not tags:
            issues.append(f"[WARN] {name}: 标签为空——至少需要门派/功法/等级/擅用/关系五类")
            errors += 1
            continue

        # 检查五类必填
        covered = set()
        for tag in tags:
            for cat in REQUIRED_CATEGORIES:
                if tag.startswith(f"{cat}/"):
                    covered.add(cat)
                    all_tags[cat].add(tag)

        missing_cats = set(REQUIRED_CATEGORIES) - covered
        if missing_cats:
            issues.append(f"[WARN] {name}: 缺少标签类别 {missing_cats}")
            errors += 1

        # 门派标签与本文件 faction 字段一致性
        faction = fm.get("faction", "")
        faction_tags = [t for t in tags if t.startswith("门派/")]
        if faction and faction_tags:
            expected = f"门派/{faction}"
            if expected not in faction_tags:
                issues.append(f"[WARN] {name}: faction='{faction}' 但标签中无'{expected}'")

    if errors == 0:
        total = sum(len(v) for v in all_tags.values())
        print(f"[PASS] 标签校验 OK（{len(chars)} 角色, {total} 个标签, {len(REQUIRED_CATEGORIES)} 类）")
    return min(errors, 1)

def cmd_list():
    chars = _list_character_files()
    if not chars:
        print("（无角色文件）")
        return
    for name, fpath in chars.items():
        fm = _parse_frontmatter(fpath)
        tags = _parse_tags(fm.get("tags", [])) if fm else []
        print(f"\n{name}:")
        for t in tags:
            print(f"  #{t}")

def cmd_show(category: str):
    chars = _list_character_files()
    result = defaultdict(list)
    for name, fpath in chars.items():
        fm = _parse_frontmatter(fpath)
        if not fm:
            continue
        tags = _parse_tags(fm.get("tags", []))
        for t in tags:
            if t.startswith(f"{category}/"):
                result[t].append(name)
    if not result:
        print(f"（无 {category} 类标签）")
        return
    for tag, names in sorted(result.items()):
        print(f"#{tag}: {', '.join(names)}")

def cmd_regenerate():
    """在 _索引.md 中生成标签汇总段。"""
    chars = _list_character_files()
    if not INDEX_FILE.exists():
        print(f"[FAIL] {INDEX_FILE} 不存在")
        sys.exit(1)

    all_tags: dict[str, set[str]] = defaultdict(set)
    for name, fpath in chars.items():
        fm = _parse_frontmatter(fpath)
        if not fm:
            continue
        tags = _parse_tags(fm.get("tags", []))
        for t in tags:
            all_tags[t].add(name)

    lines = ["> 本段由 `python scripts/check_tags.py regenerate` 自动生成。"]
    for cat in REQUIRED_CATEGORIES:
        cat_tags = {t: names for t, names in all_tags.items() if t.startswith(f"{cat}/")}
        if cat_tags:
            lines.append(f"\n### {cat}")
            for tag, names in sorted(cat_tags.items()):
                lines.append(f"- #{tag} → {', '.join(sorted(names))}")

    tag_block = "\n".join(lines)

    text = INDEX_FILE.read_text(encoding="utf-8")
    pattern = r"(## 标签汇总\n)(.*?)(?=\n## |\Z)"
    replacement = rf"\1\n{tag_block}\n"

    if "## 标签汇总" in text:
        new_text = re.sub(pattern, replacement, text, count=1, flags=re.DOTALL)
    else:
        # 在关系矩阵段之后插入
        marker = "## 关系矩阵"
        if marker in text:
            idx = text.find(marker)
            # 找到该段结束（下一个 ##）
            next_section = text.find("\n## ", idx + len(marker))
            if next_section == -1:
                next_section = len(text)
            new_text = text[:next_section] + f"\n\n## 标签汇总\n{tag_block}\n" + text[next_section:]
        else:
            new_text = text + f"\n\n## 标签汇总\n{tag_block}\n"

    INDEX_FILE.write_text(new_text, encoding="utf-8")
    print(f"[OK] 已重建标签汇总段（{len(all_tags)} 个标签）")

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "check":
        issues = []
        sys.exit(check(issues))
    elif cmd == "list":
        cmd_list()
    elif cmd == "show":
        cat = sys.argv[2] if len(sys.argv) > 2 else "门派"
        cmd_show(cat)
    elif cmd == "regenerate":
        cmd_regenerate()
    else:
        print(__doc__)
        sys.exit(1)

if __name__ == "__main__":
    main()
