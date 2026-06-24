//! Integration tests for /api/v2/lookup-values — AE-603.
//!
//! Covers:
//!   GET  /api/v2/lookup-values              — list (auth required, workspace-aware)
//!   POST /api/v2/lookup-values              — create global (superadmin only)
//!   PATCH /api/v2/lookup-values/:id         — update (owner for workspace, superadmin for global)
//!   DELETE /api/v2/lookup-values/:id        — soft-delete
//!   POST /api/v2/workspace/lookup-values    — create workspace-private value (owner only)
//!
//! Requires a live Postgres instance. Set TEST_DATABASE_URL or these tests
//! will be skipped. Run with:
//!   TEST_DATABASE_URL=postgresql://... cargo test --test lookup_values_test -- --nocapture

mod common;

use serde_json::json;

// ── Helpers ───────────────────────────────────────────────────────────────────

/// Promote a user to superadmin by user_id — test-only, cleaned up by harness.cleanup().
/// `users.role` is the platform-level (global) role; `global_role` is only an alias used in
/// SELECT queries and JWT claims.
async fn make_superadmin(h: &common::harness::GatewayHarness, user_id: i64) {
    sqlx::query("UPDATE users SET role = 'superadmin' WHERE id = $1")
        .bind(user_id)
        .execute(&h.pool)
        .await
        .expect("make_superadmin: UPDATE failed");
}

/// Clean up lookup_values rows inserted during a test (by label prefix).
async fn cleanup_lookup_values(h: &common::harness::GatewayHarness, label_prefix: &str) {
    let _ = sqlx::query("DELETE FROM lookup_values WHERE label LIKE $1")
        .bind(format!("{label_prefix}%"))
        .execute(&h.pool)
        .await;
}

// ── Tests ─────────────────────────────────────────────────────────────────────

#[tokio::test]
async fn test_list_lookup_values_requires_auth() {
    let h = common::harness::GatewayHarness::new().await;

    let resp = h
        .client
        .get(format!("{}/api/v2/lookup-values", h.base_url))
        .send()
        .await
        .unwrap();

    assert_eq!(resp.status(), 401, "unauthenticated request should return 401");

    h.cleanup().await;
}

#[tokio::test]
async fn test_list_lookup_values_returns_seeded_global_data() {
    let h = common::harness::GatewayHarness::new().await;
    let email = common::harness::GatewayHarness::unique_email("lv-list");
    let token = h.signup_and_get_token(&email, "Test1234!").await;

    let resp = h.get_auth("/api/v2/lookup-values", &token).await;
    assert_eq!(resp.status(), 200);

    let body: serde_json::Value = resp.json().await.unwrap();
    let data = body["data"].as_array().expect("data should be an array");

    // Migration 202606230002 seeds languages — at least 'en' should be present
    let has_en = data.iter().any(|v| v["type"] == "language" && v["value"] == "en");
    assert!(has_en, "seeded 'en' language value should be present");

    // All rows have required fields
    for row in data {
        assert!(row["id"].is_number(), "each row should have numeric id");
        assert!(row["type"].is_string(), "each row should have string type");
        assert!(row["value"].is_string(), "each row should have string value");
        assert!(row["label"].is_string(), "each row should have string label");
        assert!(row["is_active"].is_boolean(), "each row should have boolean is_active");
        assert!(row["is_custom"].is_boolean(), "each row should have boolean is_custom");
    }

    h.cleanup().await;
}

#[tokio::test]
async fn test_list_lookup_values_filtered_by_type() {
    let h = common::harness::GatewayHarness::new().await;
    let email = common::harness::GatewayHarness::unique_email("lv-filter");
    let token = h.signup_and_get_token(&email, "Test1234!").await;

    let resp = h.get_auth("/api/v2/lookup-values?type=language", &token).await;
    assert_eq!(resp.status(), 200);

    let body: serde_json::Value = resp.json().await.unwrap();
    let data = body["data"].as_array().unwrap();

    assert!(!data.is_empty(), "filtered language list should not be empty");
    for row in data {
        assert_eq!(row["type"], "language", "filtered rows should all be type=language");
    }

    h.cleanup().await;
}

