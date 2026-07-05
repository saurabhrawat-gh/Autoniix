//! `openapi-dump` — write the gateway's OpenAPI 3.1 document to
//! `rust/gateway/openapi.json`.
//!
//! Story A1 / IM-188. This binary is invoked by CI (Story A5) to regenerate
//! `openapi.json` on every build; the file is checked into the repo so the
//! harness contract validator has a stable schema to validate against.
//!
//! Usage:
//! ```bash
//! cargo run -p gateway --bin openapi-dump
//! # writes rust/gateway/openapi.json (pretty-printed, deterministic)
//! ```
//!
//! Exits 1 on any error. The pretty-printed JSON is stable across runs so a
//! `git diff` after regeneration is meaningful.

use std::path::PathBuf;

use gateway::ApiDoc;
use utoipa::OpenApi;

fn main() -> Result<(), Box<dyn std::error::Error>> {
    // Resolve the output path relative to CARGO_MANIFEST_DIR so it works
    // regardless of the shell's cwd.
    let manifest_dir = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    let out_path = manifest_dir.join("openapi.json");

    let doc = ApiDoc::openapi();
    let json = doc.to_pretty_json()?;

    // Trailing newline for POSIX-friendly diffs.
    std::fs::write(&out_path, format!("{json}\n"))?;

    eprintln!(
        "wrote OpenAPI document ({} paths) to {}",
        doc.paths.paths.len(),
        out_path.display()
    );

    Ok(())
}
