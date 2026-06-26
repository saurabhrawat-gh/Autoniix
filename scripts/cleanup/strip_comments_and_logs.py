"""One-shot cleanup tool that strips inline comments and raw debug logs.

Scope:
    Strips developer-noise comments and raw debug-style logging calls from
    first-party source files while preserving every comment that carries
    semantic meaning to a compiler, linter, formatter, type checker, build
    system, security scanner or license tool.

What is removed:
    * ``//`` inline comments in TypeScript, JavaScript, Rust, Go
    * ``#`` inline comments in Python (NOT shebangs, NOT directive comments)
    * Banner-style ASCII separator comments (lines of only ``#``/``/``/``=``/``-``/``*``)
    * Whole-line ``TODO:``/``FIXME:``/``XXX:``/``HACK:``/``NOTE:`` comments
    * Raw debug logging:
        - ``console.log/debug/info/trace(...)``
        - ``println!``/``eprintln!``/``dbg!`` in Rust
        - ``fmt.Println``/``fmt.Printf`` in Go (only when statement-level)
        - Bare top-level ``print(...)`` statements in Python library code
          (skipped inside ``if __name__ == "__main__":`` blocks and CLI files)

What is preserved (allowlist):
    * Docstrings (Python triple-quoted module/function/class strings)
    * Rust outer/inner doc comments ``///`` and ``//!``
    * JSDoc blocks ``/** ... */`` and any other ``/* ... */`` block comments
    * Go doc comments directly above ``package``/``func``/``type``/``var``/``const``
    * License/SPDX headers (any comment within the first 30 lines containing
      ``SPDX``, ``Copyright``, ``License``)
    * Shebang lines
    * Directive/pragma comments:
        Python   ``# type: ignore``, ``# noqa``, ``# pragma:``, ``# pylint:``,
                 ``# fmt: off``/``on``, ``# isort:``, ``# mypy:``, ``# ruff:``
        TS/JS    ``// @ts-expect-error``, ``// @ts-ignore``, ``// @ts-nocheck``,
                 ``// eslint-disable*``, ``// biome-ignore``, ``// prettier-ignore``
        Rust     ``// SAFETY:``, ``// PERF:``, ``// FIXME(...)`` if scoped
        Go       ``//go:build``, ``//go:generate``, ``//go:embed``, ``//go:linkname``,
                 ``//go:noinline``, ``//nolint``
    * ``console.warn`` / ``console.error`` (load-bearing error signals)
    * Any call through a real logger: ``logger``, ``log``, ``tracing``,
      ``structlog``, ``loguru``, ``slog``, ``zap``, ``pino``

Design:
    Pure-text, regex-driven, idempotent. Run with ``--dry-run`` first; rerun
    without to apply. Backups are not written: rely on git.

Usage:
    python -m scripts.cleanup.strip_comments_and_logs --paths rust/ --dry-run
    python -m scripts.cleanup.strip_comments_and_logs --paths src/ services/
    python -m scripts.cleanup.strip_comments_and_logs --paths dashboard/src web/src
    python -m scripts.cleanup.strip_comments_and_logs --paths go/
"""

from __future__ import annotations

import argparse
import io
import re
import sys
import token
import tokenize
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable

REPO_ROOT = Path(__file__).resolve().parents[2]

EXCLUDED_DIR_NAMES: frozenset[str] = frozenset(
    {
        ".git",
        ".venv",
        "venv",
        "node_modules",
        "target",
        "dist",
        "build",
        ".next",
        ".turbo",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        "__pycache__",
        "gen",
        "generated",
        "site-packages",
    }
)

EXCLUDED_PATH_SUBSTRINGS: tuple[str, ...] = (
    "rust/gateway/src/generated/",
    "dashboard/src/generated/",
    "/migrations/",
    "/proto/",
    "/.devin/",
    "/.windsurf/",
    "/.claude/",
    "/observability/",
    "/traefik/",
    "scripts/cleanup/",
)

EXCLUDED_FILE_SUFFIXES: tuple[str, ...] = (
    ".pb.go",
    ".pb.ts",
    ".tonic.rs",
    "_pb.ts",
    ".min.js",
    ".bundle.js",
)


@dataclass
class Stats:
    files_scanned: int = 0
    files_changed: int = 0
    lines_removed: int = 0
    by_lang: dict[str, int] = field(default_factory=dict)

    def record(self, lang: str, removed: int) -> None:
        if removed > 0:
            self.files_changed += 1
            self.lines_removed += removed
            self.by_lang[lang] = self.by_lang.get(lang, 0) + removed


PY_PRESERVED_HASH_PREFIXES: tuple[str, ...] = (
    "#!",
    "# type:",
    "# noqa",
    "# pragma:",
    "# pylint:",
    "# fmt:",
    "# isort:",
    "# mypy:",
    "# ruff:",
    "# black:",
    "# flake8:",
    "# coding:",
    "# -*- coding",
    "# SPDX",
    "# Copyright",
    "# License",
)

