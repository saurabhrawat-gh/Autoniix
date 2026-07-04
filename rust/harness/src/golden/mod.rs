//! Golden-file regression suite — Python ↔ Rust endpoint parity.
//!
//! Captures Python v2 responses and replays them against the Rust gateway
//! to verify response shape equivalence without requiring both services live.
//!
//! Directory layout:
//!   tests/golden/<tag>/<endpoint-slug>.json
//!
//! Each fixture JSON schema:
//! ```json
//! {
//!   "method": "GET",
//!   "path": "/api/v2/auth/mode",
//!   "status": 200,
//!   "body": { "mode": "email" },
//!   "ignore_fields": ["created_at", "updated_at", "id"]
//! }
//! ```
//!
//! Per HARNESS-ENGINEERING-PLAN.md §A4.

use anyhow::Result;
use serde_json::Value;
use std::path::PathBuf;

/// A single captured golden fixture.
#[derive(Debug, Clone)]
pub struct GoldenFixture {
    pub method: String,
    pub path: String,
    pub request_body: Option<Value>,
    pub status: u16,
    pub body: Value,
    pub ignore_fields: Vec<String>,
}

/// Replays golden fixtures against a live Rust gateway.
pub struct GoldenReplay {
    pub fixtures_dir: PathBuf,
    client: reqwest::Client,
}

impl GoldenReplay {
    pub fn new(fixtures_dir: impl Into<PathBuf>) -> Self {
        Self {
            fixtures_dir: fixtures_dir.into(),
            client: reqwest::Client::new(),
        }
    }

    /// Default: `tests/golden/` two levels above `CARGO_MANIFEST_DIR`
    /// (i.e. repo-root/tests/golden/).
    pub fn default_for_tests() -> Self {
        let dir = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .parent()
            .unwrap_or(&PathBuf::from("."))
            .parent()
            .unwrap_or(&PathBuf::from("."))
            .join("tests")
            .join("golden");
        Self::new(dir)
    }

    /// Load a fixture from `<fixtures_dir>/<name>.json`.
    pub fn load(&self, name: &str) -> Result<GoldenFixture> {
        let path = self.fixtures_dir.join(format!("{name}.json"));
        let content = std::fs::read_to_string(&path)
            .map_err(|e| anyhow::anyhow!("golden fixture '{}' not found: {}", path.display(), e))?;
        let v: Value = serde_json::from_str(&content)?;

        Ok(GoldenFixture {
            method: v["method"].as_str().unwrap_or("GET").to_string(),
            path: v["path"].as_str().unwrap_or("").to_string(),
            request_body: if v["request_body"].is_null() {
                None
            } else {
                Some(v["request_body"].clone())
            },
            status: v["status"].as_u64().unwrap_or(200) as u16,
            body: v["body"].clone(),
            ignore_fields: v["ignore_fields"]
                .as_array()
                .unwrap_or(&vec![])
                .iter()
                .filter_map(|s| s.as_str().map(str::to_string))
                .collect(),
        })
    }

    /// Save a fixture to disk (called from the capture script).
    pub fn save(&self, name: &str, fixture: &GoldenFixture) -> Result<()> {
        std::fs::create_dir_all(&self.fixtures_dir)?;
        let path = self.fixtures_dir.join(format!("{name}.json"));
        let v = serde_json::json!({
            "method": fixture.method,
            "path": fixture.path,
            "request_body": fixture.request_body,
            "status": fixture.status,
            "body": fixture.body,
            "ignore_fields": fixture.ignore_fields,
        });
        std::fs::write(path, serde_json::to_string_pretty(&v)?)?;
        Ok(())
    }

