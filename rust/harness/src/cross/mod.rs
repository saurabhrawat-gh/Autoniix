//! Cross-service equivalence testing — Python ↔ Rust ↔ Go.
//!
//! Verifies that two implementations of the same endpoint produce
//! semantically equivalent responses.  Does NOT require byte-identical
//! output; only asserts on the fields that matter for correctness.
//!
//! Per HARNESS-ENGINEERING-PLAN.md (locked: Rust for cross-service validation).

use anyhow::Result;
use reqwest::Client;
use serde_json::Value;
use thiserror::Error;
use tracing::{error, info};

#[derive(Debug, Error)]
pub enum EquivalenceError {
    #[error("HTTP error calling {service} {method} {path}: {cause}")]
    Http {
        service: String,
        method: String,
        path: String,
        cause: String,
    },

    #[error("Field '{field}' differs — service_a={a:?}, service_b={b:?}")]
    FieldMismatch { field: String, a: Value, b: Value },

    #[error("Response from {service} is not valid JSON")]
    InvalidJson { service: String },

    #[error("Status mismatch — service_a={a}, service_b={b}")]
    StatusMismatch { a: u16, b: u16 },
}

/// Result of an equivalence check.
#[derive(Debug)]
pub struct EquivalenceResult {
    pub equivalent: bool,
    pub mismatches: Vec<EquivalenceError>,
    pub service_a_body: Value,
    pub service_b_body: Value,
}

/// Configuration for a pair of services to compare.
pub struct ServicePair {
    pub service_a_name: String,
    pub service_a_base_url: String,
    pub service_b_name: String,
    pub service_b_base_url: String,
    pub client: Client,
}

impl ServicePair {
    pub fn new(
        service_a_name: impl Into<String>,
        service_a_base_url: impl Into<String>,
        service_b_name: impl Into<String>,
        service_b_base_url: impl Into<String>,
    ) -> Self {
        Self {
            service_a_name: service_a_name.into(),
            service_a_base_url: service_a_base_url.into(),
            service_b_name: service_b_name.into(),
            service_b_base_url: service_b_base_url.into(),
            client: Client::new(),
        }
    }

    /// Compare POST responses from two services on the same logical operation.
    ///
    /// `fields_to_compare` — list of top-level JSON field names that must match.
    /// Fields not in this list are ignored (e.g. timestamps, IDs that differ by design).
    pub async fn compare_post(
        &self,
        path_a: &str,
        path_b: &str,
        body_a: Value,
        body_b: Value,
        headers: Option<Vec<(String, String)>>,
        fields_to_compare: &[&str],
    ) -> Result<EquivalenceResult, EquivalenceError> {
        let (resp_a, status_a) = self
            .post(
                &self.service_a_base_url,
                path_a,
                body_a.clone(),
                headers.clone(),
            )
            .await
            .map_err(|e| EquivalenceError::Http {
                service: self.service_a_name.clone(),
                method: "POST".into(),
                path: path_a.to_string(),
                cause: e.to_string(),
            })?;

        let (resp_b, status_b) = self
            .post(&self.service_b_base_url, path_b, body_b.clone(), headers)
            .await
            .map_err(|e| EquivalenceError::Http {
                service: self.service_b_name.clone(),
                method: "POST".into(),
                path: path_b.to_string(),
                cause: e.to_string(),
            })?;

        self.compare_responses(resp_a, status_a, resp_b, status_b, fields_to_compare)
            .await
    }

    /// Compare GET responses from two services.
    pub async fn compare_get(
        &self,
        path: &str,
        headers: Option<Vec<(String, String)>>,
        fields_to_compare: &[&str],
    ) -> Result<EquivalenceResult, EquivalenceError> {
        let (resp_a, status_a) = self
            .get(&self.service_a_base_url, path, headers.clone())
            .await
            .map_err(|e| EquivalenceError::Http {
                service: self.service_a_name.clone(),
                method: "GET".into(),
                path: path.to_string(),
                cause: e.to_string(),
            })?;

        let (resp_b, status_b) = self
            .get(&self.service_b_base_url, path, headers)
            .await
            .map_err(|e| EquivalenceError::Http {
                service: self.service_b_name.clone(),
                method: "GET".into(),
                path: path.to_string(),
                cause: e.to_string(),
            })?;

        self.compare_responses(resp_a, status_a, resp_b, status_b, fields_to_compare)
            .await
    }

