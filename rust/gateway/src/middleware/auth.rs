use axum::{
    body::Body,
    extract::{Request, State},
    http::{header::AUTHORIZATION, StatusCode},
    middleware::Next,
    response::Response,
};
use std::sync::Arc;

use crate::{
    auth::{jwt::Claims, JwtManager},
    error::ApiError,
};

#[derive(Debug, Clone)]
pub struct Principal {
    pub user_id: String,
    pub wid: i64,
    pub email: String,
    pub role: String,
    pub global_role: String,
}

impl From<Claims> for Principal {
    fn from(claims: Claims) -> Self {
        Self {
            user_id: claims.sub,
            wid: claims.wid,
            email: claims.email,
            role: claims.role,
            global_role: claims.global_role,
        }
    }
}

impl Principal {
    pub fn has_role(&self, role: &str) -> bool {
        self.role == role || self.role == "owner"
    }
    
    pub fn has_any_role(&self, roles: &[&str]) -> bool {
        roles.iter().any(|r| self.has_role(r))
    }
    
    pub fn has_global_role(&self, role: &str) -> bool {
        self.global_role == role
    }
}

pub async fn auth_middleware(
    State(jwt_manager): State<Arc<JwtManager>>,
    mut request: Request,
    next: Next,
) -> Result<Response, StatusCode> {
    let auth_header = request
        .headers()
        .get(AUTHORIZATION)
        .and_then(|h| h.to_str().ok());
    
    if let Some(auth_value) = auth_header {
        if let Some(token) = auth_value.strip_prefix("Bearer ") {
            match jwt_manager.verify_token(token) {
                Ok(claims) => {
                    let principal = Principal::from(claims);
                    request.extensions_mut().insert(principal);
                    return Ok(next.run(request).await);
                }
                Err(_) => {
                    return Err(StatusCode::UNAUTHORIZED);
                }
            }
        }
    }
    
    Ok(next.run(request).await)
}

pub async fn require_auth_middleware(
    request: Request,
    next: Next,
) -> Result<Response, StatusCode> {
    if request.extensions().get::<Principal>().is_none() {
        return Err(StatusCode::UNAUTHORIZED);
    }
    
    Ok(next.run(request).await)
}

#[derive(Clone)]
pub struct RequireRole {
    pub roles: Vec<String>,
}

impl RequireRole {
    pub fn new(roles: Vec<String>) -> Self {
        Self { roles }
    }
    
    pub fn single(role: impl Into<String>) -> Self {
        Self {
            roles: vec![role.into()],
        }
    }
    
    pub async fn middleware(
        State(required): State<Self>,
        request: Request,
        next: Next,
    ) -> Result<Response, StatusCode> {
        let principal = request
            .extensions()
            .get::<Principal>()
            .ok_or(StatusCode::UNAUTHORIZED)?;
        
        let has_role = required
            .roles
            .iter()
            .any(|r| principal.has_role(r));
        
        if !has_role {
            return Err(StatusCode::FORBIDDEN);
        }
        
        Ok(next.run(request).await)
    }
}