#[tokio::test]
async fn test_create_global_value_requires_superadmin() {
    let h = common::harness::GatewayHarness::new().await;
    let email = common::harness::GatewayHarness::unique_email("lv-global-403");
    let token = h.signup_and_get_token(&email, "Test1234!").await;

    // Regular user (owner role, but not superadmin) should be forbidden
    let resp = h
        .post_auth(
            "/api/v2/lookup-values",
            json!({
                "type": "niche",
                "value": "lv_test_forbidden",
                "label": "LV Test Forbidden",
            }),
            &token,
        )
        .await;

    assert_eq!(resp.status(), 403, "non-superadmin should not be able to create global values");

    h.cleanup().await;
}

#[tokio::test]
async fn test_create_global_value_as_superadmin() {
    let h = common::harness::GatewayHarness::new().await;
    let email = common::harness::GatewayHarness::unique_email("lv-global-admin");
    let password = "Test1234!";

    // register() returns user_id; signin() does not
    let reg: serde_json::Value = h.register(&email, password, "SA User", "SA Workspace").await;
    let uid: i64 = reg["user_id"]
        .as_i64()
        .expect("register should return user_id");

    make_superadmin(&h, uid).await;

    // Re-sign-in so the JWT includes the updated global_role
    let new_signin: serde_json::Value = h.signin(&email, password).await;
    let admin_token = new_signin["access_token"].as_str().unwrap().to_string();

    let resp = h
        .post_auth(
            "/api/v2/lookup-values",
            json!({
                "type": "niche",
                "value": "lv_harness_global_test",
                "label": "LV Harness Global Test",
                "sort_order": 999,
            }),
            &admin_token,
        )
        .await;

    assert_eq!(resp.status(), 201, "superadmin should be able to create global values");
    let body: serde_json::Value = resp.json().await.unwrap();
    assert_eq!(body["type"], "niche");
    assert_eq!(body["value"], "lv_harness_global_test");
    assert!(body["workspace_id"].is_null(), "global value should have null workspace_id");
    assert_eq!(body["is_active"], true);

    cleanup_lookup_values(&h, "LV Harness Global Test").await;
    h.cleanup().await;
}

#[tokio::test]
async fn test_create_workspace_value_as_owner() {
    let h = common::harness::GatewayHarness::new().await;
    let email = common::harness::GatewayHarness::unique_email("lv-ws-create");
    let token = h.signup_and_get_token(&email, "Test1234!").await;

    let resp = h
        .post_auth(
            "/api/v2/workspace/lookup-values",
            json!({
                "type": "niche",
                "value": "lv_ws_custom_niche",
                "label": "LV WS Custom Niche",
            }),
            &token,
        )
        .await;

    assert_eq!(resp.status(), 201, "owner should be able to create workspace-private values");
    let body: serde_json::Value = resp.json().await.unwrap();
    assert_eq!(body["value"], "lv_ws_custom_niche");
    assert!(
        body["workspace_id"].is_number(),
        "workspace-private value should have a workspace_id"
    );
    assert_eq!(body["is_active"], true);

    cleanup_lookup_values(&h, "LV WS Custom Niche").await;
    h.cleanup().await;
}

