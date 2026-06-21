use chrono::Utc;
use jsonwebtoken::{decode, encode, DecodingKey, EncodingKey, Header, Validation};
use serde::{Deserialize, Serialize};

use crate::error::{ApiError, ApiResult};

#[derive(Debug, Serialize, Deserialize)]
pub struct Claims {
    pub sub: String,
    pub email: String,
    pub role: String,
    pub global_role: String,
    pub wid: i64,
    pub iat: i64,
    pub exp: i64,
}

impl Claims {
    pub fn new(
        user_id: String,
        wid: i64,
        email: String,
        role: String,
        global_role: String,
        expires_in_secs: i64,
    ) -> Self {
        let now = Utc::now().timestamp();

        Self {
            sub: user_id,
            email,
            role,
            global_role,
            wid,
            iat: now,
            exp: now + expires_in_secs,
        }
    }
}

pub struct JwtManager {
    encoding_key: EncodingKey,
    decoding_key: DecodingKey,
}

impl JwtManager {
    pub fn new(secret: &str) -> Self {
        Self {
            encoding_key: EncodingKey::from_secret(secret.as_bytes()),
            decoding_key: DecodingKey::from_secret(secret.as_bytes()),
        }
    }

    pub fn create_token(&self, claims: Claims) -> ApiResult<String> {
        encode(&Header::default(), &claims, &self.encoding_key).map_err(|e| {
            tracing::error!("Failed to encode JWT: {:?}", e);
            ApiError::Internal("Failed to encode JWT".to_string())
        })
    }

    pub fn verify_token(&self, token: &str) -> ApiResult<Claims> {
        let validation = Validation::default();

        decode::<Claims>(token, &self.decoding_key, &validation)
            .map(|data| data.claims)
            .map_err(|e| {
                tracing::warn!("JWT validation failed: {:?}", e);
                ApiError::Unauthorized
            })
    }

    pub fn create_access_token(
        &self,
        user_id: String,
        wid: i64,
        email: String,
        role: String,
        global_role: String,
    ) -> ApiResult<String> {
        let claims = Claims::new(user_id, wid, email, role, global_role, 3600);
        self.create_token(claims)
    }

    pub fn create_refresh_token(
        &self,
        user_id: String,
        wid: i64,
        email: String,
        role: String,
        global_role: String,
    ) -> ApiResult<String> {
        let claims = Claims::new(user_id, wid, email, role, global_role, 60 * 60 * 24 * 30);
        self.create_token(claims)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_jwt_roundtrip() {
        let manager = JwtManager::new("test-secret-key");

        let token = manager
            .create_access_token(
                "123".to_string(),
                456,
                "test@example.com".to_string(),
                "owner".to_string(),
                "superadmin".to_string(),
            )
            .unwrap();

        let claims = manager.verify_token(&token).unwrap();

        assert_eq!(claims.sub, "123");
        assert_eq!(claims.wid, 456);
        assert_eq!(claims.email, "test@example.com");
        assert_eq!(claims.role, "owner");
        assert_eq!(claims.global_role, "superadmin");
    }

    #[test]
    fn test_decodes_python_shaped_token() {
        let manager = JwtManager::new("shared-secret");
        let now = Utc::now().timestamp();
        let python_claims = Claims {
            sub: "42".to_string(),
            email: "py@example.com".to_string(),
            role: "viewer".to_string(),
            global_role: "user".to_string(),
            wid: 7,
            iat: now,
            exp: now + 3600,
        };
        let token = manager.create_token(python_claims).unwrap();
        let decoded = manager.verify_token(&token).unwrap();
        assert_eq!(decoded.sub, "42");
        assert_eq!(decoded.wid, 7);
        assert_eq!(decoded.role, "viewer");
        assert_eq!(decoded.global_role, "user");
    }

    #[test]
    fn test_invalid_token() {
        let manager = JwtManager::new("test-secret-key");
        let result = manager.verify_token("invalid.token.here");

        assert!(result.is_err());
    }
}
