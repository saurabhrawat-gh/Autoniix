//! Autoniix test harness.
//!
//! Four modules per HARNESS-ENGINEERING-PLAN.md:
//! - `contract`  — OpenAPI schema validation against live endpoints
//! - `providers` — Typed mocks for 8 external APIs (OpenAI, Anthropic, …)
//!                 + `MockBff` wiremock server for `PROVIDER_MODE=mock`
//! - `cross`     — Equivalence tests between Python ↔ Rust ↔ Go services
//! - `golden`    — Golden-file regression: capture + replay Python ↔ Rust

pub mod contract;
pub mod cross;
pub mod golden;
pub mod providers;
