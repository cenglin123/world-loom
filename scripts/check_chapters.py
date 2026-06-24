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

    # 检查大纲主线（不依赖具体标题名）
    if OUTLINE_FILE.exists():
        if not _body_has_content(OUTLINE_FILE):
            issues.append("[H1-BLOCK] 大纲/主线.md 主线一句话仍为'待填写'")
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
    context_files = None  # 只读时空种子（仅 --staged 模式填充）
    if args.files:
        chapter_files = [Path(f).resolve() for f in args.files if Path(f).exists()]
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
            and not any(x in f for x in ("_准备_", "_审查_", "_审查后_"))
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