TS_PRESERVED_SLASH_PREFIXES: tuple[str, ...] = (
    "// @ts-expect-error",
    "// @ts-ignore",
    "// @ts-nocheck",
    "// @ts-check",
    "// eslint-disable",
    "// eslint-enable",
    "// biome-ignore",
    "// prettier-ignore",
    "// SPDX",
    "// Copyright",
    "// License",
    "/// <reference",
)

RUST_PRESERVED_SLASH_PREFIXES: tuple[str, ...] = (
    "///",
    "//!",
    "// SAFETY:",
    "// PERF:",
    "// SPDX",
    "// Copyright",
    "// License",
)

GO_PRESERVED_SLASH_PREFIXES: tuple[str, ...] = (
    "//go:",
    "//nolint",
    "//lint:",
    "// SPDX",
    "// Copyright",
    "// License",
)

BANNER_CHARS = set("#/=*-_~")


def _is_banner(stripped: str) -> bool:
    if len(stripped) < 4:
        return False
    body = stripped.lstrip("#/* ").rstrip("*/ ")
    if not body:
        body = stripped
    return len(set(body)) <= 2 and all(c in BANNER_CHARS or c == " " for c in body)


def _is_todo_only(stripped: str) -> bool:
    upper = stripped.upper()
    for marker in ("TODO", "FIXME", "XXX", "HACK", "NOTE", "WIP"):
        if marker + ":" in upper or marker + "(" in upper:
            return True
    return False


def _starts_with_any(line: str, prefixes: Iterable[str]) -> bool:
    s = line.lstrip()
    return any(s.startswith(p) for p in prefixes)


def _split_code_and_inline_comment(
    line: str, comment_token: str, string_chars: tuple[str, ...] = ('"', "'", "`")
) -> tuple[str, str | None]:
    """Return (code_part, inline_comment_or_none) honouring strings.

    Naive but adequate: tracks single-char quote contexts and skips escapes.
    Does not understand TS template-literal nesting; safe because we only need
    to recognise inline comments, not parse strings perfectly.
    """
    i = 0
    n = len(line)
    in_str: str | None = None
    while i < n:
        ch = line[i]
        if in_str:
            if ch == "\\" and i + 1 < n:
                i += 2
                continue
            if ch == in_str:
                in_str = None
            i += 1
            continue
        if ch in string_chars:
            in_str = ch
            i += 1
            continue
        if line.startswith(comment_token, i):
            return line[:i], line[i:]
        i += 1
    return line, None


def _should_preserve_py_comment(comment: str, lineno: int) -> bool:
    s = comment.lstrip()
    if any(s.startswith(p) for p in PY_PRESERVED_HASH_PREFIXES):
        return True
    if lineno <= 30 and any(tok in comment for tok in ("SPDX", "Copyright", "License")):
        return True
    return False


_PY_BARE_PRINT_RE = re.compile(r"^\s*print\s*\(")
_PY_MAIN_GUARD_RE = re.compile(r"^\s*if\s+__name__\s*==\s*[\"']__main__[\"']\s*:")


def clean_python(text: str, *, strip_bare_print: bool = True) -> tuple[str, int]:
    """Strip inline ``#`` comments and (optionally) bare debug ``print()`` lines.

    Uses :mod:`tokenize` so that hashes inside string literals and f-strings
    are never misinterpreted as comments. Bare ``print()`` calls are removed
    only outside ``if __name__ == "__main__":`` blocks.
    """
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(text).readline))
    except (tokenize.TokenizeError, IndentationError, SyntaxError):
        return text, 0

    lines_to_drop: set[int] = set()
    comment_spans: list[tuple[int, int, int]] = []
    removed = 0

    for tok in tokens:
        if tok.type != token.COMMENT:
            continue
        lineno = tok.start[0]
        col = tok.start[1]
        comment_text = tok.string
        if _should_preserve_py_comment(comment_text, lineno):
            continue
        comment_spans.append((lineno, col, len(comment_text)))

    raw_lines = text.splitlines(keepends=True)
    line_map: dict[int, str] = {i + 1: raw_lines[i] for i in range(len(raw_lines))}

    for lineno, col, length in comment_spans:
        line = line_map.get(lineno)
        if line is None:
            continue
        before = line[:col]
        if before.strip() == "":
            lines_to_drop.add(lineno)
            removed += 1
        else:
            after = line[col + length :]
            newline = "\n" if line.endswith("\n") else ""
            stripped_after = after.rstrip("\n")
            new_line = before.rstrip()
            if stripped_after:
                new_line += stripped_after
            line_map[lineno] = new_line + newline

    if strip_bare_print:
        main_indent: int | None = None
        for i, raw in enumerate(raw_lines, start=1):
            lstripped = raw.lstrip()
            indent = len(raw) - len(lstripped)
            stripped = raw.strip()
            if main_indent is not None and stripped and indent <= main_indent:
                main_indent = None
            if main_indent is None and _PY_MAIN_GUARD_RE.match(stripped):
                main_indent = indent
                continue
            if main_indent is not None:
                continue
            if _PY_BARE_PRINT_RE.match(raw) and i not in lines_to_drop:
                if stripped.endswith(")") or stripped.endswith("),"):
                    line_map.pop(i, None)
                    lines_to_drop.add(i)
                    removed += 1

    out: list[str] = []
    for i in range(1, len(raw_lines) + 1):
        if i in lines_to_drop:
            continue
        if i in line_map:
            out.append(line_map[i])
    return "".join(out), removed


