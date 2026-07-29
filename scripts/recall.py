#!/usr/bin/env python
"""上下文召回 CLI —— 为写前上下文包组装注入集。

Phase 1（当前）：人物生成内核永久置顶 + 最近 5 条 L2 + 所有 pinned + 所有未解决问题。输出 Markdown 注入集，供 agent 转写为自然语言后注入上下文包。
Phase 2（预留）：--mode embedding 做语义相关性排序。

用法:
  python scripts/recall.py <角色名> [<角色名> ...]      # 返回在场角色的 Markdown 注入集
  python scripts/recall.py --count                        # 统计全仓库 L2 总条数
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHAR_DIR = ROOT / "02_人物"

# 写前永久置顶的人物生成字段。字段内容的唯一事实源在人物卡「一、人设」。
STABLE_CORE_FIELDS = (
    "错误信念", "自觉欲望", "深层需要",
    "核心价值排序", "自我认同", "默认策略", "压力退化模式",
    "认知盲点", "行为边界", "越线条件与代价",
    "表面身份及其要求", "秘密自我", "暴露代价", "逼迫选择的条件",
)


def _read_text(path: Path) -> str | None:
    """读取文件内容，UTF-8 解码失败时返回 None。"""
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        print(f"[WARN] 文件非 UTF-8 编码: {path.relative_to(ROOT)}", file=sys.stderr)
        return None


def _is_placeholder(val: str) -> bool:
    """模板占位符检测——'（待填写…）' 或 '（待选择…）'。普通中文括号内容不过滤。"""
    return bool(re.match(r"^[（(]待[填写选择]", val.strip()))


def _parse_table_fields(text: str, wanted: tuple[str, ...]) -> dict[str, str]:
    """从 Markdown 两列表格读取指定字段；占位符不返回。"""
    found: dict[str, str] = {}
    wanted_set = set(wanted)
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|") or stripped.startswith("|---"):
            continue
        cells = [cell.strip() for cell in stripped.split("|")[1:-1]]
        if len(cells) < 2 or cells[0] not in wanted_set:
            continue
        value = cells[1]
        if value and not _is_placeholder(value):
            found[cells[0]] = value
    return found


def _list_characters() -> list[str]:
    chars = []
    for f in sorted(CHAR_DIR.glob("*.md")):
        name = f.stem
        if name in ("_索引", "人物模板", "README"):
            continue
        chars.append(name)
    return chars


def _parse_l2_entries(text: str) -> list[dict]:
    """解析人物文件「二、记忆」段中的 L2 条目。
    结构锚点：#### (场景名) 切分条目，**字段**：提取值。"""
    # 定位「二、记忆」段
    mem_start = text.find("## 二、记忆")
    if mem_start == -1:
        return []

    # 截取到「三、关系」之前（如果存在）
    rel_start = text.find("## 三、关系", mem_start)
    section = text[mem_start:rel_start] if rel_start != -1 else text[mem_start:]

    # 按 #### 切分；第一个 block 是本节说明文字。
    entries = []
    blocks = re.split(r"\n#### ", section)
    for block in blocks[1:]:
        entry = {}
        # 场景名在 #### 后面——剥离 [pinned] 标签和 HTML 注释
        scene_end = block.find("\n")
        raw_scene = block[:scene_end].strip() if scene_end != -1 else block.strip()
        raw_scene = re.sub(r"\[pinned\]", "", raw_scene)
        raw_scene = re.sub(r"<!--.*?-->", "", raw_scene)
        entry["场景"] = raw_scene.strip()

        # 提取字段
        fields = {
            "我的行动": "我的行动",
            "我的判断": "我的判断",
            "情感轨迹": "情感轨迹",
            "未解决的问题": "未解决的问题",
            "对他人看法的变化": "对他人看法的变化",
        }
        for key, label in fields.items():
            m = re.search(rf"\*\*{label}\*\*[：:]\s*(.+?)(?=\n\*\*|\n\n|\Z)", block, re.DOTALL)
            if m:
                val = m.group(1).strip()
                if val and not _is_placeholder(val):  # 排除模板占位符
                    entry[key] = val

        if entry.get("场景") and len(entry) > 1:
            # 检测 [pinned] 标记
            entry["pinned"] = "[pinned]" in block
            entries.append(entry)

    return entries


def cmd_recall(char_names: list[str]):
    """为指定角色生成 Markdown 注入集。"""
    output = {"stable_core": {}, "l2": {}}

    for name in char_names:
        char_file = CHAR_DIR / f"{name}.md"
        if not char_file.exists():
            print(f"[WARN] 角色文件不存在: 02_人物/{name}.md", file=sys.stderr)
            continue

        text = _read_text(char_file)
        if text is None:
            continue

        stable_core = _parse_table_fields(text, STABLE_CORE_FIELDS)
        if stable_core:
            output["stable_core"][name] = stable_core

        # L2 条目
        entries = _parse_l2_entries(text)
        if not entries:
            output["l2"][name] = []
            continue

        # Phase 1 过滤：取前 5 条文件序 + pinned + 未解决问题非空（条目按写入时间倒序追加，文件序即时间序）
        selected = []
        for e in entries[:5]:
            selected.append(e)

        for e in entries[5:]:
            if e.get("pinned"):
                if e not in selected:
                    selected.append(e)

        for e in entries:
            unsolved = e.get("未解决的问题", "")
            if unsolved and unsolved not in ("—", "-", "无"):
                if e not in selected:
                    selected.append(e)

        # 保持原始时间序输出
        output["l2"][name] = selected

    # 输出 Markdown（agent 的内部材料，供压缩转写为自然语言后注入上下文包）
    print("# 写前注入集 · recall.py Phase 1")
    print("# 过滤策略：人物生成内核永久置顶 + 每人最近 5 条 L2 + pinned + 未解决问题非空")
    print()

    if output["stable_core"]:
        print("## 人物生成内核（永久置顶）")
        for name, fields in output["stable_core"].items():
            print(f"\n### {name}")
            for k, v in fields.items():
                print(f"- **{k}**：{v}")
        print()

    print("## L2 情节记忆")
    for name, entries in output["l2"].items():
        print(f"\n### {name}（{len(entries)} 条）")
        if not entries:
            print("（无 L2 数据）")
            continue
        for i, e in enumerate(entries):
            pin = " [pinned]" if e.get("pinned") else ""
            print(f"\n#### {e.get('场景','?')}{pin}")
            for key in ["我的行动", "我的判断", "情感轨迹", "未解决的问题", "对他人看法的变化"]:
                val = e.get(key, "")
                if val:
                    print(f"- **{key}**：{val}")


def cmd_count():
    """统计全仓库 L2 条目总数 + 角色分布。"""
    chars = _list_characters()
    if not chars:
        print("L2 总数: 0（无角色文件）")
        return

    total = 0
    for name in chars:
        text = _read_text(CHAR_DIR / f"{name}.md")
        if text is None:
            continue
        entries = _parse_l2_entries(text)
        total += len(entries)
        print(f"  {name}: {len(entries)} 条 L2")

    print(f"\nL2 总数: {total}")
    if total >= 300:
        print("[NOTICE] L2 总量超 300——建议评估升级至 Phase 2 RAG 检索")
    elif total >= 100:
        print("[INFO] L2 总量超 100——可考虑启用 Phase 1.5 手动 pin 机制")


def main():
    args = sys.argv[1:]

    if not args:
        print(__doc__)
        sys.exit(1)

    if args[0] == "--count":
        cmd_count()
    elif args[0] == "--help":
        print(__doc__)
    else:
        cmd_recall(args)


if __name__ == "__main__":
    main()
