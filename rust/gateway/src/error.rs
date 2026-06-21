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

    /// 403 with no message body (legacy callers that don't need to surface
    /// a reason).
    #[error("Forbidden")]
    Forbidden,

    /// 403 carrying a human-readable reason. Use this for action-specific
    /// rejections like "Cannot disable your own account" — matches the
    /// shape Python returns via `HTTPException(403, "...")`.
    #[error("{0}")]
    ForbiddenWith(String),

    #[error("Not found: {0}")]
    NotFound(String),

    #[error("Validation error: {0}")]
    Validation(String),

    #[error("Internal server error: {0}")]
    Internal(String),

    #[error("Service unavailable: {0}")]
    ServiceUnavailable(String),

    #[error("Conflict: {0}")]
    Conflict(String),
}

impl IntoResponse for ApiError {
    fn into_response(self) -> Response {
        let (status, code, message) = match self {
            ApiError::Database(ref e) => {
                tracing::error!("Database error: {:?}", e);
                (
                    StatusCode::INTERNAL_SERVER_ERROR,
                    "DB_ERROR",
                    self.to_string(),
                )
            }
            ApiError::Unauthorized => (StatusCode::UNAUTHORIZED, "UNAUTHORIZED", self.to_string()),
            ApiError::Forbidden => (StatusCode::FORBIDDEN, "FORBIDDEN", self.to_string()),
            ApiError::ForbiddenWith(_) => (StatusCode::FORBIDDEN, "FORBIDDEN", self.to_string()),
            ApiError::NotFound(_) => (StatusCode::NOT_FOUND, "NOT_FOUND", self.to_string()),
            ApiError::Validation(_) => (
                StatusCode::BAD_REQUEST,
                "VALIDATION_ERROR",
                self.to_string(),
            ),
            ApiError::Internal(_) => (
                StatusCode::INTERNAL_SERVER_ERROR,
                "INTERNAL_ERROR",
                self.to_string(),
            ),
            ApiError::ServiceUnavailable(_) => (
                StatusCode::SERVICE_UNAVAILABLE,
                "SERVICE_UNAVAILABLE",
                self.to_string(),
            ),
            ApiError::Conflict(_) => (StatusCode::CONFLICT, "CONFLICT", self.to_string()),
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
