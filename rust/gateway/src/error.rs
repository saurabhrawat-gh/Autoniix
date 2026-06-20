use axum::{
    http::StatusCode,
    response::{IntoResponse, Response},
    Json,
};
use serde_json::json;
use thiserror::Error;

#[derive(Error, Debug)]
pub enum ApiError {
    #[error("Database error: {0}")]
    Database(#[from] sqlx::Error),
    
    #[error("Authentication failed")]
    Unauthorized,
    
    #[error("Forbidden")]
    Forbidden,
    
    #[error("Not found: {0}")]
    NotFound(String),
    
    #[error("Validation error: {0}")]
    Validation(String),
    
    #[error("Internal server error")]
    Internal,
    
    #[error("Service unavailable: {0}")]
    ServiceUnavailable(String),
}

impl IntoResponse for ApiError {
    fn into_response(self) -> Response {
        let (status, code, message) = match self {
            ApiError::Database(ref e) => {
                tracing::error!("Database error: {:?}", e);
                (StatusCode::INTERNAL_SERVER_ERROR, "DB_ERROR", self.to_string())
            }
            ApiError::Unauthorized => {
                (StatusCode::UNAUTHORIZED, "UNAUTHORIZED", self.to_string())
            }
            ApiError::Forbidden => {
                (StatusCode::FORBIDDEN, "FORBIDDEN", self.to_string())
            }
            ApiError::NotFound(_) => {
                (StatusCode::NOT_FOUND, "NOT_FOUND", self.to_string())
            }
            ApiError::Validation(_) => {
                (StatusCode::BAD_REQUEST, "VALIDATION_ERROR", self.to_string())
            }
            ApiError::Internal => {
                (StatusCode::INTERNAL_SERVER_ERROR, "INTERNAL_ERROR", self.to_string())
            }
            ApiError::ServiceUnavailable(_) => {
                (StatusCode::SERVICE_UNAVAILABLE, "SERVICE_UNAVAILABLE", self.to_string())
            }
        };
        
        let body = Json(json!({
            "error": {
                "code": code,
                "message": message,
            }
        }));
        
        (status, body).into_response()
    }
}

pub type ApiResult<T> = Result<T, ApiError>;
