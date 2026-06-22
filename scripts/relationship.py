#!/usr/bin/env python
"""人物关系四格 CLI —— 增删改查 + 完整性校验 + 索引文件视图生成。

数据源: 02_人物/relationships.json
视图:  02_人物/_索引.md 的关系矩阵段（由 regenerate 生成）

用法:
  python scripts/relationship.py list                              # 列出所有关系对
  python scripts/relationship.py show 沈照影                       # 查某角色的全部关系
  python scripts/relationship.py show 沈照影 顾寒枝                # 查指定角色对
  python scripts/relationship.py set 沈照影 顾寒枝 \               # 新建/全量覆盖
      --public "..." --hidden-a "..." --hidden-b "..." \
      --trigger "映月湖事件"
  python scripts/relationship.py update 沈照影 顾寒枝 \            # 更新单个单元格
      --hidden-a "新的隐藏层内容"
  python scripts/relationship.py delete 沈照影 顾寒枝              # 删除关系对
  python scripts/relationship.py regenerate                        # 重建 _索引.md 矩阵段
  python scripts/relationship.py check                             # 校验完整性
"""

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_FILE = ROOT / "02_人物" / "relationships.json"
INDEX_FILE = ROOT / "02_人物" / "_索引.md"
CHAR_DIR = ROOT / "02_人物"

# ── helpers ──────────────────────────────────────────────

def _load() -> dict:
    if not DATA_FILE.exists():
        return {"meta": {"version": 1}, "pairs": {}}
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))

def _save(data: dict):
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    DATA_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8"
    )

def _key(a: str, b: str) -> str:
    """规范化角色对 key：按字母序。"""
    return f"{min(a, b)}:{max(a, b)}" if a <= b else f"{b}:{a}"

def _list_characters() -> list[str]:
    """从人物目录扫描实际角色文件（排除模板和索引）。"""
    chars = []
    for f in sorted(CHAR_DIR.glob("*.md")):
        name = f.stem
        if name in ("_索引", "人物模板", "README"):
            continue
        chars.append(name)
    return chars

def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

# ── commands ─────────────────────────────────────────────

def cmd_list():
    data = _load()
    if not data["pairs"]:
        print("（无关系数据）")
        return
    for k, v in data["pairs"].items():
        a, b = k.split(":")
        print(f"\n{'='*50}")
        print(f"  {a} <-> {b}")
        print(f"  公开: {v.get('公开','')}")
        print(f"  {a} 隐藏: {v.get(f'{a}_隐藏','')}")
        print(f"  {b} 隐藏: {v.get(f'{b}_隐藏','')}")
        print(f"  盲区({a}): {v.get(f'{a}_盲区','')}")
        print(f"  盲区({b}): {v.get(f'{b}_盲区','')}")
        print(f"  禁区: {v.get('禁区','')}")
        print(f"  更新时间: {v.get('updated_at','')}")
        print(f"  触发事件: {v.get('updated_trigger','')}")

def cmd_show(char_a: str, char_b: str | None = None):
    data = _load()
    if char_b:
        k = _key(char_a, char_b)
        if k not in data["pairs"]:
            print(f"未找到 {char_a} <-> {char_b} 的关系记录")
            return
        v = data["pairs"][k]
        a, b = k.split(":")
        print(json.dumps({k: v}, ensure_ascii=False, indent=2))
    else:
        found = False
        for k, v in data["pairs"].items():
            if char_a in k.split(":"):
                found = True
                print(json.dumps({k: v}, ensure_ascii=False, indent=2))
                print()
        if not found:
            print(f"未找到 {char_a} 的任何关系记录")

def cmd_set(char_a: str, char_b: str, public: str = "",
            hidden_a: str = "", hidden_b: str = "",
            blind_a: str = "", blind_b: str = "",
            forbidden: str = "", trigger: str = ""):
    data = _load()
    k = _key(char_a, char_b)
    a, b = k.split(":")
    data["pairs"][k] = {
        "公开": public,
        f"{a}_隐藏": hidden_a,
        f"{b}_隐藏": hidden_b,
        f"{a}_盲区": blind_a,
        f"{b}_盲区": blind_b,
        "禁区": forbidden,
        "updated_at": _now(),
        "updated_trigger": trigger,
    }
    _save(data)
    print(f"[OK] 已设置 {char_a} <-> {char_b}")

