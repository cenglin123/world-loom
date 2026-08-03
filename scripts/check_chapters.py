#!/usr/bin/env python
"""章节 + 人物时空一致性校验。
检查项：
  - 章节 frontmatter 字段完整性
  - characters_present 引用的角色都在 02_人物/ 下有文件
  - status=dead 的角色不出现在 characters_present 中
  - 同一 in_world_date 下角色不出现于两个不同 location
  - 日期文字结构相同且可解析时，章节顺序与日期顺序不得倒流（不可解析 → 跳过，fail-open）
  - 就绪自检：世界观/大纲主线一句话/人物/叙述约定非空才能提交正文
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
# 四阶段工作流的过程文件（_准备_/_审查_/_审查后_）统一放各卷的这个子目录，
# 与正文章节分开——正文目录只留 第M章.md。
WORK_DIR = "_工作"
WORLD_FILE = ROOT / "00_世界观" / "核心设定.md"
OUTLINE_FILE = ROOT / "01_大纲" / "主线.md"
INDEX_FILE = CHAR_DIR / "_索引.md"
STYLE_LOCKED_FILE = ROOT / "docs" / "style-locked.md"  # 视角/时态锁定层（就绪自检参照）

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

_CN_DIGIT = {"零": 0, "〇": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4,
             "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
_NUM_TOKEN_RE = re.compile(r"初?[零〇一二两三四五六七八九十百千万廿卅]+|\d+")


def _cn_to_int(s: str) -> int | None:
    """中文数字（含 初/十/廿/卅/百/千 前缀）→ int；不可解析返回 None。"""
    if s.isdigit():
        return int(s)
    s = s.lstrip("初")
    section = 0
    for unit, mul in (("千", 1000), ("百", 100), ("十", 10)):
        if unit in s:
            left, _, s = s.partition(unit)
            section += (_CN_DIGIT.get(left[-1], 1) if left else 1) * mul
    if s.startswith("廿"):
        section, s = section + 20, s[1:]
    elif s.startswith("卅"):
        section, s = section + 30, s[1:]
    if s:
        d = _CN_DIGIT.get(s)
        if d is None:
            return None
        section += d
    return section


def _date_parts(s: str) -> tuple[tuple[str, ...], tuple[int, ...]] | None:
    """日期串 → (文字骨架, 数值序列)。含不可解析数字或无数字 → None。

    两个日期只在**文字骨架完全相同**时可比（同日历、同纪元）；
    骨架不同（改元/换历法/换纪月名）→ 不比较，fail-open。
    """
    lits, nums, pos = [], [], 0
    for m in _NUM_TOKEN_RE.finditer(s):
        lits.append(s[pos:m.start()])
        v = _cn_to_int(m.group())
        if v is None:
            return None
        nums.append(v)
        pos = m.end()
    lits.append(s[pos:])
    if not nums:
        return None
    return tuple(lits), tuple(nums)


def _section_has_content(text: str, heading: str) -> bool:
    """指定 `## <heading>` 小节去掉占位符后是否有实质内容。"""
    m = re.search(rf"^## {re.escape(heading)}\s*$(.*?)(?=^## |\Z)",
                  text, flags=re.M | re.DOTALL)
    if not m:
        return False
    cleaned = re.sub(r'[（(]待[填写选择][^）)]*[）)]', '', m.group(1)).strip()
    return bool(cleaned)

def _body_has_content(path: Path) -> bool:
    """检查 markdown 文件去掉 frontmatter 后是否有实质内容（非仅占位符）。"""
    if not path.exists():
        return False
    text = path.read_text(encoding="utf-8")
    if text.startswith("---"):
        end = text.find("---", 3)
        body = text[end+3:] if end != -1 else text
    else:
        body = text
    # 去掉中文占位符（待填写/待选择 及其变体）
    cleaned = re.sub(r'[（(]待[填写选择][^）)]*[）)]', '', body)
    cleaned = cleaned.strip()
    return bool(cleaned)

def check_readiness(issues: list):
    """H1: 就绪自检——世界观/大纲/人物/写作风格非空才允许提交正文。"""
    # 检查世界观（不依赖具体标题名，检查文件体是否有实质内容）
    if WORLD_FILE.exists():
        if not _body_has_content(WORLD_FILE):
            issues.append("[H1-BLOCK] 世界观/核心设定.md 无实质内容（仍为待填写）")
    else:
        issues.append("[H1-BLOCK] 世界观/核心设定.md 不存在")

    # 检查大纲主线（整文件有实质内容，且「主线（一句话）」小节单独填好——
    # 只填了分卷规划等其它小节不算就绪）
    if OUTLINE_FILE.exists():
        if not _body_has_content(OUTLINE_FILE):
            issues.append("[H1-BLOCK] 大纲/主线.md 主线一句话仍为'待填写'")
        elif not _section_has_content(
                OUTLINE_FILE.read_text(encoding="utf-8"), "主线（一句话）"):
            issues.append("[H1-BLOCK] 大纲/主线.md「主线（一句话）」小节仍为待填写")
    else:
        issues.append("[H1-BLOCK] 大纲/主线.md 不存在")

    # 检查至少一个角色
    chars = _list_character_files()
    if not chars:
        issues.append("[H1-BLOCK] 02_人物/ 下无任何实际角色文件（仅有模板/索引）")

    # 检查 style-locked.md 有实质内容（视角/时态段已选定）
    if STYLE_LOCKED_FILE.exists():
        if not _body_has_content(STYLE_LOCKED_FILE):
            issues.append("[H1-BLOCK] docs/style-locked.md 视角/时态段仍为待选择，缺少实质内容")
    else:
        issues.append("[H1-BLOCK] docs/style-locked.md 不存在")

    # 内容文件缺失时提示从模板生成（单分支 + 内容不入库，新克隆需要 init）
    if any("不存在" in i for i in issues):
        issues.append("[INFO] 内容文件缺失可从模板生成：python scripts/template.py init")

def check_chapters(chapter_files: list[Path], issues: list, context_files: list | None = None):
    """D3: 章节 frontmatter 完整性 + 时空一致性。

    context_files: 只读种子章节（如已提交的旧章节）。仅用于填充时空表以检测
    跨 commit 的"同日两地"冲突，不对其本身做 frontmatter 校验、不产出 issue。
    """
    chars = _list_character_files()
    # 构建角色 status 映射
    char_status = {}
    for name, fpath in chars.items():
        fm = _parse_frontmatter(fpath)
        if fm:
            char_status[name] = fm.get("status", "alive")

    # {in_world_date: {角色: location}}
    spacetime: dict[str, dict[str, str]] = defaultdict(dict)
    # 时序检测用：(volume, chapter, date, path, 是否本次受检)
    dated: list[tuple[int, int, str, Path, bool]] = []

    def _vc(fm: dict) -> tuple[int, int]:
        try:
            return int(fm.get("volume", 0)), int(fm.get("chapter", 0))
        except (TypeError, ValueError):
            return 0, 0

    # 只读种子：已提交章节，建立既有时空占用（不报其自身 issue）
    for cf in sorted(context_files or []):
        fm = _parse_frontmatter(cf)
        if not fm:
            continue
        loc = fm.get("location", "")
        date = fm.get("in_world_date", "")
        if date and loc:
            for c in _parse_characters_present(fm.get("characters_present")):
                spacetime[date].setdefault(c, loc)
        if date:
            v, ch = _vc(fm)
            dated.append((v, ch, date, cf, False))

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

        # 白名单豁免判据（封"沉默漏标"）：agent 章节须有 model；
        # 用户手写章节须显式 author: human，否则一律 BLOCK。
        if not fm.get("model") and fm.get("author", "") != "human":
            issues.append(
                f"[BLOCK] {cf.relative_to(ROOT)}: 缺 model 字段——agent 生成章节须标 "
                f"model/generated_at；用户手写章节须显式 author: human"
            )

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
        if date:
            v, ch = _vc(fm)
            dated.append((v, ch, date, cf, True))
        if date and loc:
            for c in present:
                if c in spacetime[date] and spacetime[date][c] != loc:
                    issues.append(
                        f"[BLOCK] {cf.relative_to(ROOT)}: 角色 '{c}' 在同一天({date})"
                        f" 出现在两个地点: '{spacetime[date][c]}' 和 '{loc}'"
                    )
                spacetime[date][c] = loc

    # 时序单调检测：按卷章排序后，相邻两章日期文字骨架相同且可解析时，
    # 后章日期数值序列小于前章 = 时间线倒流。骨架不同（改元/换纪月名）→ 跳过。
    dated.sort(key=lambda r: (r[0], r[1]))
    for prev, curr in zip(dated, dated[1:]):
        if not curr[4]:
            continue
        a, b = _date_parts(prev[2]), _date_parts(curr[2])
        if not a or not b or a[0] != b[0]:
            continue
        if b[1] < a[1]:
            issues.append(
                f"[BLOCK] {curr[3].relative_to(ROOT)}: 日期 '{curr[2]}' 早于"
                f" 前一章（第{prev[0]}卷第{prev[1]}章）的 '{prev[2]}'——时间线倒流"
            )

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
    context_files = None  # 只读时空种子（仅 --staged 模式填充）
    if args.files:
        chapter_files = [Path(f).resolve() for f in args.files if Path(f).exists()]
    elif args.staged:
        import subprocess
        result = subprocess.run(
            ["git", "-c", "core.quotepath=false", "diff", "--cached", "--name-only"],
            capture_output=True, text=True, cwd=str(ROOT),
            # git 输出 UTF-8 中文路径；不显式指定则按系统区域解码
            # （中文 Windows = GBK）→ UnicodeDecodeError，hook 里表现为脚本崩溃
            encoding="utf-8", errors="replace",
        )
        staged = result.stdout.strip().split("\n")
        chapter_files = [
            ROOT / f for f in staged
            if f.startswith("03_正文/") and Path(f).name.startswith("第")
            and Path(f).name.endswith("章.md")
        ]
        # 只读种子：已提交章节（不在本次暂存内），用于跨 commit 同日两地检测
        staged_set = set(chapter_files)
        context_files = [
            p for p in TEXT_DIR.rglob("第*章.md")
            if not any(x in p.name for x in ("_准备_", "_审查_", "_审查后_"))
            and p not in staged_set
        ]
    else:
        chapter_files = sorted(
            p for p in TEXT_DIR.rglob("第*章.md")
            if not any(x in p.name for x in ("_准备_", "_审查_", "_审查后_"))
        )

    if chapter_files:
        check_chapters(chapter_files, issues, context_files=context_files)

    # 过程文件位置：_准备_/_审查_/_审查后_ 必须在 第N卷/_工作/ 下，不与正文混放
    if TEXT_DIR.is_dir():
        misplaced = [
            p for p in TEXT_DIR.rglob("*.md")
            if any(x in p.name for x in ("_准备_", "_审查_", "_审查后_"))
            and p.parent.name != WORK_DIR
        ]
        for p in sorted(misplaced):
            rel = p.relative_to(ROOT).as_posix()
            issues.append(
                f"[WARN] 过程文件位置不对：{rel}\n"
                f"       应移入 {p.parent.relative_to(ROOT).as_posix()}/{WORK_DIR}/"
            )

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
