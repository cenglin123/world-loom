#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""模板骨架 ↔ 内容文件管理。

_模板/ 按原路径存放每个可填写文件的空白骨架。骨架与内容文件都入库、都有 git
历史，区别只在能不能对外分发（划分见 scripts/layers.py，闸门见 .githooks/pre-push）。

命令：
    check                     对照表：模板 → 内容文件是否存在、是否已填写
    init                      确保是 git 仓库（自动 git init），缺失的内容文件
                              从模板生成（绝不覆盖已存在文件），把 core.hooksPath
                              指向 .githooks 让钩子生效。**git init 是强制前置**——
                              没有 .git/ 时钩子挂载是空操作，enforcement 层裸奔。
    reset <路径...>           预览重置（不加 --force 只列出，不写入）
    reset --all --force       全部重置为模板 + 删除模板覆盖不到的内容层文件
                              （正文章节、角色卡、卷复盘、文风样本、已归档计划），
                              开新书用；旧内容仍在 git 历史里
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from layers import is_content  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
TPL_DIR = ROOT / "_模板"

# reset --all 的删除范围：这些前缀下「内容层且无模板覆盖」的文件会被清掉。
# 源码例外（各 README、_设计方法、人物模板、复盘协议）is_content 为 False，天然豁免。
EXTRA_DELETE_PREFIXES: tuple[str, ...] = (
    "00_世界观/", "01_大纲/", "02_人物/", "03_正文/", "04_伏笔/",
    "05_复盘/", "06_文风样本/", "docs/plans/",
)

# 判定「产物是否已被填写」——占位符特征。命中越少说明填得越多。
PLACEHOLDER_RE = re.compile(r"[（(]待填写|[（(]待填|[（(]待选择|[（(]示例")