def cmd_update(char_a: str, char_b: str, **kwargs):
    data = _load()
    k = _key(char_a, char_b)
    if k not in data["pairs"]:
        print(f"未找到 {char_a} <-> {char_b}，请先用 set 创建")
        sys.exit(1)
    for field, val in kwargs.items():
        if val is not None:
            data["pairs"][k][field] = val
    data["pairs"][k]["updated_at"] = _now()
    _save(data)
    print(f"[OK] 已更新 {char_a} <-> {char_b}")

def cmd_delete(char_a: str, char_b: str):
    data = _load()
    k = _key(char_a, char_b)
    if k not in data["pairs"]:
        print(f"未找到 {char_a} <-> {char_b}")
        return
    del data["pairs"][k]
    _save(data)
    print(f"[OK] 已删除 {char_a} <-> {char_b}")

def cmd_regenerate():
    """根据 relationships.json 重建 _索引.md 的关系矩阵段。"""
    data = _load()
    if not INDEX_FILE.exists():
        print(f"[FAIL] 索引文件不存在: {INDEX_FILE}")
        sys.exit(1)

    text = INDEX_FILE.read_text(encoding="utf-8")

    # 构建关系矩阵 markdown 表格
    rows = ["| A → B | 公开层 | A 隐藏 | B 隐藏 | A 盲区 | B 盲区 | 禁区 | 最后更新 |",
            "|-------|--------|--------|--------|--------|--------|------|---------|"]
    for k, v in data["pairs"].items():
        a, b = k.split(":")
        pub = _esc(v.get("公开", ""))
        ha = _esc(v.get(f"{a}_隐藏", ""))
        hb = _esc(v.get(f"{b}_隐藏", ""))
        ba = _esc(v.get(f"{a}_盲区", ""))
        bb = _esc(v.get(f"{b}_盲区", ""))
        fb = _esc(v.get("禁区", ""))
        ts = v.get("updated_at", "")[:10] or ""
        rows.append(f"| {a} → {b} | {pub} | {ha} | {hb} | {ba} | {bb} | {fb} | {ts} |")
        rows.append(f"| {b} → {a} | {pub} | {hb} | {ha} | {bb} | {ba} | {fb} | {ts} |")
    if len(rows) == 2:
        rows.append("| （待填） | | | | | | | |")

    matrix_block = "\n".join(rows)

    # 替换 ## 关系矩阵（角色对摘要）段——从该标题到下一个 ## 或文件末尾
    pattern = r"(## 关系矩阵（角色对摘要）\n)(.*?)(?=\n## |\Z)"
    replacement = rf"\1\n> 本段由 `python scripts/relationship.py regenerate` 从 `02_人物/relationships.json` 自动生成，请勿手动编辑。\n\n{matrix_block}\n"
    new_text = re.sub(pattern, replacement, text, count=1, flags=re.DOTALL)

    if new_text == text:
        print("[WARN] 未找到 '## 关系矩阵（角色对摘要）' 段，请在 _索引.md 中添加该标题")
        sys.exit(1)

    INDEX_FILE.write_text(new_text, encoding="utf-8")
    print(f"[OK] 已重建 {INDEX_FILE} 的关系矩阵段（{len(data['pairs'])} 对关系）")

