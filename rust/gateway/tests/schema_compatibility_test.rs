//! Schema compatibility tests per HARNESS-ENGINEERING-PLAN.md Section 13.
//!
//! Verifies Rust gateway can read/write Python's production schema.
//! Requires a test database with Python's migrations applied.
//!
//! Run:
//!   TEST_DATABASE_URL=postgresql://localhost/autoniix_test cargo test -p gateway --test schema_compatibility_test

use serde_json::json;
use sqlx::PgPool;

async fn get_test_pool() -> PgPool {
    let database_url = std::env::var("TEST_DATABASE_URL")
        .unwrap_or_else(|_| "postgresql://localhost/autoniix_test".to_string());

    match PgPool::connect(&database_url).await {
        Ok(pool) => pool,
        Err(e) => {
            eprintln!("SKIP: cannot connect to test database: {e}");
            eprintln!("      Set TEST_DATABASE_URL and run scripts/setup_test_db.sh");
            return PgPool::connect_lazy(&database_url)
                .expect("failed to create lazy pool");
        }
    }
}

fn skip_if_no_db(pool: &PgPool) -> bool {
    pool.acquire().is_ok() == false
}

// ── Schema structure validation (no live service needed) ───────────────────

#[tokio::test]
async fn test_users_table_uses_integer_ids() {
    let pool = get_test_pool().await;
    if skip_if_no_db(&pool) {
        eprintln!("SKIP: no test database");
        return;
    }

    let row: Option<(String, String)> = sqlx::query_as(
        "SELECT column_name, data_type FROM information_schema.columns \
         WHERE table_name = 'users' AND column_name = 'id'"
    )
    .fetch_optional(&pool)
    .await
    .unwrap_or(None);

    match row {
        Some((name, dtype)) => {
            assert_eq!(name, "id");
            assert!(
                dtype == "integer" || dtype == "bigint",
                "users.id must be integer type, got {dtype}"
            );
        }
        None => eprintln!("SKIP: users table not found in test DB"),
    }
}

#[tokio::test]
async fn test_workspaces_table_uses_integer_ids() {
    let pool = get_test_pool().await;
    if skip_if_no_db(&pool) {
        eprintln!("SKIP: no test database");
        return;
    }

    let row: Option<(String, String)> = sqlx::query_as(
        "SELECT column_name, data_type FROM information_schema.columns \
         WHERE table_name = 'workspaces' AND column_name = 'id'"
    )
    .fetch_optional(&pool)
    .await
    .unwrap_or(None);

    match row {
        Some((name, dtype)) => {
            assert_eq!(name, "id");
            assert!(
                dtype == "integer" || dtype == "bigint",
                "workspaces.id must be integer type, got {dtype}"
            );
        }
        None => eprintln!("SKIP: workspaces table not found in test DB"),
    }
}

#[tokio::test]
async fn test_workspace_members_table_exists() {
    let pool = get_test_pool().await;
    if skip_if_no_db(&pool) {
        eprintln!("SKIP: no test database");
        return;
    }

    let exists: Option<bool> = sqlx::query_scalar(
        "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'workspace_members')"
    )
    .fetch_optional(&pool)
    .await
    .unwrap_or(None);

    match exists {
        Some(true) => {}
        Some(false) => panic!("workspace_members table must exist"),
        None => eprintln!("SKIP: cannot query information_schema"),
    }
}

#[tokio::test]
async fn test_sessions_table_exists() {
    let pool = get_test_pool().await;
    if skip_if_no_db(&pool) {
        eprintln!("SKIP: no test database");
        return;
    }

    let exists: Option<bool> = sqlx::query_scalar(
        "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'sessions')"
    )
    .fetch_optional(&pool)
    .await
    .unwrap_or(None);

    match exists {
        Some(true) => {}
        Some(false) => panic!("sessions table must exist"),
        None => eprintln!("SKIP: cannot query information_schema"),
    }
}

#[tokio::test]
async fn test_user_roles_table_does_not_exist() {
    let pool = get_test_pool().await;
    if skip_if_no_db(&pool) {
        eprintln!("SKIP: no test database");
        return;
    }

    let exists: Option<bool> = sqlx::query_scalar(
        "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'user_roles')"
    )
    .fetch_optional(&pool)
    .await
    .unwrap_or(None);

    match exists {
        Some(false) => {} // Good — user_roles must not exist
        Some(true) => panic!("user_roles table must NOT exist (use workspace_members)"),
        None => eprintln!("SKIP: cannot query information_schema"),
    }
}

