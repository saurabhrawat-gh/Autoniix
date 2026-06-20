use axum::{
    async_trait,
    extract::FromRequestParts,
    http::{request::Parts, StatusCode},
};

use crate::middleware::Principal;

pub struct AuthUser(pub Principal);

#[async_trait]
impl<S> FromRequestParts<S> for AuthUser
where
    S: Send + Sync,
{
    type Rejection = StatusCode;
    
    async fn from_request_parts(parts: &mut Parts, _state: &S) -> Result<Self, Self::Rejection> {
        parts
            .extensions
            .get::<Principal>()
            .cloned()
            .map(AuthUser)
            .ok_or(StatusCode::UNAUTHORIZED)
    }
}

pub struct RequireOwner(pub Principal);

#[async_trait]
impl<S> FromRequestParts<S> for RequireOwner
where
    S: Send + Sync,
{
    type Rejection = StatusCode;
    
    async fn from_request_parts(parts: &mut Parts, _state: &S) -> Result<Self, Self::Rejection> {
        let principal = parts
            .extensions
            .get::<Principal>()
            .cloned()
            .ok_or(StatusCode::UNAUTHORIZED)?;
        
        if !principal.has_role("owner") && !principal.has_role("admin") {
            return Err(StatusCode::FORBIDDEN);
        }
        
        Ok(RequireOwner(principal))
    }
}

pub struct RequireAdmin(pub Principal);

#[async_trait]
impl<S> FromRequestParts<S> for RequireAdmin
where
    S: Send + Sync,
{
    type Rejection = StatusCode;
    
    async fn from_request_parts(parts: &mut Parts, _state: &S) -> Result<Self, Self::Rejection> {
        let principal = parts
            .extensions
            .get::<Principal>()
            .cloned()
            .ok_or(StatusCode::UNAUTHORIZED)?;
        
        if !principal.has_role("admin") {
            return Err(StatusCode::FORBIDDEN);
        }
        
        Ok(RequireAdmin(principal))
    }
}
