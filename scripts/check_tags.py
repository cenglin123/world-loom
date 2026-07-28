#!/usr/bin/env python
"""人物标签完整性校验。
检查项：
  - 每个角色文件是否包含四类必填标签（所属/能力/等级/擅用）
  - 标签格式合法性（以 所属/ 能力/ 等级/ 擅用/ 开头）
  - 标签值是否与角色文件中的 faction 字段一致
  - 生成标签索引视图

用法:
  python scripts/check_tags.py check              # 校验
  python scripts/check_tags.py list               # 列出所有标签
  python scripts/check_tags.py show 所属           # 按类别列出
  python scripts/check_tags.py regenerate          # 重建 _索引.md 的标签汇总段
  python scripts/check_tags.py _index              # 重建 _索引.md 的角色清单表
"""

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHAR_DIR = ROOT / "02_人物"
INDEX_FILE = CHAR_DIR / "_索引.md"

REQUIRED_CATEGORIES = ["所属", "能力", "等级", "擅用"]

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
    lines = raw.split("\n")
    for i, line in enumerate(lines):
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
                # Only enter list mode if a subsequent line starts with "- "
                # (prevents empty faction: etc. from being treated as a YAML list)
                peek_in_list = False
                for j in range(i + 1, len(lines)):
                    next_line = lines[j].strip()
                    if not next_line or next_line.startswith("#"):
                        continue
                    if next_line.startswith("- "):
                        peek_in_list = True
                    break
                in_list = peek_in_list
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
    """解析 YAML tags: 可能是 ['所属/xxx', ...] 或 [所属/xxx, ...]"""
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
            issues.append(f"[WARN] {name}: 标签为空——至少需要所属/能力/等级/擅用四类")
            errors += 1
            continue

        # 检查四类必填
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

        # 所属标签与本文件 faction 字段一致性
        faction = fm.get("faction", "")
        faction_tags = [t for t in tags if t.startswith("所属/")]
        if faction and faction_tags:
            expected = f"所属/{faction}"
            if expected not in faction_tags:
                issues.append(f"[WARN] {name}: faction='{faction}' 但标签中无'{expected}'")

    if errors > 0:
        for issue in issues:
            print(issue)
    else:
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

def cmd_index():
    """在 _索引.md 中生成角色清单表。从 02_人物/*.md 的 frontmatter 读取 role 字段。"""
    chars = _list_character_files()
    if not INDEX_FILE.exists():
        print(f"[FAIL] {INDEX_FILE} 不存在")
        sys.exit(1)

    rows = []
    for name, fpath in sorted(chars.items()):
        fm = _parse_frontmatter(fpath)
        role = fm.get("role", "—") if fm else "—"
        rows.append(f"| {name} | {name}.md | {role} |")

    if not rows:
        rows.append("| （待创建） | — | — |")

    table = "\n".join([
        "| 角色名 | 文件 | 定位 |",
        "|--------|------|------|",
    ] + rows)

    text = INDEX_FILE.read_text(encoding="utf-8")
    pattern = r"(## 角色清单\n)(.*?)(?=\n## |\Z)"
    if "## 角色清单" in text:
        new_text = re.sub(pattern, rf"\1\n{table}\n", text, count=1, flags=re.DOTALL)
    else:
        # 在文件开头插入（frontmatter 之后或文件头）
        if text.startswith("---"):
            end = text.find("---", 3)
            prefix = text[:end+3]
            body = text[end+3:]
            new_text = prefix + f"\n\n## 角色清单\n{table}\n" + body
        else:
            new_text = f"## 角色清单\n{table}\n\n" + text

    INDEX_FILE.write_text(new_text, encoding="utf-8")
    print(f"[OK] 已重建角色清单表（{len(chars)} 个角色）")