def _paren_balance_delta(text: str) -> int:
    """Return open-paren minus close-paren count, ignoring those inside
    single/double quotes. Approximation only; good enough to detect when a
    multi-line call expression has closed."""
    depth = 0
    in_str: str | None = None
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if in_str:
            if ch == "\\" and i + 1 < n:
                i += 2
                continue
            if ch == in_str:
                in_str = None
            i += 1
            continue
        if ch in ('"', "'", "`"):
            in_str = ch
            i += 1
            continue
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        i += 1
    return depth


def clean_slash_lang(
    text: str,
    *,
    preserved_prefixes: tuple[str, ...],
    strip_println_dbg: bool = False,
    strip_fmt_print: bool = False,
    strip_console_debug: bool = False,
    preserved_lines: set[int] | None = None,
) -> tuple[str, int]:
    """Common cleaner for TypeScript / JavaScript / Rust / Go.

    Preserves block comments ``/* ... */`` entirely (including JSDoc).
    Strips line comments ``//`` unless they match ``preserved_prefixes``.

    When ``strip_println_dbg`` or ``strip_fmt_print`` is set, a matched debug
    statement is removed in full even when it spans multiple lines: the
    consumer continues swallowing input until paren balance returns to zero.
    """
    lines = text.splitlines(keepends=True)
    out: list[str] = []
    removed = 0
    in_block_comment = False
    swallow_until_paren_close = 0

    i = 0
    n = len(lines)
    while i < n:
        raw = lines[i]
        stripped = raw.strip()

        if swallow_until_paren_close:
            swallow_until_paren_close += _paren_balance_delta(raw)
            removed += 1
            i += 1
            if swallow_until_paren_close <= 0:
                swallow_until_paren_close = 0
            continue

        if in_block_comment:
            out.append(raw)
            if "*/" in stripped:
                in_block_comment = False
            i += 1
            continue

        if "/*" in stripped and "*/" not in stripped[stripped.find("/*") + 2 :]:
            in_block_comment = True
            out.append(raw)
            i += 1
            continue

        if i < 30 and any(tok in raw for tok in ("SPDX", "Copyright", "License")):
            out.append(raw)
            i += 1
            continue

        if preserved_lines is not None and (i + 1) in preserved_lines:
            out.append(raw)
            i += 1
            continue

        if stripped.startswith("//"):
            if _starts_with_any(stripped, preserved_prefixes):
                out.append(raw)
                i += 1
                continue
            if _is_banner(stripped):
                removed += 1
                i += 1
                continue
            if _is_todo_only(stripped):
                removed += 1
                i += 1
                continue
            removed += 1
            i += 1
            continue

        if "//" in raw:
            code, comment = _split_code_and_inline_comment(raw.rstrip("\n"), "//")
            if comment is not None and not _starts_with_any(comment, preserved_prefixes):
                trailing_ws = "\n" if raw.endswith("\n") else ""
                cleaned = code.rstrip()
                if cleaned:
                    out.append(cleaned + trailing_ws)
                else:
                    removed += 1
                i += 1
                continue

        if strip_println_dbg and re.match(r"^\s*(println!|eprintln!|dbg!)\s*[\(\[]", raw):
            delta = _paren_balance_delta(raw)
            removed += 1
            i += 1
            if delta > 0:
                swallow_until_paren_close = delta
            continue

        if strip_fmt_print and re.match(r"^\s*fmt\.Print(ln|f)?\s*\(", raw):
            delta = _paren_balance_delta(raw)
            removed += 1
            i += 1
            if delta > 0:
                swallow_until_paren_close = delta
            continue

        if strip_console_debug and re.match(
            r"^\s*console\.(log|debug|info|trace)\s*\(", raw
        ):
            delta = _paren_balance_delta(raw)
            removed += 1
            i += 1
            if delta > 0:
                swallow_until_paren_close = delta
            continue

        out.append(raw)
        i += 1

    return "".join(out), removed