    /// Replay a single fixture against `base_url`.
    /// Returns `Ok(())` if status + body match; `Err` with diff on mismatch.
    pub async fn replay(
        &self,
        base_url: &str,
        name: &str,
        auth_token: Option<&str>,
    ) -> Result<()> {
        let fixture = self.load(name)?;
        let url = format!("{}{}", base_url.trim_end_matches('/'), fixture.path);

        let mut req_builder = match fixture.method.to_uppercase().as_str() {
            "POST" => self
                .client
                .post(&url)
                .json(fixture.request_body.as_ref().unwrap_or(&Value::Null)),
            "PUT" => self
                .client
                .put(&url)
                .json(fixture.request_body.as_ref().unwrap_or(&Value::Null)),
            "DELETE" => self.client.delete(&url),
            "PATCH" => self
                .client
                .patch(&url)
                .json(fixture.request_body.as_ref().unwrap_or(&Value::Null)),
            _ => self.client.get(&url),
        };
        if let Some(token) = auth_token {
            req_builder = req_builder.bearer_auth(token);
        }

        let resp = req_builder
            .send()
            .await
            .map_err(|e| anyhow::anyhow!("replay '{}': request failed: {}", name, e))?;

        let actual_status = resp.status().as_u16();
        let actual_body: Value = resp.json().await.unwrap_or(Value::Null);

        if actual_status != fixture.status {
            anyhow::bail!(
                "golden replay '{}': status mismatch — expected {}, got {}",
                name,
                fixture.status,
                actual_status
            );
        }

        let ignore: Vec<&str> = fixture.ignore_fields.iter().map(String::as_str).collect();
        let diffs = diff_values(&fixture.body, &actual_body, "", &ignore);
        if !diffs.is_empty() {
            anyhow::bail!(
                "golden replay '{}': body mismatch:\n{}",
                name,
                diffs.join("\n")
            );
        }

        Ok(())
    }

    /// Replay all fixtures in `fixtures_dir` (non-recursive).
    /// Returns a map of fixture name → error (if any).
    pub async fn replay_all(
        &self,
        base_url: &str,
        auth_token: Option<&str>,
    ) -> Vec<(String, String)> {
        let mut failures = Vec::new();
        for name in self.list() {
            if let Err(e) = self.replay(base_url, &name, auth_token).await {
                failures.push((name, e.to_string()));
            }
        }
        failures
    }

    /// List all fixture names (stem of *.json files) in `fixtures_dir`.
    pub fn list(&self) -> Vec<String> {
        if !self.fixtures_dir.exists() {
            return vec![];
        }
        let mut names: Vec<String> = std::fs::read_dir(&self.fixtures_dir)
            .ok()
            .into_iter()
            .flatten()
            .filter_map(|e| e.ok())
            .filter(|e| e.path().extension().and_then(|s| s.to_str()) == Some("json"))
            .filter_map(|e| {
                e.path()
                    .file_stem()
                    .and_then(|s| s.to_str())
                    .map(str::to_string)
            })
            .collect();
        names.sort();
        names
    }
}

/// Recursively diff two JSON values; returns human-readable mismatch lines.
fn diff_values(expected: &Value, actual: &Value, path: &str, ignore: &[&str]) -> Vec<String> {
    let mut out = Vec::new();
    match (expected, actual) {
        (Value::Object(exp), Value::Object(act)) => {
            for (k, ev) in exp {
                let p = if path.is_empty() {
                    k.clone()
                } else {
                    format!("{path}.{k}")
                };
                if ignore.contains(&k.as_str()) || ignore.contains(&p.as_str()) {
                    continue;
                }
                match act.get(k) {
                    None => out.push(format!("  missing field: {p}")),
                    Some(av) => out.extend(diff_values(ev, av, &p, ignore)),
                }
            }
        }
        _ if expected != actual => {
            out.push(format!("  {path}: expected {expected}, got {actual}"));
        }
        _ => {}
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn test_diff_equal_objects() {
        let a = json!({"status": "ok", "count": 3});
        let b = json!({"status": "ok", "count": 3});
        assert!(diff_values(&a, &b, "", &[]).is_empty());
    }

    #[test]
    fn test_diff_missing_field() {
        let a = json!({"status": "ok", "extra": "data"});
        let b = json!({"status": "ok"});
        let diffs = diff_values(&a, &b, "", &[]);
        assert_eq!(diffs.len(), 1);
        assert!(diffs[0].contains("extra"));
    }

    #[test]
    fn test_diff_ignored_field() {
        let a = json!({"status": "ok", "created_at": "2024-01-01"});
        let b = json!({"status": "ok", "created_at": "2025-06-01"});
        let diffs = diff_values(&a, &b, "", &["created_at"]);
        assert!(diffs.is_empty());
    }

    #[test]
    fn test_save_and_load_roundtrip() {
        let dir = tempfile::tempdir().unwrap();
        let replay = GoldenReplay::new(dir.path());
        let fixture = GoldenFixture {
            method: "GET".to_string(),
            path: "/api/v2/auth/mode".to_string(),
            request_body: None,
            status: 200,
            body: json!({"mode": "email"}),
            ignore_fields: vec![],
        };
        replay.save("auth_mode", &fixture).unwrap();
        let loaded = replay.load("auth_mode").unwrap();
        assert_eq!(loaded.method, "GET");
        assert_eq!(loaded.status, 200);
        assert_eq!(loaded.body, json!({"mode": "email"}));
    }
}