#[tokio::test]
async fn test_workspace_value_is_scoped_to_owner_workspace() {
    let h = common::harness::GatewayHarness::new().await;

    // Workspace A owner creates a private value
    let email_a = common::harness::GatewayHarness::unique_email("lv-scope-a");
    let token_a = h.signup_and_get_token(&email_a, "Test1234!").await;

    let create: serde_json::Value = h
        .post_auth(
            "/api/v2/workspace/lookup-values",
            json!({
                "type": "niche",
                "value": "lv_private_workspace_a",
                "label": "LV Private Workspace A",
            }),
            &token_a,
        )
        .await
        .json()
        .await
        .unwrap();
    assert_eq!(create["is_active"], true);

    // Workspace B owner lists — should NOT see workspace A's private value
    let email_b = common::harness::GatewayHarness::unique_email("lv-scope-b");
    let token_b = h.signup_and_get_token(&email_b, "Test1234!").await;

    let list_b: serde_json::Value = h
        .get_auth("/api/v2/lookup-values?type=niche", &token_b)
        .await
        .json()
        .await
        .unwrap();
    let data_b = list_b["data"].as_array().unwrap();
    let sees_private = data_b
        .iter()
        .any(|v| v["value"] == "lv_private_workspace_a");
    assert!(
        !sees_private,
        "workspace B should not see workspace A's private lookup value"
    );

    // Workspace A owner lists — SHOULD see their own private value
    let list_a: serde_json::Value = h
        .get_auth("/api/v2/lookup-values?type=niche", &token_a)
        .await
        .json()
        .await
        .unwrap();
    let data_a = list_a["data"].as_array().unwrap();
    let sees_own = data_a
        .iter()
        .any(|v| v["value"] == "lv_private_workspace_a");
    assert!(sees_own, "workspace A should see its own private lookup value");

    cleanup_lookup_values(&h, "LV Private Workspace A").await;
    h.cleanup().await;
}

#[tokio::test]
async fn test_update_workspace_value_as_owner() {
    let h = common::harness::GatewayHarness::new().await;
    let email = common::harness::GatewayHarness::unique_email("lv-update");
    let token = h.signup_and_get_token(&email, "Test1234!").await;

    // Create workspace-private value
    let create: serde_json::Value = h
        .post_auth(
            "/api/v2/workspace/lookup-values",
            json!({
                "type": "niche",
                "value": "lv_update_original",
                "label": "LV Update Original",
            }),
            &token,
        )
        .await
        .json()
        .await
        .unwrap();
    let id = create["id"].as_i64().expect("create should return id");

    // Update label and sort_order
    let patch = h
        .client
        .patch(format!("{}/api/v2/lookup-values/{id}", h.base_url))
        .bearer_auth(&token)
        .json(&json!({ "label": "LV Update Renamed", "sort_order": 42 }))
        .send()
        .await
        .unwrap();
    assert_eq!(patch.status(), 200, "owner should be able to update their workspace value");
    let patch_body: serde_json::Value = patch.json().await.unwrap();
    assert_eq!(patch_body["status"], "updated");
    assert_eq!(patch_body["id"], id);

    cleanup_lookup_values(&h, "LV Update").await;
    h.cleanup().await;
}

#[tokio::test]
async fn test_update_workspace_value_cross_workspace_forbidden() {
    let h = common::harness::GatewayHarness::new().await;

    // Owner A creates a value
    let email_a = common::harness::GatewayHarness::unique_email("lv-cross-a");
    let token_a = h.signup_and_get_token(&email_a, "Test1234!").await;

    let create: serde_json::Value = h
        .post_auth(
            "/api/v2/workspace/lookup-values",
            json!({
                "type": "niche",
                "value": "lv_cross_workspace_guard",
                "label": "LV Cross Workspace Guard",
            }),
            &token_a,
        )
        .await
        .json()
        .await
        .unwrap();
    let id = create["id"].as_i64().expect("create should return id");

    // Owner B tries to update it — should be 403
    let email_b = common::harness::GatewayHarness::unique_email("lv-cross-b");
    let token_b = h.signup_and_get_token(&email_b, "Test1234!").await;

    let patch = h
        .client
        .patch(format!("{}/api/v2/lookup-values/{id}", h.base_url))
        .bearer_auth(&token_b)
        .json(&json!({ "label": "Hijacked Label" }))
        .send()
        .await
        .unwrap();
    assert_eq!(
        patch.status(),
        403,
        "cross-workspace update should be forbidden"
    );

    cleanup_lookup_values(&h, "LV Cross Workspace Guard").await;
    h.cleanup().await;
}

