#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""B-2 regression：pre-commit 工作流痕迹 regex 必须覆盖非 `第X卷/` 的章节结构。

旧 regex `^03_正文/第.+卷/第[^/]+章\.md$` 太严：`03_正文/小样/第3章.md` 这类
非标准卷结构的工作流痕迹检查会被跳过——存在 BUG。
新 regex `^03_正文/.*/第[^/]+章\.md$` 放宽到 `03_正文/<dir>/第X章.md` 形状，
要求至少一个目录分隔符（防止 `03_正文/第X章.md` 这种顶级误命中），仍能
排除 README / `_工作/` 等非章节文件（它们不匹配 `第X章.md` 文件名）。
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

HOOK = Path(__file__).resolve().parent.parent / ".githooks" / "pre-commit"


def _extract_workflow_regex() -> re.Pattern[str]:
    """从 pre-commit 里抽出 §6 的章节 grep 模式。"""
    text = HOOK.read_text(encoding="utf-8")
    # 取 grep -E 后的双引号串；当前实现是 `TRUE_CHAPTERS=$(... grep -E "PATTERN" || true)`
    m = re.search(r'TRUE_CHAPTERS=\$\(echo "\$STAGED" \| grep -E "([^"]+)" \|\| true\)', text)
    assert m, "pre-commit 中未找到 TRUE_CHAPTERS 行（regex 已变？）"
    return re.compile(m.group(1))


PATTERN = _extract_workflow_regex()


@pytest.mark.parametrize("path", [
    "03_正文/第1卷/第1章.md",                       # 标准：必须命中
    "03_正文/第1卷/第12章.md",                      # 多位数章节
    "03_正文/小样/第3章.md",                        # 非标准卷结构（BUG 主战场）
    "03_正文/草稿/第0章.md",                        # 其他非卷子目录
    "03_正文/外传/第1章.md",                        # 外传结构
])
def test_workflow_regex_matches_real_chapters(path):
    """正则必须命中所有 `03_正文/<dir>/第X章.md` 形式的真章节。"""
    assert PATTERN.search(path), \
        f"工作流痕迹检查应命中 {path}（防止 enforcement 跳过）"


@pytest.mark.parametrize("path", [
    "03_正文/README.md",                            # 目录 README 不应命中
    "03_正文/_工作/_准备_第1章.md",                 # 过程文件不应命中
    "03_正文/_工作/_审查_第1章.md",                 # 同上
    "03_正文/_工作/_审查后_第1章.md",
    "README.md",                                    # 顶层 README
    "00_世界观/核心设定.md",                        # 世界观不在 03_正文/
])
def test_workflow_regex_excludes_non_chapter_files(path):
    """正则不应把过程文件 / README / 非 03_正文/ 当作真章节。"""
    assert not PATTERN.search(path), \
        f"工作流痕迹检查不应命中 {path}"