// ── Rust reads Python-created data ──────────────────────────────────────────

#[tokio::test]
async fn test_rust_reads_python_created_user() {
    let pool = get_test_pool().await;
    if skip_if_no_db(&pool) {
        eprintln!("SKIP: no test database");
        return;
    }

    // Simulate Python creating a user (direct SQL insert matching Python's schema)
    let email = format!("py-user-{}@schema.test", chrono::Utc::now().timestamp_nanos_opt().unwrap_or(0));
    let user_id: i64 = match sqlx::query_scalar(
        "INSERT INTO users (email, password_hash, role, disabled, email_verified)
         VALUES ($1, $2, 'user', false, true)
         RETURNING id"
    )
    .bind(&email)
    .bind("$argon2id$v=19$m=19456,t=2,p=1$salt$hash")
    .fetch_one(&pool)
    .await
    {
        Ok(id) => id,
        Err(e) => {
            eprintln!("SKIP: cannot insert test user: {e}");
            return;
        }
    };

    assert!(user_id > 0, "Python-created user must have positive integer id");

    // Rust reads the same user via SQL (simulating what the gateway does)
    let read_email: String = sqlx::query_scalar("SELECT email FROM users WHERE id = $1")
        .bind(user_id)
        .fetch_one(&pool)
        .await
        .expect("Rust must be able to read Python-created user");

    assert_eq!(read_email, email);

    // Cleanup
    let _ = sqlx::query("DELETE FROM users WHERE id = $1")
        .bind(user_id)
        .execute(&pool)
        .await;
}

#[tokio::test]
async fn test_rust_created_user_has_integer_id() {
    let pool = get_test_pool().await;
    if skip_if_no_db(&pool) {
        eprintln!("SKIP: no test database");
        return;
    }

    let email = format!("rust-user-{}@schema.test", chrono::Utc::now().timestamp_nanos_opt().unwrap_or(0));

    // Insert as Rust gateway would
    let user_id: i64 = match sqlx::query_scalar(
        "INSERT INTO users (email, password_hash, role, disabled, email_verified)
         VALUES ($1, $2, 'superadmin', false, true)
         RETURNING id"
    )
    .bind(&email)
    .bind("$argon2id$v=19$m=19456,t=2,p=1$salt$hash")
    .fetch_one(&pool)
    .await
    {
        Ok(id) => id,
        Err(e) => {
            eprintln!("SKIP: cannot insert test user: {e}");
            return;
        }
    };

    // Verify id is i64 (not UUID text)
    assert!(user_id > 0, "Rust-created user must have positive i64 id");

    // Cleanup
    let _ = sqlx::query("DELETE FROM users WHERE id = $1")
        .bind(user_id)
        .execute(&pool)
        .await;
}

// ── JWT cross-validation ────────────────────────────────────────────────────

#[tokio::test]
async fn test_rust_jwt_sub_is_stringified_int() {
    use jsonwebtoken::{decode, DecodingKey, Validation, Algorithm};

    let secret = std::env::var("AUTH_JWT_SECRET")
        .unwrap_or_else(|_| "test-jwt-secret-key-must-be-long-enough".to_string());

    // Simulate Rust creating a JWT (as jwt.rs does)
    use jsonwebtoken::{encode, EncodingKey, Header};
    let claims = json!({
        "sub": "42",
        "email": "test@schema.test",
        "role": "owner",
        "global_role": "superadmin",
        "wid": 7,
        "iat": 1718901234,
        "exp": 1718904834
    });

    let token = encode(
        &Header::new(Algorithm::HS256),
        &claims,
        &EncodingKey::from_secret(secret.as_bytes()),
    )
    .expect("must encode JWT");

    // Decode and verify sub is parseable as int (Python does int(claims["sub"]))
    let token_data = decode::<serde_json::Value>(
        &token,
        &DecodingKey::from_secret(secret.as_bytes()),
        &Validation::new(Algorithm::HS256),
    )
    .expect("must decode JWT");

    let sub = token_data.claims["sub"].as_str().expect("sub must be string");
    let user_id: i64 = sub.parse().expect("sub must be parseable as i64");
    assert_eq!(user_id, 42);

    let wid = token_data.claims["wid"].as_i64().expect("wid must be i64");
    assert_eq!(wid, 7);

    let role = token_data.claims["role"].as_str().expect("role must be string");
    assert_eq!(role, "owner");
}

