#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""layers.is_content 分类表驱动测试。

is_content 是防内容泄漏的**最底层不变量**——publish.py 剥哪些文件、
pre-push 闸门拦哪些文件，全由它决定。分类错一个路径，内容就可能外泄。
"""
from __future__ import annotations

import pytest

from layers import is_content

# 内容层 + 开发层：机制等同，都不分发
CONTENT = [
    "00_世界观/核心设定.md",
    "00_世界观/外围设定.md",
    "01_大纲/主线.md",
    "02_人物/某角色.md",
    "03_正文/第1卷/第1章.md",
    "04_伏笔/伏笔登记表.md",
    "05_复盘/第1卷_复盘.md",
    "06_文风样本/某样本.md",
    "docs/CURRENT.md",
    "docs/CHANGELOG.md",
    "docs/style-locked.md",
    "docs/decisions.md",
    "docs/plans/active/foo.md",
    "docs/plans/completed/bar.md",
    "docs/plans/deferred/baz.md",
    "docs/plans/README.md",
    "简介.md",
    # 开发层
    "AGENTS.md", "CLAUDE.md", "GEMINI.md", "README.md",
    "docs/development.md", "scripts/release.py",
    "tests/conftest.py", "tests/test_layers.py",
]

# 源码层：会随分发出去
SOURCE = [
    "scripts/layers.py", "scripts/publish.py", "scripts/update.py",
    "scripts/check_all.py", "scripts/template.py",
    "_模板/00_世界观/核心设定.md", "_模板/README.md",
    "_分发/AGENTS.md", "_分发/README.md",
    "VERSION", ".gitignore",
    "docs/workflow.md", "docs/writing-style.md", "docs/pitfalls.md",
    "docs/frontmatter-schemas.md", "docs/audit-checklist.md",
    "使用手册.md", "example_world/核心设定.md",
    # 内容目录里的源码层例外（README/模板/方法文档）
    "00_世界观/_设计方法.md", "01_大纲/README.md",
    "02_人物/README.md", "02_人物/人物模板.md",
    "03_正文/README.md", "04_伏笔/README.md",
    "05_复盘/README.md", "05_复盘/reviewer-protocol.md",
    "05_复盘/reviewer-prompt-template.md",
    "05_复盘/maintenance-executor.md", "05_复盘/复盘模板.md",
]


@pytest.mark.parametrize("path", CONTENT)
def test_content_paths(path: str):
    assert is_content(path), f"应为内容/开发层（不分发）：{path}"


@pytest.mark.parametrize("path", SOURCE)
def test_source_paths(path: str):
    assert not is_content(path), f"应为源码层（可分发）：{path}"


@pytest.mark.parametrize("path,expected", [
    ("00_世界观\\核心设定.md", True),   # Windows 分隔符归一
    ("./AGENTS.md", True),              # 前导 ./ 剥掉
    ("./scripts/layers.py", False),
])
def test_path_normalization(path: str, expected: bool):
    assert is_content(path) is expected
