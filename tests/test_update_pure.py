#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""update.py 纯函数测试——版本号解析与 zip 包裹目录检测。

update.py 是 release 包的**消费端**：release.py 打的 zip 与 GitHub 自动
Source code zip 的结构差异，全靠 detect_prefix 区分。这对契约一旦错位，
用户更新时就会解错目录。
"""
from __future__ import annotations

import pytest

from update import detect_prefix, parse_version


@pytest.mark.parametrize("s,expected", [
    ("0.2.0", (0, 2, 0)),
    ("v0.2.0", (0, 2, 0)),
    (" 0.10.3 ", (0, 10, 3)),
    ("1.2.3", (1, 2, 3)),
])
def test_parse_version_ok(s: str, expected: tuple[int, int, int]):
    assert parse_version(s) == expected


@pytest.mark.parametrize("s", ["", "0.2", "a.b.c", "0.2.0.1", "v1.2"])
def test_parse_version_bad(s: str):
    with pytest.raises(ValueError):
        parse_version(s)


def test_detect_prefix_flat_release_zip():
    # release.py 打的包：顶层就是源码层文件，无包裹目录
    names = ["VERSION", "AGENTS.md", "scripts/layers.py", "_模板/README.md"]
    assert detect_prefix(names) == ""


def test_detect_prefix_wrapped_source_code():
    # GitHub 自动 Source code：带一层 world-loom-x.y.z/ 包裹
    names = ["world-loom-0.2.0/VERSION", "world-loom-0.2.0/AGENTS.md",
             "world-loom-0.2.0/scripts/layers.py"]
    assert detect_prefix(names) == "world-loom-0.2.0/"


def test_detect_prefix_known_root_not_wrapped():
    # 顶层就是已知根目录名 → 不是包裹目录
    assert detect_prefix(["scripts/layers.py", "scripts/publish.py"]) == ""


def test_detect_prefix_multiple_tops_not_wrapped():
    # 多个顶层目录 → 无法判定包裹，返回空前缀
    assert detect_prefix(["a/x", "b/y"]) == ""
