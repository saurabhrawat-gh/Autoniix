//! REST contract validator — validates live API responses against OpenAPI schemas.
//!
//! Per HARNESS-ENGINEERING-PLAN.md Week 1 Day 1-2.

use std::path::Path;

use anyhow::{Context, Result};
use jsonschema::JSONSchema;
use reqwest::{Client, Method};
use serde_json::Value;
use thiserror::Error;
use tracing::{error, info, warn};

#[derive(Debug, Error)]
pub enum ContractError {
    #[error("HTTP request failed: {0}")]
    Request(#[from] reqwest::Error),

    #[error("Response status {actual} does not match expected {expected}")]
    WrongStatus { expected: u16, actual: u16 },

    #[error("Response is not valid JSON: {0}")]
    InvalidJson(String),

    #[error("Schema not found for {method} {path} (status {code})")]
    SchemaNotFound {
        method: String,
        path: String,
        code: u16,
    },

    #[error("Schema validation errors:\n{}", errors.join("\n  - "))]
    ValidationFailed { errors: Vec<String> },

    #[error("Schema file error: {0}")]
    SchemaFile(#[from] anyhow::Error),
}

/// Validates live REST endpoints against an OpenAPI 3.0 schema.
pub struct ContractValidator {
    schema: Value,
    client: Client,
}

impl ContractValidator {
    /// Load schema from a JSON or YAML file on disk.
    pub fn from_file(path: impl AsRef<Path>) -> Result<Self> {
        let path = path.as_ref();
        let raw = std::fs::read_to_string(path)
            .with_context(|| format!("reading schema file {}", path.display()))?;

        let schema: Value = if path.extension().and_then(|e| e.to_str()) == Some("yaml")
            || path.extension().and_then(|e| e.to_str()) == Some("yml")
        {
            serde_yaml_value(&raw)?
        } else {
            serde_json::from_str(&raw)
                .with_context(|| format!("parsing JSON schema from {}", path.display()))?
        };

        Ok(Self {
            schema,
            client: Client::new(),
        })
    }

    /// Load schema from an already-parsed JSON value.
    pub fn from_value(schema: Value) -> Self {
        Self {
            schema,
            client: Client::new(),
        }
    }

    /// Fetch OpenAPI schema from a live `/openapi.json` endpoint.
    pub async fn from_endpoint(base_url: &str) -> Result<Self> {
        let url = format!("{base_url}/openapi.json");
        let schema: Value = reqwest::get(&url)
            .await
            .with_context(|| format!("fetching schema from {url}"))?
            .json()
            .await
            .context("parsing /openapi.json response")?;

        info!(base_url, "loaded openapi schema from endpoint");
        Ok(Self::from_value(schema))
    }

    /// Validate a live endpoint response against the OpenAPI schema.
    ///
    /// Makes the HTTP request, checks status code, then validates the JSON body.
    pub async fn validate_endpoint(
        &self,
        base_url: &str,
        method: Method,
        path: &str,
        request_body: Option<Value>,
        headers: Option<Vec<(String, String)>>,
        expected_status: u16,
    ) -> Result<Value, ContractError> {
        let url = format!("{base_url}{path}");
        info!(method = %method, url, "validating endpoint");

        let mut req = self.client.request(method.clone(), &url);
        if let Some(body) = request_body {
            req = req.json(&body);
        }
        if let Some(hdrs) = headers {
            for (k, v) in hdrs {
                req = req.header(k, v);
            }
        }

        let response = req.send().await?;
        let actual_status = response.status().as_u16();

        if actual_status != expected_status {
            return Err(ContractError::WrongStatus {
                expected: expected_status,
                actual: actual_status,
            });
        }

        let body_text = response.text().await.unwrap_or_default();
        let body: Value = serde_json::from_str(&body_text)
            .map_err(|_| ContractError::InvalidJson(body_text.clone()))?;

        // Locate response schema in the OpenAPI document
        let response_schema = self.get_response_schema(method.as_str(), path, expected_status)?;

        // Validate
        let compiled =
            JSONSchema::compile(&response_schema).map_err(|e| ContractError::ValidationFailed {
                errors: vec![e.to_string()],
            })?;

        let errors: Vec<String> = match compiled.validate(&body) {
            Ok(()) => Vec::new(),
            Err(validation_errors) => validation_errors
                .map(|e| format!("{}: {}", e.instance_path, e))
                .collect(),
        };

        if errors.is_empty() {
            info!(method = %method, path, status = expected_status, "contract validated ✓");
            Ok(body)
        } else {
            error!(method = %method, path, ?errors, "contract validation failed");
            Err(ContractError::ValidationFailed { errors })
        }
    }

    /// Extract the response JSON schema for a given operation from the OpenAPI document.
    fn get_response_schema(
        &self,
        method: &str,
        path: &str,
        status: u16,
    ) -> Result<Value, ContractError> {
        let method_lower = method.to_lowercase();
        let status_str = status.to_string();

        let schema_ref = self
            .schema
            .get("paths")
            .and_then(|p| p.get(path))
            .and_then(|p| p.get(&method_lower))
            .and_then(|op| op.get("responses"))
            .and_then(|r| r.get(&status_str))
            .and_then(|r| r.get("content"))
            .and_then(|c| c.get("application/json"))
            .and_then(|j| j.get("schema"));

        match schema_ref {
            None => {
                warn!(method, path, status, "no schema found in OpenAPI document");
                Err(ContractError::SchemaNotFound {
                    method: method.to_string(),
                    path: path.to_string(),
                    code: status,
                })
            }
            Some(s) => Ok(self.resolve_ref(s.clone())),
        }
    }

    /// Resolve a `$ref` pointer within the schema document (single level).
    fn resolve_ref(&self, schema: Value) -> Value {
        if let Some(ref_str) = schema.get("$ref").and_then(|r| r.as_str()) {
            if let Some(pointer) = ref_str.strip_prefix("#/") {
                let parts: Vec<&str> = pointer.split('/').collect();
                let mut cursor = &self.schema;
                for part in &parts {
                    cursor = match cursor.get(part) {
                        Some(v) => v,
                        None => return schema,
                    };
                }
                return cursor.clone();
            }
        }
        schema
    }
}

/// Minimal YAML→JSON conversion (delegates to serde_json via string round-trip for now).
/// Replace with `serde_yaml` if added as a dependency.
fn serde_yaml_value(raw: &str) -> Result<Value> {
    // Attempt basic YAML by stripping comments and re-parsing as JSON (not robust).
    // TODO: add serde_yaml to workspace deps for proper YAML support.
    serde_json::from_str(raw).context("YAML parsing not yet supported; use JSON schema")
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    fn sample_schema() -> Value {
        json!({
            "openapi": "3.0.3",
            "paths": {
                "/api/v2/auth/signup": {
                    "post": {
                        "responses": {
                            "201": {
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "type": "object",
                                            "required": ["access_token", "refresh_token"],
                                            "properties": {
                                                "access_token": {"type": "string"},
                                                "refresh_token": {"type": "string"},
                                                "expires_in": {"type": "integer"}
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        })
    }

    #[test]
    fn test_get_response_schema_found() {
        let validator = ContractValidator::from_value(sample_schema());
        let schema = validator.get_response_schema("POST", "/api/v2/auth/signup", 201);
        assert!(schema.is_ok());
        let s = schema.unwrap();
        assert_eq!(s["type"], "object");
    }

    #[test]
    fn test_get_response_schema_not_found() {
        let validator = ContractValidator::from_value(sample_schema());
        let schema = validator.get_response_schema("GET", "/api/v2/missing", 200);
        assert!(matches!(schema, Err(ContractError::SchemaNotFound { .. })));
    }

    #[test]
    fn test_validate_response_passes() {
        let validator = ContractValidator::from_value(sample_schema());
        let schema = validator
            .get_response_schema("POST", "/api/v2/auth/signup", 201)
            .unwrap();

        let response = json!({
            "access_token": "eyJhbGc...",
            "refresh_token": "opaque_token_abc123",
            "expires_in": 3600
        });

        let compiled = JSONSchema::compile(&schema).unwrap();
        let errors: Vec<String> = match compiled.validate(&response) {
            Ok(()) => Vec::new(),
            Err(validation_errors) => validation_errors.map(|e| e.to_string()).collect(),
        };
        assert!(
            errors.is_empty(),
            "expected no validation errors: {errors:?}"
        );
    }

    #[test]
    fn test_validate_response_fails_missing_required() {
        let validator = ContractValidator::from_value(sample_schema());
        let schema = validator
            .get_response_schema("POST", "/api/v2/auth/signup", 201)
            .unwrap();

        let response = json!({ "expires_in": 3600 }); // missing access_token + refresh_token

        let compiled = JSONSchema::compile(&schema).unwrap();
        let errors: Vec<String> = match compiled.validate(&response) {
            Ok(()) => Vec::new(),
            Err(validation_errors) => validation_errors.map(|e| e.to_string()).collect(),
        };
        assert!(
            !errors.is_empty(),
            "expected validation errors for missing fields"
        );
    }
}
