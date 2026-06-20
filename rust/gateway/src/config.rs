use anyhow::Result;
use std::env;

#[derive(Debug, Clone)]
pub struct Config {
    pub environment: String,
    pub port: u16,
    pub database_url: String,
    pub jwt_secret: String,
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
        })
    }
}
