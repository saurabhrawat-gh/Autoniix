use anyhow::Result;
use std::env;

#[derive(Debug, Clone)]
pub struct Config {
    pub environment: String,
    pub port: u16,
    pub database_url: String,
    pub jwt_secret: String,
    /// `"live"` (default) or `"mock"`. When `"mock"`, gateway tests inject a
    /// wiremock BFF server and set `PYTHON_BFF_URL` to its address so proxy
    /// handlers (trigger, clone, brand-kit, …) never hit the real Python BFF.
    pub provider_mode: String,
    /// Base URL of the Python BFF, overridable for testing.
    pub python_bff_url: String,
}

impl Config {
    pub fn from_env() -> Result<Self> {
        Ok(Config {
            environment: env::var("ENVIRONMENT").unwrap_or_else(|_| "development".to_string()),
            port: env::var("PORT")
                .unwrap_or_else(|_| "8080".to_string())
                .parse()?,
            database_url: env::var("DATABASE_URL")?,
            jwt_secret: env::var("AUTH_JWT_SECRET")
                .or_else(|_| env::var("DASHBOARD_JWT_SECRET"))
                .or_else(|_| env::var("JWT_SECRET"))?,
            provider_mode: env::var("PROVIDER_MODE")
                .unwrap_or_else(|_| "live".to_string()),
            python_bff_url: env::var("PYTHON_BFF_URL")
                .unwrap_or_else(|_| "http://localhost:8020".to_string()),
        })
    }
}