    async fn post(
        &self,
        base: &str,
        path: &str,
        body: Value,
        headers: Option<Vec<(String, String)>>,
    ) -> Result<(reqwest::Response, u16)> {
        let mut req = self.client.post(format!("{base}{path}")).json(&body);
        if let Some(hdrs) = headers {
            for (k, v) in hdrs {
                req = req.header(k, v);
            }
        }
        let resp = req.send().await?;
        let status = resp.status().as_u16();
        Ok((resp, status))
    }

    async fn get(
        &self,
        base: &str,
        path: &str,
        headers: Option<Vec<(String, String)>>,
    ) -> Result<(reqwest::Response, u16)> {
        let mut req = self.client.get(format!("{base}{path}"));
        if let Some(hdrs) = headers {
            for (k, v) in hdrs {
                req = req.header(k, v);
            }
        }
        let resp = req.send().await?;
        let status = resp.status().as_u16();
        Ok((resp, status))
    }

    async fn compare_responses(
        &self,
        resp_a: reqwest::Response,
        status_a: u16,
        resp_b: reqwest::Response,
        status_b: u16,
        fields_to_compare: &[&str],
    ) -> Result<EquivalenceResult, EquivalenceError> {
        let body_a: Value = resp_a
            .json()
            .await
            .map_err(|_| EquivalenceError::InvalidJson {
                service: self.service_a_name.clone(),
            })?;
        let body_b: Value = resp_b
            .json()
            .await
            .map_err(|_| EquivalenceError::InvalidJson {
                service: self.service_b_name.clone(),
            })?;

        let mut mismatches = Vec::new();

        // Check status codes match
        if status_a != status_b {
            mismatches.push(EquivalenceError::StatusMismatch {
                a: status_a,
                b: status_b,
            });
        }

        // Check specified fields match
        for field in fields_to_compare {
            let val_a = body_a.get(field).unwrap_or(&Value::Null);
            let val_b = body_b.get(field).unwrap_or(&Value::Null);

            if val_a != val_b {
                mismatches.push(EquivalenceError::FieldMismatch {
                    field: field.to_string(),
                    a: val_a.clone(),
                    b: val_b.clone(),
                });
            }
        }

        let equivalent = mismatches.is_empty();
        if equivalent {
            info!(
                service_a = %self.service_a_name,
                service_b = %self.service_b_name,
                fields = ?fields_to_compare,
                "equivalence check passed ✓"
            );
        } else {
            error!(
                service_a = %self.service_a_name,
                service_b = %self.service_b_name,
                mismatch_count = mismatches.len(),
                "equivalence check FAILED"
            );
        }

        Ok(EquivalenceResult {
            equivalent,
            mismatches,
            service_a_body: body_a,
            service_b_body: body_b,
        })
    }
}

/// Convenience: assert two services produce equivalent auth responses.
///
/// Checks that both signup endpoints return a valid JWT access_token
/// and a refresh_token, without requiring identical values (tokens
/// will always differ between services).
pub async fn assert_auth_token_structure(result: &EquivalenceResult) {
    assert!(
        result
            .service_a_body
            .get("access_token")
            .and_then(|v| v.as_str())
            .is_some(),
        "service_a missing access_token"
    );
    assert!(
        result
            .service_b_body
            .get("access_token")
            .and_then(|v| v.as_str())
            .is_some(),
        "service_b missing access_token"
    );
    assert!(
        result
            .service_a_body
            .get("refresh_token")
            .and_then(|v| v.as_str())
            .is_some(),
        "service_a missing refresh_token"
    );
    assert!(
        result
            .service_b_body
            .get("refresh_token")
            .and_then(|v| v.as_str())
            .is_some(),
        "service_b missing refresh_token"
    );
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    // Unit test for field comparison logic (no live services needed)
    #[test]
    fn test_field_mismatch_detection() {
        let a = json!({"email": "user@example.com", "role": "admin"});
        let b = json!({"email": "user@example.com", "role": "user"});

        let fields = ["email", "role"];
        let mut mismatches = Vec::new();
        for field in &fields {
            let va = a.get(field).unwrap_or(&Value::Null);
            let vb = b.get(field).unwrap_or(&Value::Null);
            if va != vb {
                mismatches.push(format!("{field}: {va} ≠ {vb}"));
            }
        }

        assert_eq!(mismatches.len(), 1);
        assert!(mismatches[0].contains("role"));
    }

    #[test]
    fn test_no_mismatch_when_equal() {
        let a = json!({"email": "user@example.com", "status": "active"});
        let b = json!({"email": "user@example.com", "status": "active"});

        let fields = ["email", "status"];
        let mismatches: Vec<_> = fields.iter().filter(|f| a.get(*f) != b.get(*f)).collect();
        assert!(mismatches.is_empty());
    }
}
