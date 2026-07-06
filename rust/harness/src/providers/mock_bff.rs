//! Mock Python BFF server (wiremock) for `PROVIDER_MODE=mock` integration tests.
//!
//! Usage in gateway tests:
//! ```rust
//! let bff = MockBff::start().await;
//! std::env::set_var("PYTHON_BFF_URL", bff.url());
//! let h = GatewayHarness::new().await;
//! // ... proxy routes now hit the mock, not the real Python BFF
//! ```
//!
//! Per HARNESS-ENGINEERING-PLAN.md §A2.

use serde_json::json;
use wiremock::{
    matchers::{method, path_regex},
    Mock, MockServer, ResponseTemplate,
};

/// A running wiremock server that emulates the Python BFF for proxy endpoints.
pub struct MockBff {
    pub server: MockServer,
}

impl MockBff {
    /// Start the mock BFF and register default handlers for all known proxy paths.
    pub async fn start() -> Self {
        let server = MockServer::start().await;

        // --- channels proxy (trigger, clone, brand-kit, job pause/resume/stop) ---
        // helper closure-free registration via path_regex
        let routes: &[(&str, &str, u16, bool)] = &[
            // (method, path_pattern, status, is_data_list)
            ("POST", r"^/api/channels", 200, false),
            ("GET", r"^/api/channels", 200, false),
            ("PUT", r"^/api/channels", 200, false),
            ("GET", r"^/api/v2/providers", 200, true),
            ("POST", r"^/api/v2/providers", 200, false),
            ("PUT", r"^/api/v2/providers", 200, false),
            ("DELETE", r"^/api/v2/providers", 204, false),
            ("GET", r"^/api/v2/content", 200, true),
            ("POST", r"^/api/v2/content", 200, false),
            ("GET", r"^/api/v2/jobs", 200, true),
            ("POST", r"^/api/v2/jobs", 200, false),
            ("GET", r"^/api/v2/library", 200, true),
            ("POST", r"^/api/v2/library", 200, false),
            ("PUT", r"^/api/v2/library", 200, false),
            ("DELETE", r"^/api/v2/library", 204, false),
            ("GET", r"^/api/v2/review", 200, true),
            ("POST", r"^/api/v2/review", 200, false),
            ("GET", r"^/api/v2/experiments", 200, true),
        ];

        for (m, pattern, status, is_list) in routes {
            let body = if *status == 204 {
                None
            } else if *is_list {
                Some(json!({"data": [], "mock": true}))
            } else {
                Some(json!({"status": "ok", "mock": true}))
            };
            let mut tmpl = ResponseTemplate::new(*status);
            if let Some(b) = body {
                tmpl = tmpl.set_body_json(b);
            }
            Mock::given(method(*m))
                .and(path_regex(*pattern))
                .respond_with(tmpl)
                .mount(&server)
                .await;
        }

        Self { server }
    }

    /// Returns the base URL of the mock BFF.
    /// Set `PYTHON_BFF_URL` env var to this before starting `GatewayHarness`.
    pub fn url(&self) -> String {
        self.server.uri()
    }

    /// Configure an additional custom mock handler on this server.
    pub async fn add_mock(&self, mock: Mock) {
        mock.mount(&self.server).await;
    }
}