def _templates() -> list[Path]:
    """_模板/ 下所有模板文件的相对路径（相对 _模板/），README.md 除外。"""
    if not TPL_DIR.is_dir():
        return []
    out = []
    for p in sorted(TPL_DIR.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(TPL_DIR)
        if rel.as_posix() == "README.md":
            continue
        out.append(rel)
    return out


def products() -> set[str]:
    """`init` 会生成的产物路径（仓库相对，posix 分隔）。

    这些路径属内容层，但源码层文档可以指向它们——下游跑完 init 就存在。
    """
    return {rel.as_posix() for rel in _templates()}


def extra_content_files() -> list[str]:
    """删除范围内的内容层文件中，无模板覆盖的那些——`reset --all` 要清掉的部分。

    正文章节、角色卡、卷复盘、文风样本、已归档计划等：它们不在 _模板/ 里，
    但属于"这本书"——开新书时重置模板产物不够，还得删掉这些才算内容清空。
    """
    prods = products()
    out = []
    for pre in EXTRA_DELETE_PREFIXES:
        d = ROOT / pre
        if not d.is_dir():
            continue
        for p in sorted(d.rglob("*")):
            if not p.is_file():
                continue
            rel = p.relative_to(ROOT).as_posix()
            if rel in prods or not is_content(rel):
                continue
            out.append(rel)
    return out


def _fill_state(target: Path) -> str:
    """产物的填写状态：missing / blank / filled。"""
    if not target.is_file():
        return "missing"
    try:
        text = target.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return "filled"
    return "blank" if PLACEHOLDER_RE.search(text) else "filled"


def cmd_check(_args) -> int:
    rels = _templates()
    if not rels:
        print("[FAIL] _模板/ 下没有模板文件")
        return 1
    label = {"missing": "缺失（跑 init 生成）", "blank": "空白骨架", "filled": "已填写"}
    missing = 0
    print(f"{'模板 → 产物':<44} 状态")
    print("-" * 68)
    for rel in rels:
        state = _fill_state(ROOT / rel)
        missing += state == "missing"
        print(f"{rel.as_posix():<44} {label[state]}")
    print("-" * 68)
    if missing:
        print(f"[INFO] {missing} 个产物文件缺失——`python scripts/template.py init` 可从模板生成")
    else:
        print("[PASS] 模板覆盖的产物文件均已存在")
    return 0


def enable_git_hooks() -> tuple[bool, str | None]:
    """把 core.hooksPath 指向 .githooks，返回 (是否成功, 结果说明)。

    全新 clone 的 core.hooksPath 是空的，git 只看 .git/hooks/——仓库里带的三个
    钩子（提交前校验、治理标记、推送闸门）于是一个都不跑，而文档却按"生效"在
    引用它们。init 是用户的第一个动作，在这里挂载。

    已有配置不覆盖：那是用户或别的工具有意设的，动它可能拆掉人家的东西。
    """
    hooks_dir = ROOT / ".githooks"
    if not hooks_dir.is_dir():
        return False, ".githooks/ 目录不存在"
    try:
        proc = subprocess.run(
            ["git", "config", "--local", "core.hooksPath"],
            cwd=ROOT, capture_output=True, timeout=10,
            text=True, encoding="utf-8", errors="replace",
        )
    except subprocess.TimeoutExpired:
        return False, "读取 core.hooksPath 超时（10 秒）"
    except OSError as exc:
        return False, f"读取 core.hooksPath 失败：{exc}"
    # rc=0 表示键存在；rc=1 + 空输出是「键未设置」——全新仓库默认就是这样。
    current = proc.stdout.strip() if proc.returncode == 0 else ""
    if proc.returncode != 0 and (proc.stderr or "").strip():
        return False, f"读取 core.hooksPath 失败：{(proc.stderr or proc.stdout).strip()}"
    if current == ".githooks":
        return True, None
    if current:
        return True, (f"[INFO] core.hooksPath 已指向 {current}（非 .githooks），保持不动——"
                      f"如需启用本仓钩子：git config core.hooksPath .githooks")
    try:
        done = subprocess.run(
            ["git", "config", "--local", "core.hooksPath", ".githooks"],
            cwd=ROOT, capture_output=True, timeout=10,
            text=True, encoding="utf-8", errors="replace",
        )
    except subprocess.TimeoutExpired:
        return False, "写入 core.hooksPath 超时（10 秒）"
    except OSError as exc:
        return False, f"写入 core.hooksPath 失败：{exc}"
    if done.returncode != 0:
        return False, f"写入 core.hooksPath 失败：{(done.stderr or done.stdout).strip()}"
    try:
        verify = subprocess.run(
            ["git", "config", "--local", "core.hooksPath"],
            cwd=ROOT, capture_output=True, timeout=10,
            text=True, encoding="utf-8", errors="replace",
        )
    except subprocess.TimeoutExpired:
        return False, "复核 core.hooksPath 超时（10 秒）"
    except OSError as exc:
        return False, f"复核 core.hooksPath 失败：{exc}"
    if verify.returncode != 0:
        return False, f"复核 core.hooksPath 失败：{(verify.stderr or verify.stdout).strip()}"
    actual = verify.stdout.strip()
    if actual != ".githooks":
        return False, f"复核失败：core.hooksPath 实为 {actual or '未设置'}，与写入值 .githooks 不一致"
    return True, "[OK] 已启用仓库钩子（core.hooksPath → .githooks）：提交前校验、治理标记、推送闸门现在生效"


def ensure_git_repo() -> tuple[bool, str | None]:
    """确保 ROOT 是 git 仓库——钩子挂载要求 .git/ 存在。

    release zip 由 `git archive template-dist` 产生，不含 .git/。若不解压
    后跑 git init 就直接 template.py init：
    - 模板产物照常生成（init_missing 不依赖 git）
    - enable_git_hooks 静默失败（`git config` 在非仓库上无 op）
    - 用户看到「已生成 XX」+「无任何钩子提示」，以为生效
    - 实际：pre-commit / commit-msg / pre-push 三个钩子全部裸奔——enforcement
      层从源头上关掉，比 update 机制任何漏洞都更基础。

    因此 init 是 git init 的强制前置。

    返回 (ok, 信息消息)。ok=False 时调用方应中止（enforcement 已无意义）。
    """
    if (ROOT / ".git").exists():
        return True, None  # 已经是仓库，不动
    try:
        proc = subprocess.run(
            ["git", "init", "-q"],
            cwd=ROOT, capture_output=True, timeout=10,
            text=True, encoding="utf-8", errors="replace",
        )
    except FileNotFoundError:
        return False, "[FAIL] git 未安装。请安装 git 后重试 template.py init。"
    except subprocess.TimeoutExpired:
        return False, "[FAIL] git init 超时（10 秒）。请稍后再试。"
    if proc.returncode != 0:
        return False, f"[FAIL] git init 失败：{(proc.stderr or proc.stdout).strip()}"
    return True, "[OK] 已 git init（此前是裸目录；钩子挂载现在生效）"


def init_missing() -> list[str]:
    """把 _模板/ 下缺失的产物补齐（绝不覆盖已存在文件），返回新建清单。

    无副作用以外的输出——供 update.py 复用：升级后补新版新增的模板。
    cmd_init 负责打印与挂载钩子，这里只做文件复制。
    """
    created = []
    for rel in _templates():
        target = ROOT / rel
        if target.exists():
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(TPL_DIR / rel, target)
        created.append(rel.as_posix())
    return created


def cmd_init(_args) -> int:
    # git init 是强制前置：没有 .git/ 时钩子挂载是空操作，
    # 整个 enforcement 层会裸奔。
    ok, info = ensure_git_repo()
    if info:
        print(info)
    if not ok:
        return 1  # 不继续生成产物——enforcement 已失败，沉默继续更危险

    created = init_missing()
    if created:
        print("[OK] 从模板生成：")
        for c in created:
            print(f"  + {c}")
    else:
        print("[OK] 无缺失产物，未改动任何文件")
    hooks = enable_git_hooks()
    if hooks[1]:
        print(hooks[1])
    if not hooks[0]:
        print(f"[FAIL] 钩子挂载失败：{hooks[1]}")
        return 1
    return 0


def cmd_reset(args) -> int:
    rels = _templates()
    if args.all:
        targets = rels
    else:
        wanted = {Path(p).as_posix().lstrip("./") for p in args.paths}
        known = {r.as_posix() for r in rels}
        unknown = wanted - known
        if unknown:
            print("[FAIL] 以下路径没有对应模板：")
            for u in sorted(unknown):
                print(f"  ? {u}")
            print("可重置的路径见 `python scripts/template.py check`")
            return 1
        targets = [r for r in rels if r.as_posix() in wanted]

    if not targets:
        print("[FAIL] 未指定要重置的文件（用 --all 或给出路径）")
        return 1

    extras = extra_content_files() if args.all else []

    print("将被模板覆盖的文件：")
    for rel in targets:
        state = _fill_state(ROOT / rel)
        warn = "  ← 已填写，内容将丢失" if state == "filled" else ""
        print(f"  {rel.as_posix()}{warn}")
    if extras:
        print("将被删除的文件（模板覆盖不到的内容层产物）：")
        for rel in extras:
            print(f"  - {rel}")

    if not args.force:
        print("\n[DRY-RUN] 未写入任何文件。确认无误后加 --force 真正执行。")
        return 0

    for rel in targets:
        target = ROOT / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(TPL_DIR / rel, target)
    print(f"\n[OK] 已重置 {len(targets)} 个文件为模板状态")
    for rel in extras:
        (ROOT / rel).unlink()
    # 清理删空了的目录（保留有内容的）
    for pre in EXTRA_DELETE_PREFIXES:
        d = ROOT / pre
        if not d.is_dir():
            continue
        for sub in sorted((p for p in d.rglob("*") if p.is_dir()),
                          key=lambda p: len(p.parts), reverse=True):
            try:
                sub.rmdir()
            except OSError:
                pass
    if extras:
        print(f"[OK] 已删除 {len(extras)} 个模板覆盖不到的内容层文件")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="模板层 ↔ 内容层管理（_模板/ 是源码，同路径产物在 .gitignore 中）"
    )
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("check", help="对照表：模板 → 产物是否存在、是否已填写")
    sub.add_parser("init", help="缺失的产物从模板生成（不覆盖已存在文件）")

    p_reset = sub.add_parser("reset", help="用模板覆盖产物（默认 dry-run）")
    p_reset.add_argument("paths", nargs="*", help="要重置的产物路径，如 01_大纲/主线.md")
    p_reset.add_argument("--all", action="store_true", help="重置模板覆盖的全部文件")
    p_reset.add_argument("--force", action="store_true", help="真正写入（否则只预览）")

    args = parser.parse_args(argv)
    if args.cmd == "check":
        return cmd_check(args)
    if args.cmd == "init":
        return cmd_init(args)
    if args.cmd == "reset":
        return cmd_reset(args)
    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main(sys.argv[1:]))