def cmd_check() -> int:
    """校验完整性：JSON <-> 角色文件 一致性。"""
    data = _load()
    chars = _list_characters()
    issues = 0

    # 检查 JSON 中的角色是否都有对应文件
    for k in data["pairs"]:
        a, b = k.split(":")
        for c in (a, b):
            if c not in chars:
                print(f"[WARN] {k}: '{c}' 在 relationships.json 中存在但无对应角色文件")
                issues += 1

    # 检查 JSON 中的隐藏/盲区字段名与 key 中的角色名一致
    for k, v in data["pairs"].items():
        a, b = k.split(":")
        expected = {f"{a}_隐藏", f"{b}_隐藏", f"{a}_盲区", f"{b}_盲区", "公开", "禁区", "updated_at", "updated_trigger"}
        extra = set(v.keys()) - expected
        if extra:
            print(f"[WARN] {k}: 多余字段 {extra}")
            issues += 1
        missing = (expected - set(v.keys())) - {"updated_trigger"}  # trigger 可选
        if missing:
            print(f"[WARN] {k}: 缺少字段 {missing}")
            issues += 1

    if issues == 0:
        print(f"[PASS] relationships.json OK（{len(data['pairs'])} 对关系, {len(chars)} 个角色）")
    return min(issues, 1)

def _esc(s: str) -> str:
    """转义 markdown 表格中的 | 字符。"""
    return s.replace("|", "\\|").replace("\n", " ")

# ── main ─────────────────────────────────────────────────

def usage():
    print(__doc__)
    sys.exit(1)

def main():
    args = sys.argv[1:]
    if not args:
        usage()

    cmd = args[0]

    if cmd == "list":
        cmd_list()
    elif cmd == "show":
        if len(args) == 2:
            cmd_show(args[1])
        elif len(args) == 3:
            cmd_show(args[1], args[2])
        else:
            usage()
    elif cmd == "set":
        if len(args) < 3:
            usage()
        # 解析 --key value 参数
        kwargs = {}
        i = 3
        while i < len(args):
            if args[i].startswith("--"):
                key = args[i][2:].replace("-", "_")
                val = args[i+1] if i+1 < len(args) and not args[i+1].startswith("--") else ""
                kwargs[key] = val
                i += 2 if val else 1
            else:
                i += 1
        cmd_set(args[1], args[2],
                public=kwargs.get("public", ""),
                hidden_a=kwargs.get("hidden_a", ""),
                hidden_b=kwargs.get("hidden_b", ""),
                blind_a=kwargs.get("blind_a", ""),
                blind_b=kwargs.get("blind_b", ""),
                forbidden=kwargs.get("forbidden", ""),
                trigger=kwargs.get("trigger", ""))
    elif cmd == "update":
        if len(args) < 3:
            usage()
        updates = {}
        field_map = {
            "public": "公开", "hidden_a": None, "hidden_b": None,
            "blind_a": None, "blind_b": None, "forbidden": "禁区", "trigger": "updated_trigger"
        }
        i = 3
        while i < len(args):
            if args[i].startswith("--"):
                key = args[i][2:]
                val = args[i+1] if i+1 < len(args) and not args[i+1].startswith("--") else ""
                # 映射到 JSON 字段
                json_key = key.replace("-", "_")
                if json_key in ("hidden_a", "hidden_b", "blind_a", "blind_b"):
                    # 需要拼上角色名：f"{角色名}_{隐藏/盲区}"
                    a, b = sorted([args[1], args[2]])
                    if json_key.endswith("_a"):
                        json_key_final = f"{a}_{json_key[:-2]}"
                    else:
                        json_key_final = f"{b}_{json_key[:-2]}"
                elif json_key == "public":
                    json_key_final = "公开"
                elif json_key == "forbidden":
                    json_key_final = "禁区"
                elif json_key == "trigger":
                    json_key_final = "updated_trigger"
                else:
                    json_key_final = json_key
                updates[json_key_final] = val
                i += 2 if val else 1
            else:
                i += 1
        cmd_update(args[1], args[2], **updates)
    elif cmd == "delete":
        if len(args) != 3:
            usage()
        cmd_delete(args[1], args[2])
    elif cmd == "regenerate":
        cmd_regenerate()
    elif cmd == "check":
        sys.exit(cmd_check())
    else:
        usage()

if __name__ == "__main__":
    main()
