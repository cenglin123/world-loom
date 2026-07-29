#!/usr/bin/env python
"""伏笔登记表完整性检查。
检查项：
  - Markdown 表格结构完整性（列数）
  - 状态字段合法值（open / closed / abandoned）
  - open 超期检测（埋下后超过阈值未收）
  - closed 缺实际回收位置
  - ID 格式合法性
"""

import re
import sys
from pathlib import Path

CLUE_FILE = Path(__file__).resolve().parent.parent / "04_伏笔" / "伏笔登记表.md"
OPEN_STALE_CHAPTERS = 20  # open 超过 N 章未收 → 报警
USED_STALE_CHAPTERS = 15  # open 超过 M 章从未被提及 → 提示尽快用掉

def parse_chapter(ch: str) -> int | None:
    """解析 '3/10' 或 '1' 格式的章节号，返回绝对章节序号。模糊时序返回 None。"""
    ch = ch.strip()
    if not ch or ch in ("—", "-", "待填"):
        return None
    parts = ch.split("/")
    try:
        if len(parts) == 2:
            return int(parts[0]) * 1000 + int(parts[1])  # 卷*1000+章
        return int(parts[0]) * 1000
    except (ValueError, IndexError):
        return None

def main() -> int:
    if not CLUE_FILE.exists():
        print(f"[SKIP] 伏笔登记表不存在（{CLUE_FILE}）")
        return 0

    text = CLUE_FILE.read_text(encoding="utf-8")
    # 跳过 HTML 注释行和示例标记行
    lines = [l for l in text.split("\n") if not l.strip().startswith("<!--")]

    # 找表格行（以 | 开头）
    rows = [l for l in lines if l.strip().startswith("|") and not l.strip().startswith("|---")]
    if len(rows) < 3:
        print("[PASS] 伏笔登记表为空（仅有表头+分隔行）")
        return 0

    # 解析表头
    header = [c.strip() for c in rows[0].split("|")[1:-1]]
    expected_cols = ["ID", "描述", "埋下位置（卷/章）", "预计回收位置", "实际回收位置", "状态", "备注"]
    if len(header) < 6:
        print(f"[FAIL] 伏笔表列数不足：期望 ≥6，实际 {len(header)}")
        return 1

    issues = 0
    data_rows = rows[2:]  # 跳过表头+分隔行

    for i, row in enumerate(data_rows):
        cols = [c.strip() for c in row.split("|")[1:-1]]
        if len(cols) < 6:
            print(f"[WARN] 行 {i+1} 列数不足")
            issues += 1
            continue

        cid, desc, buried, expected, actual, status, *_ = cols

        # 跳过示例行（F001 且标记为示例）
        if cid == "F001" and "示例" in desc:
            continue
        # 跳过"待填"行
        if cid == "（待填）" or cid == "（待创建）":
            continue

        # ID 格式
        if not re.match(r"^F\d{3,}$", cid):
            print(f"[WARN] {cid}: ID 格式非法（期望 F001 起）")
            issues += 1

        # 状态
        if status not in ("open", "closed", "abandoned"):
            print(f"[WARN] {cid}: 状态非法值 '{status}'（允许: open/closed/abandoned）")
            issues += 1

        # open → 检查超期
        if status == "open":
            buried_ch = parse_chapter(buried)
            if buried_ch is None:
                print(f"[INFO] {cid}: 埋下位置为模糊时序（'{buried}'），无法机械判超期，需人工审查")
            else:
                # 查找最后写入章
                last_ch = _find_last_chapter()
                if last_ch and (last_ch - buried_ch) > OPEN_STALE_CHAPTERS:
                    print(f"[WARN] {cid}: open 超过 ~{OPEN_STALE_CHAPTERS} 章未收（埋于 {buried}），可能悬空")
                    issues += 1
                elif last_ch and (last_ch - buried_ch) > USED_STALE_CHAPTERS:
                    print(f"[INFO] {cid}: 埋了较久未用（{buried}），建议尽快回收或废弃（伏笔时效原则：埋下的伏笔要快速挖出来用掉）")

        # closed → 必须有实际回收位置
        if status == "closed" and (not actual or actual in ("—", "-", "待填")):
            print(f"[WARN] {cid}: status=closed 但缺实际回收位置")
            issues += 1

    if issues == 0:
        print(f"[PASS] 伏笔登记表 OK（{len(data_rows)} 条数据行）")
    return min(issues, 1)

def _find_last_chapter() -> int | None:
    """扫描 03_正文/ 目录找最后写入的章节。"""
    text_dir = CLUE_FILE.parent.parent / "03_正文"
    if not text_dir.exists():
        return None
    chapters = sorted(text_dir.rglob("第*章.md"))
    if not chapters:
        return None
    # 取最后修改的文件名
    last = chapters[-1]
    m = re.search(r"第(\d+)章", last.stem)
    if m:
        vol_m = re.search(r"第(\d+)卷", str(last.parent))
        vol = int(vol_m.group(1)) if vol_m else 1
        return vol * 1000 + int(m.group(1))
    return None

if __name__ == "__main__":
    sys.exit(main())