def cmd_wizard(char_name: str):
    """角色创建/完善向导。检查必填字段，报告缺口并给出引导提示。"""
    char_file = CHAR_DIR / f"{char_name}.md"
    template_file = CHAR_DIR / "人物模板.md"

    # 文件不存在 → 从模板创建
    if not char_file.exists():
        if not template_file.exists():
            print(f"[FAIL] 人物模板不存在：{template_file}")
            sys.exit(1)
        template_text = template_file.read_text(encoding="utf-8")
        # 替换占位符
        new_text = template_text.replace("<角色名>", char_name)
        char_file.write_text(new_text, encoding="utf-8")
        print(f"[OK] 已从模板创建 {char_file.relative_to(ROOT)}")

    fm = _parse_frontmatter(char_file)
    if fm is None:
        print(f"[FAIL] {char_file.relative_to(ROOT)} 缺少 frontmatter")
        sys.exit(1)

    # 读取正文中的人物生成字段
    body_text = char_file.read_text(encoding="utf-8")
    body_after_fm = body_text[body_text.find("---", 3)+3:] if body_text.startswith("---") else body_text

    def _value_is_filled(val: str) -> bool:
        val = val.strip()
        return bool(val) and not val.startswith(("（", "(")) and "待填" not in val

    def _body_has_field(text: str, field: str) -> bool:
        """检查 Markdown 两列表格中的字段是否非空、非占位符。"""
        pattern = rf"\| {re.escape(field)} \| (.+?) \|"
        m = re.search(pattern, text)
        return bool(m and _value_is_filled(m.group(1)))

    def _body_has_bullet(text: str, field: str) -> bool:
        """检查 `- **字段**：值` 是否非空、非占位符。"""
        pattern = rf"(?m)^- \*\*{re.escape(field)}\*\*[：:]\s*(.*)$"
        m = re.search(pattern, text)
        return bool(m and _value_is_filled(m.group(1)))

    def _table_check(field: str, prompt: str, example: str) -> dict:
        return {
            "value": "✓" if _body_has_field(body_after_fm, field) else "",
            "prompt": prompt,
            "example": example,
        }

    def _bullet_check(field: str, prompt: str, example: str) -> dict:
        return {
            "value": "✓" if _body_has_bullet(body_after_fm, field) else "",
            "prompt": prompt,
            "example": example,
        }

    # 检查清单
    checks = {
        "status (alive|dead|departed|unknown)": {
            "value": fm.get("status", ""),
            "prompt": "该角色当前是存活、已故、退场还是状态未知？",
            "example": "alive"
        },
        "role (protagonist|antagonist|deuteragonist|supporting|minor)": {
            "value": fm.get("role", ""),
            "prompt": "该角色在故事中的定位？主角/反派/二号位/配角/次要？",
            "example": "protagonist"
        },
        "age": {
            "value": fm.get("age", ""),
            "prompt": "该角色的年龄？",
            "example": "27"
        },
        "faction": {
            "value": fm.get("faction", ""),
            "prompt": "该角色所属/阵营？（对应 #所属/ 标签）",
            "example": "七瑶门"
        },
        "first_appearance (卷/章)": {
            "value": fm.get("first_appearance", ""),
            "prompt": "该角色首次出场的卷/章？",
            "example": "1/3"
        },
        "world_position (上层|下层|边缘|中心)": {
            "value": fm.get("world_position", ""),
            "prompt": "该角色在世界结构中的位置？上层、下层、边缘还是中心？",
            "example": "边缘"
        },
        "style_register": {
            "value": fm.get("style_register", ""),
            "prompt": "对照 docs/style-locked.md 选择该角色的文风注册。",
            "example": "武侠"
        },
        "塑造性事件": _table_check(
            "塑造性事件",
            "哪件具体经历真正改变了该角色？只写事件，不写流水账生平。",
            "七岁时亲眼看见父亲因犹豫错失救援时机，十一名同袍因此战死"
        ),
        "错误信念": _table_check(
            "错误信念",
            "该角色从塑造性事件中得出了什么片面结论？",
            "任何犹豫都会害死人"
        ),
        "自觉欲望": _table_check(
            "自觉欲望",
            "该角色以为得到什么就能解决问题？必须具体。",
            "掌握所有威胁的动向，让同伴永远不必承担意外"
        ),
        "深层需要": _table_check(
            "深层需要",
            "该角色真正需要理解、接受或改变什么？",
            "理解审慎不等于软弱，控制也不等于安全"
        ),
        "核心价值排序": _table_check(
            "核心价值排序",
            "目标冲突时如何排序？至少写出三项。",
            "姐妹安全 > 查清真相 > 门派名誉 > 自己性命"
        ),
        "自我认同": _table_check(
            "自我认同",
            "该角色认为自己是怎样的人？",
            "我是必须替所有人提前发现危险的人"
        ),
        "默认策略": _table_check(
            "默认策略",
            "该角色通常用什么方式解决问题？",
            "先收集信息，再用规则和责任迫使他人配合"
        ),
        "压力退化模式": _table_check(
            "压力退化模式",
            "恐惧升高或资源不足时，默认策略如何变形？",
            "从收集信息退化为封锁信息、替所有人做决定"
        ),
        "认知盲点": _table_check(
            "认知盲点",
            "哪类事实最容易被该角色忽略或曲解？",
            "低估他人自主承担风险的意愿"
        ),
        "行为边界": _table_check(
            "行为边界",
            "正常状态下不愿做什么？",
            "不以无辜者作诱饵，不隐瞒直接威胁姐妹安全的信息"
        ),
        "越线条件与代价": _table_check(
            "越线条件与代价",
            "什么冲突会逼他越线；越线后会失去什么？",
            "若唯一线索依附于无辜者，可能短暂欺骗对方；代价是失去自我认同与同伴信任"
        ),
        "表面身份及其要求": _table_check(
            "表面身份及其要求",
            "公开身份是什么，它要求该角色必须怎样生活？",
            "七瑶门外行小队领队；必须显得冷静、公正、永远有答案"
        ),
        "秘密自我": _table_check(
            "秘密自我",
            "真正想要、害怕或必须隐藏的另一面是什么？",
            "其实渴望有人替她做一次决定，也害怕自己根本保护不了所有人"
        ),
        "暴露代价": _table_check(
            "暴露代价",
            "秘密被看见后会失去什么？",
            "失去领队权威，也可能让姐妹不再相信她的判断"
        ),
        "逼迫选择的条件": _table_check(
            "逼迫选择的条件",
            "什么事件会让表面身份与秘密自我无法继续共存？",
            "必须公开承认自己判断错误，才能阻止姐妹执行错误命令"
        ),
        "表达层/外表": _bullet_check(
            "外表", "哪些外观信息能体现身份、处境或行动能力？", "白衣利落，惯把袖口束紧以便随时出手"
        ),
        "表达层/语言指纹": _bullet_check(
            "语言指纹", "句长、称呼和回避表达有什么规律？", "话少，先给结论；对姐妹用昵称，对外人用全名"
        ),
        "表达层/身体语言": _bullet_check(
            "身体语言", "紧张、撒谎或争夺控制权时有什么可观察动作？", "越不确定越放慢动作，右手会停在剑柄一寸外"
        ),
        "表达层/注意力偏向": _bullet_check(
            "注意力偏向", "进入新场景后最先注意什么？", "先看出口、遮蔽物和姐妹之间的距离"
        ),
    }

    # 检查标签四类
    tags = _parse_tags(fm.get("tags", []))
    tag_covered = set()
    for t in tags:
        for cat in REQUIRED_CATEGORIES:
            if t.startswith(f"{cat}/"):
                tag_covered.add(cat)
    for cat in REQUIRED_CATEGORIES:
        checks[f"标签 #{cat}/"] = {
            "value": "✓" if cat in tag_covered else "",
            "prompt": f"该角色的{cat}是什么？",
            "example": f"{cat}/<填写>"
        }

    filled = []
    missing = []
    for field, info in checks.items():
        if info["value"] and info["value"] != "[]":
            filled.append(field)
        else:
            missing.append((field, info))

    print(f"\n{'='*50}")
    print(f"  {char_name} · 人物卡完善状态")
    print(f"  {len(filled)}/{len(checks)} 字段已填写\n")

    if filled:
        print("已填写:")
        for f in filled:
            print(f"  [OK] {f}")

    if missing:
        print(f"\n待完善 ({len(missing)} 项):\n")
        for field, info in missing:
            print(f"  [  ] {field}")
            print(f"       提示: {info['prompt']}")
            print(f"       示例: {info['example']}")
            print()

    if not missing:
        print("\n全部字段已就绪，可以开始使用该角色。")
    else:
        print(f"填写完成后运行 python scripts/check_tags.py check 校验完整性。")

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
        cat = sys.argv[2] if len(sys.argv) > 2 else "所属"
        cmd_show(cat)
    elif cmd == "regenerate":
        cmd_regenerate()
    elif cmd == "wizard":
        if len(sys.argv) < 3:
            print("用法: python scripts/check_tags.py wizard <角色名>")
            sys.exit(1)
        cmd_wizard(sys.argv[2])
    elif cmd == "_index":
        cmd_index()
    else:
        print(__doc__)
        sys.exit(1)

if __name__ == "__main__":
    main()