def clean_typescript(text: str) -> tuple[str, int]:
    return clean_slash_lang(
        text,
        preserved_prefixes=TS_PRESERVED_SLASH_PREFIXES,
        strip_console_debug=True,
    )


def clean_rust(text: str) -> tuple[str, int]:
    return clean_slash_lang(
        text,
        preserved_prefixes=RUST_PRESERVED_SLASH_PREFIXES,
        strip_println_dbg=True,
    )


_GO_DECL_RE = re.compile(r"^\s*(package|func|type|var|const)\b")


def _go_doc_comment_lines(text: str) -> set[int]:
    """Return 1-based line numbers of ``//`` comments that immediately precede
    a top-level Go declaration (the idiomatic position for doc comments).

    A doc-comment block is a contiguous run of ``//`` lines whose first
    non-comment, non-blank successor matches a declaration keyword.
    """
    lines = text.splitlines()
    doc_lines: set[int] = set()
    n = len(lines)
    i = 0
    while i < n:
        stripped = lines[i].lstrip()
        if stripped.startswith("//"):
            start = i
            while i < n and lines[i].lstrip().startswith("//"):
                i += 1
            j = i
            while j < n and not lines[j].strip():
                j += 1
            if j < n and _GO_DECL_RE.match(lines[j]):
                for k in range(start, i):
                    doc_lines.add(k + 1)
            continue
        i += 1
    return doc_lines


def clean_go(text: str) -> tuple[str, int]:
    return clean_slash_lang(
        text,
        preserved_prefixes=GO_PRESERVED_SLASH_PREFIXES,
        strip_fmt_print=True,
        preserved_lines=_go_doc_comment_lines(text),
    )


LANG_HANDLERS: dict[str, Callable[[str, Path], tuple[str, int]]] = {
    ".py": lambda t, p: clean_python(t, strip_bare_print=_should_strip_bare_print(p)),
    ".ts": lambda t, _p: clean_typescript(t),
    ".tsx": lambda t, _p: clean_typescript(t),
    ".js": lambda t, _p: clean_typescript(t),
    ".jsx": lambda t, _p: clean_typescript(t),
    ".rs": lambda t, _p: clean_rust(t),
    ".go": lambda t, _p: clean_go(t),
}


def _should_strip_bare_print(path: Path) -> bool:
    parts = set(path.parts)
    if "tests" in parts or "scripts" in parts:
        return False
    name = path.name
    if name.startswith("test_") or name.endswith("_test.py") or name == "conftest.py":
        return False
    return True


def _should_skip(path: Path) -> bool:
    parts = set(path.parts)
    if parts & EXCLUDED_DIR_NAMES:
        return True
    spath = str(path).replace("\\", "/")
    if any(sub in spath for sub in EXCLUDED_PATH_SUBSTRINGS):
        return True
    if any(spath.endswith(suf) for suf in EXCLUDED_FILE_SUFFIXES):
        return True
    return False


def iter_target_files(roots: list[Path]) -> Iterable[Path]:
    for root in roots:
        if root.is_file():
            if not _should_skip(root) and root.suffix in LANG_HANDLERS:
                yield root
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix not in LANG_HANDLERS:
                continue
            if _should_skip(path):
                continue
            yield path


def process_file(path: Path, *, dry_run: bool) -> int:
    handler = LANG_HANDLERS[path.suffix]
    try:
        original = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return 0
    new_text, removed = handler(original, path)
    if removed == 0 or new_text == original:
        return 0
    if not dry_run:
        path.write_text(new_text, encoding="utf-8")
    return removed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="strip_comments_and_logs",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--paths",
        nargs="+",
        required=True,
        help="One or more files or directories to process (relative to repo root or absolute).",
    )
    parser.add_argument("--dry-run", action="store_true", help="Report changes without writing.")
    parser.add_argument("--quiet", action="store_true", help="Suppress per-file output.")
    args = parser.parse_args(argv)

    roots: list[Path] = []
    for raw in args.paths:
        p = Path(raw)
        if not p.is_absolute():
            p = (REPO_ROOT / raw).resolve()
        if not p.exists():
            print(f"warn: path does not exist: {p}", file=sys.stderr)
            continue
        roots.append(p)

    stats = Stats()
    for f in iter_target_files(roots):
        stats.files_scanned += 1
        removed = process_file(f, dry_run=args.dry_run)
        if removed:
            stats.record(f.suffix, removed)
            if not args.quiet:
                rel = f.relative_to(REPO_ROOT) if str(f).startswith(str(REPO_ROOT)) else f
                print(f"  {rel}: -{removed}")

    mode = "DRY-RUN" if args.dry_run else "APPLIED"
    print(
        f"[{mode}] scanned={stats.files_scanned} changed={stats.files_changed} "
        f"lines_removed={stats.lines_removed} by_lang={stats.by_lang}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