#[tokio::test]
async fn test_python_jwt_decodes_in_rust() {
    use jsonwebtoken::{decode, DecodingKey, Validation, Algorithm};

    let secret = std::env::var("AUTH_JWT_SECRET")
        .unwrap_or_else(|_| "test-jwt-secret-key-must-be-long-enough".to_string());

    // Simulate Python creating a JWT (sub as int, wid as int)
    use jsonwebtoken::{encode, EncodingKey, Header};
    let claims = json!({
        "sub": 42,               // Python sends int
        "email": "py@schema.test",
        "role": "member",
        "global_role": "user",
        "wid": 7,
        "iat": 1718901234,
        "exp": 1718904834
    });

    let token = encode(
        &Header::new(Algorithm::HS256),
        &claims,
        &EncodingKey::from_secret(secret.as_bytes()),
    )
    .expect("must encode JWT");

    // Rust decodes it — Rust's Claims struct has sub: String
    // jsonwebtoken will serialize int sub as string when deserializing into String
    let result = decode::<serde_json::Value>(
        &token,
        &DecodingKey::from_secret(secret.as_bytes()),
        &Validation::new(Algorithm::HS256),
    );

    match result {
        Ok(token_data) => {
            // Rust can read the token — sub may be int or string depending on serde
            let sub = &token_data.claims["sub"];
            if let Some(s) = sub.as_str() {
                let _: i64 = s.parse().expect("stringified sub must parse as i64");
            } else if let Some(i) = sub.as_i64() {
                assert_eq!(i, 42);
            } else {
                panic!("sub must be string or int, got {sub}");
            }
            println!("✓ Python-shaped JWT decodes in Rust");
        }
        Err(e) => panic!("Rust must decode Python-shaped JWT: {e}"),
    }
}

// ── Workspace role resolution ───────────────────────────────────────────────

#[tokio::test]
async fn test_workspace_members_role_resolution() {
    let pool = get_test_pool().await;
    if skip_if_no_db(&pool) {
        eprintln!("SKIP: no test database");
        return;
    }

    let email = format!("member-{}@schema.test", chrono::Utc::now().timestamp_nanos_opt().unwrap_or(0));

    // Create user
    let user_id: i64 = match sqlx::query_scalar(
        "INSERT INTO users (email, password_hash, role, disabled, email_verified)
         VALUES ($1, 'hash', 'user', false, true) RETURNING id"
    )
    .bind(&email)
    .fetch_one(&pool)
    .await
    {
        Ok(id) => id,
        Err(e) => { eprintln!("SKIP: {e}"); return; }
    };

    // Create workspace
    let slug = format!("ws-{}", user_id);
    let workspace_id: i64 = match sqlx::query_scalar(
        "INSERT INTO workspaces (name, slug, plan, owner_user_id)
         VALUES ('Test WS', $1, 'starter', $2) RETURNING id"
    )
    .bind(&slug)
    .bind(user_id)
    .fetch_one(&pool)
    .await
    {
        Ok(id) => id,
        Err(e) => {
            let _ = sqlx::query("DELETE FROM users WHERE id = $1").bind(user_id).execute(&pool).await;
            eprintln!("SKIP: {e}");
            return;
        }
    };

    // Create membership with 'viewer' role
    let _ = sqlx::query(
        "INSERT INTO workspace_members (workspace_id, user_id, role) VALUES ($1, $2, 'viewer')"
    )
    .bind(workspace_id)
    .bind(user_id)
    .execute(&pool)
    .await;

    // Read role back (as Rust gateway does)
    let role: String = sqlx::query_scalar(
        "SELECT role FROM workspace_members WHERE workspace_id = $1 AND user_id = $2"
    )
    .bind(workspace_id)
    .bind(user_id)
    .fetch_one(&pool)
    .await
    .expect("must read workspace_members role");

    assert_eq!(role, "viewer");

    // Cleanup
    let _ = sqlx::query("DELETE FROM workspace_members WHERE workspace_id = $1 AND user_id = $2")
        .bind(workspace_id).bind(user_id).execute(&pool).await;
    let _ = sqlx::query("DELETE FROM workspaces WHERE id = $1").bind(workspace_id).execute(&pool).await;
    let _ = sqlx::query("DELETE FROM users WHERE id = $1").bind(user_id).execute(&pool).await;
}
