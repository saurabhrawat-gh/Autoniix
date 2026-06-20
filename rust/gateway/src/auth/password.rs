use argon2::{
    password_hash::{rand_core::OsRng, PasswordHash, PasswordHasher, PasswordVerifier, SaltString},
    Argon2,
};

use crate::error::{ApiError, ApiResult};

pub struct PasswordManager;

impl PasswordManager {
    pub fn hash_password(password: &str) -> ApiResult<String> {
        let salt = SaltString::generate(&mut OsRng);
        let argon2 = Argon2::default();
        
        argon2
            .hash_password(password.as_bytes(), &salt)
            .map(|hash| hash.to_string())
            .map_err(|e| {
                tracing::error!("Password hashing failed: {:?}", e);
                ApiError::Internal("Password hashing failed".to_string())
            })
    }
    
    pub fn verify_password(password: &str, hash: &str) -> ApiResult<bool> {
        let parsed_hash = PasswordHash::new(hash).map_err(|e| {
            tracing::error!("Failed to parse password hash: {:?}", e);
            ApiError::Internal("Failed to parse password hash".to_string())
        })?;
        
        let argon2 = Argon2::default();
        
        Ok(argon2
            .verify_password(password.as_bytes(), &parsed_hash)
            .is_ok())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    
    #[test]
    fn test_password_hash_verify() {
        let password = "super-secret-password";
        let hash = PasswordManager::hash_password(password).unwrap();
        
        assert!(PasswordManager::verify_password(password, &hash).unwrap());
        assert!(!PasswordManager::verify_password("wrong-password", &hash).unwrap());
    }
}
