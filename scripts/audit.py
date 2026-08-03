"""audit.py — 文档一致性机械检查 (token-light, read-only).

Checks that init-agent-docs initialized files have not rotted:
dead links, STRUCTURE index completeness, birth-record presence,
AGENTS.md line budget, sync health.

All subcommands are read-only — this tool never modifies files.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import layers  # noqa: E402
import template  # noqa: E402

# Convention: this script lives at <project_root>/scripts/audit.py.
ROOT = Path(__file__).resolve().parent.parent

MARKDOWN_LINK_RE = re.compile(r"\[([^\]]*)\]\(([^)]+)\)")
WIKILINK_RE = re.compile(r"!?\[\[([^\[\]]+)\]\]")
FENCED_BLOCK_RE = re.compile(r"```[\s\S]*?```", re.MULTILINE)
INLINE_CODE_RE = re.compile(r"`[^`]+`")
HTML_COMMENT_RE = re.compile(r"<!--[\s\S]*?-->")


def _strip_noise(text: str) -> str:
    """Remove fenced code blocks, inline code, and HTML comments."""
    text = FENCED_BLOCK_RE.sub("", text)
    text = INLINE_CODE_RE.sub("", text)
    text = HTML_COMMENT_RE.sub("", text)
    return text

# Root-level instruction files always checked.
_ROOT_DOC_FILES = [
    "AGENTS.md",
]

def _discover_doc_files() -> list[str]:
    """入库的全部 markdown。

    未入库的文件（`.claudian/` 等工作区）不参与——它们不是仓库的一部分，
    其中的链接指向别处是常态。
    """
    out = subprocess.run(
        ["git", "-c", "core.quotepath=false", "ls-files", "*.md"],
        cwd=ROOT, capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )
    if out.returncode != 0:
        return list(_ROOT_DOC_FILES)
    return sorted(f for f in out.stdout.splitlines() if f.strip())

MANIFEST_GLOBS = [
    "package.json",
    "pyproject.toml",
    "requirements.txt",
    "requirements*.txt",
    "setup.py",
    "setup.cfg",
    "go.mod",
    "Cargo.toml",
    "Gemfile",
    "composer.json",
    "pom.xml",
    "build.gradle",
    "build.gradle.kts",
]


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _lines(path: Path) -> list[str]:
    if not path.is_file():
        return []
    return _read(path).splitlines()


def _exists(rel: str) -> bool:
    return (ROOT / rel).is_file()


def _effective_dir(doc_rel: str) -> Path:
    """相对链接的解析基准目录——**内容落地后所在的目录**，不一定是文件当前位置。

    `_分发/README.md` 会被映射成根目录的 `README.md`，`_模板/docs/CURRENT.md`
    会被 init 生成到 `docs/`。按文件当前位置解析，这两类的相对链接全是假死链。
    """
    rel = doc_rel.replace("\\", "/")
    landed = layers.DIST_MAP.get(rel, (None,))[0]
    if landed is None and rel.startswith("_模板/"):
        landed = rel[len("_模板/"):]
    return (ROOT / landed).parent if landed else (ROOT / rel).parent


def _resolve(target: str, source_dir: Path) -> Path:
    """Resolve a markdown link target relative to the source file's directory.

    Per CommonMark spec, all paths are relative to the containing file except
    those starting with '/'. Absolute paths (/) are resolved against ROOT.
    """
    if target.startswith("/"):
        return (ROOT / target.lstrip("/")).resolve()
    return (source_dir / target).resolve()
# ---------------------------------------------------------------------------
# link extraction
# ---------------------------------------------------------------------------

def _extract_file_links(text: str) -> list[tuple[str, str, int]]:
    """Return (target_path, display_text, line_number) for every local file link.

    Strips code blocks, inline code, and HTML comments before extraction to
    avoid false positives from example links and commented-out references.
    Line numbers are preserved relative to the original text.
    """
    clean = _strip_noise(text)
    links: list[tuple[str, str, int]] = []
    for lineno, line in enumerate(clean.splitlines(), 1):
        for m in MARKDOWN_LINK_RE.finditer(line):
            target = m.group(2).strip()
            if target.startswith(("http://", "https://", "#")):
                continue
            links.append((target, m.group(1).strip(), lineno))
    return links


def _extract_wikilinks(text: str) -> list[tuple[str, int]]:
    """Return (target, line_number) for every `[[wikilink]]` and `![[embed]]`.

    Target keeps only the path part — the `|别名`, `#小节` 与结尾 `/` 都剥掉。
    表格里的别名写作 `\\|`，转义反斜杠先还原再切。
    """
    out: list[tuple[str, int]] = []
    for lineno, line in enumerate(_strip_noise(text).splitlines(), 1):
        for m in WIKILINK_RE.finditer(line):
            raw = m.group(1).replace("\\|", "|")
            target = raw.split("|")[0].split("#")[0].strip().rstrip("/")
            if target:
                out.append((target, lineno))
    return out


def _pending_init(rel: str, products: set[str]) -> bool:
    """目标由 `init` 生成——尚未生成不算断链。

    目录也算：`docs/plans/active/` 在 init 写进第一个产物时就存在了。
    """
    rel = rel.replace("\\", "/").rstrip("/")
    if rel in products:
        return True
    return any(p.startswith(rel + "/") for p in products)


def _is_product(resolved: Path, products: set[str]) -> bool:
    try:
        rel = resolved.relative_to(ROOT).as_posix()
    except ValueError:
        return False
    return _pending_init(rel, products)


def _index_by_name(docs: list[str]) -> dict[str, list[str]]:
    """basename（去 .md）→ 仓库相对路径，供无路径 wikilink 回退解析。"""
    idx: dict[str, list[str]] = {}
    for rel in docs:
        idx.setdefault(Path(rel).stem, []).append(rel)
    return idx


def _resolve_wikilink(target: str, by_name: dict[str, list[str]]) -> str | None:
    """Wikilink 按仓库根解析（Obsidian 约定），失败则回退唯一同名匹配。

    同名多份时判为无法解析——链接本身有歧义，猜一个只会掩盖问题。
    返回仓库相对路径（posix），解析不到返回 None。
    """
    for cand in (target, target + ".md"):
        p = ROOT / cand
        if p.is_file():
            return cand.replace("\\", "/")
        if p.is_dir():
            return cand.rstrip("/").replace("\\", "/")
    hits = by_name.get(Path(target).name, [])
    return hits[0] if len(hits) == 1 else None


# ---------------------------------------------------------------------------
# dead-links
# ---------------------------------------------------------------------------

def _check_dead_links() -> list[dict[str, Any]]:
    docs = _discover_doc_files()
    by_name = _index_by_name(docs)
    products = template.products()
    results: list[dict[str, Any]] = []

    for doc_rel in docs:
        path = ROOT / doc_rel
        if not path.is_file():
            continue
        source_dir = _effective_dir(doc_rel)
        text = _read(path)
        source_is_content = layers.is_content(doc_rel)

        for target, _label, lineno in _extract_file_links(text):
            resolved = _resolve(target, source_dir)
            exists = resolved.is_file() or resolved.is_dir() or _is_product(resolved, products)
            results.append({
                "kind": "dead_link",
                "status": "ok" if exists else "dead",
                "source": doc_rel, "line": lineno, "target": target,
            })

        for target, lineno in _extract_wikilinks(text):
            rel = _resolve_wikilink(target, by_name)
            if rel is None:
                # 产物尚未生成 ≠ 断链——下游 clone 跑 init 之前本就是空的
                status = "ok" if (_pending_init(target, products)
                                  or target + ".md" in products) else "dead"
            elif (not source_is_content
                  and layers.is_content(rel)
                  and rel not in products):
                status = "cross_layer"
            else:
                status = "ok"
            results.append({
                "kind": "dead_link",
                "status": status,
                "source": doc_rel, "line": lineno, "target": target,
            })
    return results


# ---------------------------------------------------------------------------
# structure
# ---------------------------------------------------------------------------

def _structure_table_links() -> list[tuple[str, str, int]]:
    """Parse STRUCTURE.md index table: return (rel_path, label, lineno)."""
    path = ROOT / "docs" / "STRUCTURE.md"
    if not path.is_file():
        return []
    entries: list[tuple[str, str, int]] = []
    in_table = False
    for lineno, line in enumerate(_lines(path), 1):
        stripped = line.strip()
        if stripped.startswith("|") and "---" not in stripped.replace(" ", ""):
            if not in_table:
                in_table = True
                continue
            for m in MARKDOWN_LINK_RE.finditer(line):
                target = m.group(2).strip()
                if target.startswith(("http://", "https://", "#")):
                    continue
                entries.append((target, m.group(1).strip(), lineno))
        elif in_table and not stripped.startswith("|"):
            in_table = False
    return entries


def _check_structure() -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []

    if not _exists("docs/STRUCTURE.md"):
        return results

    index_entries = _structure_table_links()
    indexed_paths = {e[0] for e in index_entries}

    # Check each indexed target exists.
    for target, _label, lineno in index_entries:
        if not _exists(target):
            results.append({
                "kind": "structure",
                "status": "missing",
                "source": "docs/STRUCTURE.md",
                "line": lineno,
                "target": target,
            })
        else:
            results.append({
                "kind": "structure",
                "status": "ok",
                "source": "docs/STRUCTURE.md",
                "line": lineno,
                "target": target,
            })

    # Check for orphan files in docs/ not in index.
    docs_dir = ROOT / "docs"
    if docs_dir.is_dir():
        for f in sorted(docs_dir.rglob("*.md")):
            rel = str(f.relative_to(ROOT)).replace("\\", "/")
            if rel in indexed_paths:
                continue
            # Skip plan files — they are transient by design.
            if rel.startswith("docs/plans/"):
                continue
            # Skip audit-checklist itself.
            if rel == "docs/audit-checklist.md":
                continue
            results.append({
                "kind": "structure",
                "status": "orphan",
                "source": "docs/STRUCTURE.md",
                "line": 0,
                "target": rel,
            })

    return results


# ---------------------------------------------------------------------------
# misc checks
# ---------------------------------------------------------------------------

def _check_birth_record() -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    found = False
    for candidate in [
        "docs/plans/completed/initialization.md",
        "docs/initialization.md",
    ]:
        if _exists(candidate):
            results.append({
                "kind": "birth_record",
                "status": "found",
                "path": candidate,
            })
            found = True
            break
    if not found:
        results.append({
            "kind": "birth_record",
            "status": "missing",
            "path": "docs/plans/completed/initialization.md or docs/initialization.md",
        })
    return results


def _check_line_budget() -> list[dict[str, Any]]:
    # 检查分发出去的那份——下游 agent 会话实际加载的是它，预算约束对它才有意义。
    p = ROOT / "_分发" / "AGENTS.md"
    if not p.is_file():
        return [{"kind": "line_budget", "status": "missing", "lines": 0, "words": 0}]
    text = _read(p)
    line_count = len(text.splitlines())
    word_count = len(text.split())
    lines_ok = line_count <= 200
    words_ok = word_count <= 400
    if lines_ok and words_ok:
        status = "ok"
    elif not lines_ok or not words_ok:
        status = "warn"
    return [{"kind": "line_budget", "status": status, "lines": line_count, "words": word_count}]


def _check_sync() -> list[dict[str, Any]]:
    script = ROOT / "scripts" / "agent_links.py"
    if not script.is_file():
        return [{"kind": "sync", "status": "skip", "detail": "agent_links.py not found"}]
    try:
        result = subprocess.run(
            [sys.executable, str(script), "check"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        return [{"kind": "sync", "status": "error", "detail": str(exc)}]
    status = "ok" if result.returncode == 0 else "broken"
    return [{"kind": "sync", "status": status, "detail": result.stdout.strip() or result.stderr.strip()}]


# ---------------------------------------------------------------------------
# memory
# ---------------------------------------------------------------------------

def _check_memory() -> list[dict[str, Any]]:
    """Check .agent/memory/ structure health.

    Small projects (no .agent/memory/ dir) are not an error — they skip.
    For projects with the directory, we verify:
    - MEMORY.md exists and is non-empty
    - AGENTS.md contains the pointer and inline section
    - Links in MEMORY.md resolve to existing files
    """
    results: list[dict[str, Any]] = []
    memory_dir = ROOT / ".agent" / "memory"

    # Small projects: memory dir absence is OK
    if not memory_dir.is_dir():
        results.append({
            "kind": "memory",
            "status": "skip",
            "detail": "No .agent/memory/ directory (small project or not enabled)",
        })
        return results

    # Check MEMORY.md exists
    mem_index = memory_dir / "MEMORY.md"
    if not mem_index.is_file():
        results.append({
            "kind": "memory",
            "status": "missing",
            "detail": ".agent/memory/MEMORY.md missing",
        })
        return results

    # Check MEMORY.md is not empty
    if mem_index.stat().st_size == 0:
        results.append({
            "kind": "memory",
            "status": "empty",
            "detail": ".agent/memory/MEMORY.md is empty",
        })

    # Check AGENTS.md contains memory pointer and inline section
    agents_md = ROOT / "AGENTS.md"
    if agents_md.is_file():
        content = _read(agents_md)
        if ".agent/memory/MEMORY.md" not in content:
            results.append({
                "kind": "memory",
                "status": "unlinked",
                "detail": "AGENTS.md missing pointer to .agent/memory/MEMORY.md",
            })
        if "## 项目记忆" not in content:
            results.append({
                "kind": "memory",
                "status": "unlinked",
                "detail": "AGENTS.md missing inline memory section",
            })

    # Check referenced memory files exist
    for target, _label, lineno in _extract_file_links(_read(mem_index)):
        resolved = _resolve(target, mem_index.parent)
        if not resolved.is_file():
            results.append({
                "kind": "memory",
                "status": "dead_link",
                "source": ".agent/memory/MEMORY.md",
                "line": lineno,
                "target": target,
            })

    if not results:
        results.append({
            "kind": "memory",
            "status": "ok",
            "detail": ".agent/memory/ structure healthy",
        })

    return results


# ---------------------------------------------------------------------------
# aggregate
# ---------------------------------------------------------------------------

def _run_all() -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    results.extend(_check_dead_links())
    results.extend(_check_structure())
    results.extend(_check_birth_record())
    results.extend(_check_line_budget())
    results.extend(_check_sync())
    results.extend(_check_memory())
    return results


# ---------------------------------------------------------------------------
# output
# ---------------------------------------------------------------------------

_STATUS_GLYPHS: dict[str, str] = {
    "ok":          "OK",
    "dead":        "DEAD",
    "cross_layer": "CROSS",
    "missing":     "MISS",
    "orphan":      "ORPHAN",
    "undocumented":"UNDOC",
    "warn":        "WARN",
    "found":       "FOUND",
    "broken":      "BROKEN",
    "error":       "ERROR",
    "skip":        "SKIP",
    "empty":       "EMPTY",
    "unlinked":    "UNLINK",
}


def _format_text(results: list[dict[str, Any]], verbose: bool = False) -> str:
    lines_out: list[str] = []
    for r in results:
        if not verbose and r["status"] in ("ok", "found"):
            continue
        glyph = _STATUS_GLYPHS.get(r["status"], r["status"].upper())
        kind = r["kind"]

        if kind == "dead_link":
            note = ""
            if r["status"] == "cross_layer":
                note = "  ← 源码层指向内容层，分发后必断"
            lines_out.append(
                f"[{glyph:<6}] {r['source']}:{r['line']} -> {r['target']}{note}"
            )
        elif kind == "structure":
            if r["status"] == "orphan":
                lines_out.append(
                    f"[{glyph:<6}] docs/STRUCTURE.md — not in index: {r['target']}"
                )
            elif r["status"] == "missing":
                lines_out.append(
                    f"[{glyph:<6}] docs/STRUCTURE.md:{r['line']} -> {r['target']} (file missing)"
                )
        elif kind == "birth_record":
            if r["status"] == "missing":
                lines_out.append(f"[{glyph:<6}] Birth record missing: {r['path']}")
            else:
                lines_out.append(f"[{glyph:<6}] Birth record: {r['path']}")
        elif kind == "line_budget":
            if r["status"] == "missing":
                lines_out.append("[MISS  ] AGENTS.md not found")
            elif r["status"] == "warn":
                lines_out.append(
                    f"[WARN   ] AGENTS.md: {r['lines']} lines / {r['words']} words (limit 200/400)"
                )
            else:
                lines_out.append(
                    f"[OK    ] AGENTS.md: {r['lines']} lines / {r['words']} words (limit 200/400)"
                )
        elif kind == "sync":
            if r["status"] == "broken":
                lines_out.append(f"[BROKEN ] AGENTS.md/CLAUDE.md/GEMINI.md out of sync")
            elif r["status"] == "error":
                lines_out.append(f"[ERROR  ] sync check failed: {r['detail']}")
            elif r["status"] == "skip":
                lines_out.append("[SKIP   ] sync check (agent_links.py unavailable)")
        elif kind == "memory":
            if r["status"] == "skip":
                lines_out.append("[SKIP   ] memory (no .agent/memory/ directory)")
            elif r["status"] == "ok":
                if verbose:
                    lines_out.append("[OK    ] memory structure healthy")
            elif r["status"] == "dead_link":
                lines_out.append(
                    f"[DEAD   ] {r['source']}:{r['line']} -> {r['target']}"
                )
            else:
                lines_out.append(f"[{glyph:<6}] memory: {r['detail']}")
    return "\n".join(lines_out)


# ---------------------------------------------------------------------------
# commands
# ---------------------------------------------------------------------------

def _cmd_check(args: argparse.Namespace) -> None:
    results = _run_all()
    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        print(_format_text(results, verbose=args.verbose))

    has_issues = any(r["status"] not in ("ok", "found", "skip") for r in results)
    if has_issues:
        raise SystemExit(1)


def _cmd_dead_links(args: argparse.Namespace) -> None:
    results = _check_dead_links()
    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        print(_format_text(results, verbose=args.verbose))
    if any(r["status"] != "ok" for r in results):
        raise SystemExit(1)


def _cmd_structure(args: argparse.Namespace) -> None:
    results = _check_structure()
    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        print(_format_text(results, verbose=args.verbose))
    if any(r["status"] != "ok" for r in results):
        raise SystemExit(1)
def _cmd_memory(args: argparse.Namespace) -> None:
    results = _check_memory()
    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        print(_format_text(results, verbose=args.verbose))
    if any(r["status"] not in ("ok", "skip") for r in results):
        raise SystemExit(1)


# ---------------------------------------------------------------------------
# cli
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="init-agent-docs document consistency mechanical checks"
    )
    sub = parser.add_subparsers(dest="command")

    p_check = sub.add_parser("check", help="Run all checks")
    p_check.add_argument("--json", action="store_true", help="Output JSON")
    p_check.add_argument("--verbose", action="store_true", help="Show OK entries")
    p_check.set_defaults(func=_cmd_check)

    p_dead = sub.add_parser("dead-links", help="Dead link check only")
    p_dead.add_argument("--json", action="store_true", help="Output JSON")
    p_dead.add_argument("--verbose", action="store_true", help="Show OK entries")
    p_dead.set_defaults(func=_cmd_dead_links)

    p_struct = sub.add_parser("structure", help="STRUCTURE index check only")
    p_struct.add_argument("--json", action="store_true", help="Output JSON")
    p_struct.add_argument("--verbose", action="store_true", help="Show OK entries")
    p_struct.set_defaults(func=_cmd_structure)

    p_mem = sub.add_parser("memory", help="Memory structure check only")
    p_mem.add_argument("--json", action="store_true", help="Output JSON")
    p_mem.add_argument("--verbose", action="store_true", help="Show OK entries")
    p_mem.set_defaults(func=_cmd_memory)

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        parser.print_help()
        raise SystemExit(1)
    args.func(args)


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    main(sys.argv[1:])