#[tokio::test]
async fn test_deactivate_workspace_value() {
    let h = common::harness::GatewayHarness::new().await;
    let email = common::harness::GatewayHarness::unique_email("lv-deactivate");
    let token = h.signup_and_get_token(&email, "Test1234!").await;

    // Create
    let create: serde_json::Value = h
        .post_auth(
            "/api/v2/workspace/lookup-values",
            json!({
                "type": "niche",
                "value": "lv_deactivate_me",
                "label": "LV Deactivate Me",
            }),
            &token,
        )
        .await
        .json()
        .await
        .unwrap();
    let id = create["id"].as_i64().unwrap();

    // Soft-delete
    let del = h
        .client
        .delete(format!("{}/api/v2/lookup-values/{id}", h.base_url))
        .bearer_auth(&token)
        .send()
        .await
        .unwrap();
    assert_eq!(del.status(), 204, "deactivate should return 204 No Content");

    // Default list (is_active=true) should no longer include it
    let list: serde_json::Value = h
        .get_auth("/api/v2/lookup-values?type=niche", &token)
        .await
        .json()
        .await
        .unwrap();
    let data = list["data"].as_array().unwrap();
    let still_visible = data.iter().any(|v| v["id"] == id);
    assert!(
        !still_visible,
        "deactivated value should not appear in default list"
    );

    // include_inactive=true should show it
    let list_all: serde_json::Value = h
        .get_auth(
            "/api/v2/lookup-values?type=niche&include_inactive=true",
            &token,
        )
        .await
        .json()
        .await
        .unwrap();
    let data_all = list_all["data"].as_array().unwrap();
    let in_inactive = data_all
        .iter()
        .any(|v| v["id"] == id && v["is_active"] == false);
    assert!(
        in_inactive,
        "deactivated value should appear with include_inactive=true"
    );

    cleanup_lookup_values(&h, "LV Deactivate Me").await;
    h.cleanup().await;
}

#[tokio::test]
async fn test_deactivate_cross_workspace_forbidden() {
    let h = common::harness::GatewayHarness::new().await;

    let email_a = common::harness::GatewayHarness::unique_email("lv-del-cross-a");
    let token_a = h.signup_and_get_token(&email_a, "Test1234!").await;

    let create: serde_json::Value = h
        .post_auth(
            "/api/v2/workspace/lookup-values",
            json!({
                "type": "niche",
                "value": "lv_del_guard",
                "label": "LV Del Guard",
            }),
            &token_a,
        )
        .await
        .json()
        .await
        .unwrap();
    let id = create["id"].as_i64().unwrap();

    let email_b = common::harness::GatewayHarness::unique_email("lv-del-cross-b");
    let token_b = h.signup_and_get_token(&email_b, "Test1234!").await;

    let del = h
        .client
        .delete(format!("{}/api/v2/lookup-values/{id}", h.base_url))
        .bearer_auth(&token_b)
        .send()
        .await
        .unwrap();
    assert_eq!(
        del.status(),
        403,
        "cross-workspace delete should be forbidden"
    );

    cleanup_lookup_values(&h, "LV Del Guard").await;
    h.cleanup().await;
}

#[tokio::test]
async fn test_lookup_value_not_found_returns_404() {
    let h = common::harness::GatewayHarness::new().await;
    let email = common::harness::GatewayHarness::unique_email("lv-404");
    let token = h.signup_and_get_token(&email, "Test1234!").await;

    let patch = h
        .client
        .patch(format!("{}/api/v2/lookup-values/999999999", h.base_url))
        .bearer_auth(&token)
        .json(&json!({ "label": "Ghost" }))
        .send()
        .await
        .unwrap();
    assert_eq!(patch.status(), 404, "nonexistent id should return 404");

    let del = h
        .client
        .delete(format!("{}/api/v2/lookup-values/999999999", h.base_url))
        .bearer_auth(&token)
        .send()
        .await
        .unwrap();
    assert_eq!(del.status(), 404, "nonexistent id should return 404");

    h.cleanup().await;
}
