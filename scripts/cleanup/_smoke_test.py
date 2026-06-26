"""Smoke test for strip_comments_and_logs.

Builds synthetic snippets in every supported language, runs the cleaner,
asserts that semantic content (docstrings, doc-comments, directives,
licence headers, structured logging, console.warn/error, string literals
containing comment-like characters) is preserved, and that noise is gone.
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parents[2]))

from scripts.cleanup.strip_comments_and_logs import (
    clean_go,
    clean_python,
    clean_rust,
    clean_typescript,
)


def _check(name: str, must_keep: list[str], must_drop: list[str], cleaned: str) -> None:
    for needle in must_keep:
        assert needle in cleaned, f"[{name}] LOST: {needle!r}\nCLEANED:\n{cleaned}"
    for needle in must_drop:
        assert needle not in cleaned, f"[{name}] KEPT: {needle!r}\nCLEANED:\n{cleaned}"
    print(f"  ok: {name}")


def test_python() -> None:
    src = '''#!/usr/bin/env python
# SPDX-License-Identifier: MIT
"""Module docstring stays."""

from __future__ import annotations

import os  # type: ignore[import]


def greet(name: str) -> str:
    """Return a greeting (docstring stays)."""
    x = "value with # inside"
    y = f"hash inside f-string #{name}"
    print("debug noise should go")
    return f"hi {name}"


# banner line below
# =================
# TODO: drop me
def main() -> None:
    # inline note removed
    greet("world")  # trailing comment removed


if __name__ == "__main__":
    print("CLI output is preserved")
'''
    cleaned, removed = clean_python(src, strip_bare_print=True)
    _check(
        "python",
        must_keep=[
            "#!/usr/bin/env python",
            "# SPDX-License-Identifier: MIT",
            '"""Module docstring stays."""',
            '"""Return a greeting (docstring stays)."""',
            "# type: ignore[import]",
            '"value with # inside"',
            "f\"hash inside f-string",
            'print("CLI output is preserved")',
        ],
        must_drop=[
            'print("debug noise should go")',
            "# banner line below",
            "# =================",
            "# TODO: drop me",
            "# inline note removed",
            "# trailing comment removed",
        ],
        cleaned=cleaned,
    )
    assert removed > 0


def test_rust() -> None:
    src = '''// SPDX-License-Identifier: MIT
//! Crate-level doc stays.

/// Outer doc stays.
pub fn hello() {
    // inline note dropped
    println!("debug log dropped");
    let s = "with // inside string";
    tracing::info!("kept");
    // SAFETY: this is preserved
    let p = 1;
    dbg!(p);
    // TODO: drop me
}
'''
    cleaned, removed = clean_rust(src)
    _check(
        "rust",
        must_keep=[
            "// SPDX-License-Identifier: MIT",
            "//! Crate-level doc stays.",
            "/// Outer doc stays.",
            '"with // inside string"',
            "tracing::info!",
            "// SAFETY: this is preserved",
        ],
        must_drop=[
            "// inline note dropped",
            'println!("debug log dropped")',
            "dbg!(p)",
            "// TODO: drop me",
        ],
        cleaned=cleaned,
    )
    assert removed > 0


def test_typescript() -> None:
    src = '''// SPDX-License-Identifier: MIT
/**
 * JSDoc stays.
 */
export function greet(name: string) {
  // inline note dropped
  const s = "with // inside string";
  console.log("debug log dropped");
  console.warn("important warn kept");
  console.error("important error kept");
  logger.info("structured log kept");
  // @ts-expect-error preserved
  // eslint-disable-next-line
  return name;
}
'''
    cleaned, removed = clean_typescript(src)
    _check(
        "typescript",
        must_keep=[
            "// SPDX-License-Identifier: MIT",
            "/**",
            "JSDoc stays.",
            '"with // inside string"',
            'console.warn("important warn kept")',
            'console.error("important error kept")',
            'logger.info("structured log kept")',
            "// @ts-expect-error preserved",
            "// eslint-disable-next-line",
        ],
        must_drop=[
            "// inline note dropped",
            'console.log("debug log dropped")',
        ],
        cleaned=cleaned,
    )
    assert removed > 0


def test_go() -> None:
    src = '''// SPDX-License-Identifier: MIT
//go:build linux

// Package widget does stuff.
package widget

import "fmt"

// Greet returns hi. Doc comment above func stays.
func Greet(name string) string {
    // inline note dropped
    fmt.Println("debug log dropped")
    s := "with // inside string"
    return s + name
}
'''
    cleaned, removed = clean_go(src)
    _check(
        "go",
        must_keep=[
            "// SPDX-License-Identifier: MIT",
            "//go:build linux",
            "// Package widget does stuff.",
            "// Greet returns hi. Doc comment above func stays.",
            '"with // inside string"',
        ],
        must_drop=[
            "// inline note dropped",
            'fmt.Println("debug log dropped")',
        ],
        cleaned=cleaned,
    )
    assert removed > 0


def test_rust_multiline_macro() -> None:
    src = '''pub fn x() {
    eprintln!(
        "multi-line {} {}",
        a,
        b,
    );
    println!(
        "another {}",
        c
    );
    let y = 1;
}
'''
    cleaned, removed = clean_rust(src)
    _check(
        "rust_multiline_macro",
        must_keep=["let y = 1;"],
        must_drop=[
            "eprintln!",
            "println!",
            '"multi-line {} {}"',
            '"another {}"',
            "    a,",
        ],
        cleaned=cleaned,
    )
    assert removed >= 6


def test_typescript_multiline_console() -> None:
    src = '''export function f() {
  console.log(
    "first",
    obj,
    nested.value,
  );
  const y = 1;
  console.warn("kept");
}
'''
    cleaned, removed = clean_typescript(src)
    _check(
        "typescript_multiline_console",
        must_keep=["const y = 1;", 'console.warn("kept")'],
        must_drop=["console.log(", '"first"', "nested.value"],
        cleaned=cleaned,
    )
    assert removed >= 4


def test_go_multiline_print() -> None:
    src = '''package x

// F does things.
func F() {
    fmt.Println(
        "first",
        "second",
    )
    y := 1
}
'''
    cleaned, removed = clean_go(src)
    _check(
        "go_multiline_print",
        must_keep=["// F does things.", "y := 1"],
        must_drop=["fmt.Println(", '"first"', '"second"'],
        cleaned=cleaned,
    )
    assert removed >= 3


if __name__ == "__main__":
    test_python()
    test_rust()
    test_typescript()
    test_go()
    test_rust_multiline_macro()
    test_typescript_multiline_console()
    test_go_multiline_print()
    print("ALL GREEN")
