//! Autoniix test harness.
//!
//! Three modules per HARNESS-ENGINEERING-PLAN.md:
//! - `contract`  — OpenAPI schema validation against live endpoints
//! - `providers` — Typed mocks for 8 external APIs (OpenAI, Anthropic, …)
//! - `cross`     — Equivalence tests between Python ↔ Rust ↔ Go services

pub mod contract;
pub mod cross;
pub mod providers;
