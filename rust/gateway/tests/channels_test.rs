//! Integration tests for /api/v2/channels — GH #675, AE-587.
//!
//! Requires a live Postgres instance. Set TEST_DATABASE_URL or these tests
//! will be skipped. Run with:
//!   TEST_DATABASE_URL=postgresql://... cargo test --test channels_test -- --nocapture

mod common;

use serde_json::json;

// ── Helpers ───────────────────────────────────────────────────────────────────

async fn cleanup_channel(h: &common::harness::GatewayHarness, channel_id: &str) {
    let _ = sqlx::query("DELETE FROM channel_memory WHERE channel_id=$1")
        .bind(channel_id)
        .execute(&h.pool)
        .await;
    let _ = sqlx::query("DELETE FROM channel_references WHERE channel_id=$1")
        .bind(channel_id)
        .execute(&h.pool)
        .await;
    let _ = sqlx::query("DELETE FROM channel_topic_rules WHERE channel_id=$1")
        .bind(channel_id)
        .execute(&h.pool)
        .await;
    let _ = sqlx::query("DELETE FROM channel_pillars WHERE channel_id=$1")
        .bind(channel_id)
        .execute(&h.pool)
        .await;
    let _ = sqlx::query("DELETE FROM channel_profiles WHERE channel_id=$1")
        .bind(channel_id)
        .execute(&h.pool)
        .await;
    let _ = sqlx::query("DELETE FROM channels WHERE channel_id=$1")
        .bind(channel_id)
        .execute(&h.pool)
        .await;
}

// ── Tests ─────────────────────────────────────────────────────────────────────

#[tokio::test]
async fn test_create_and_list_channels() {
    let h = common::harness::GatewayHarness::new().await;
    let email = common::harness::GatewayHarness::unique_email("ch-create");
    let token = h.signup_and_get_token(&email, "Test1234!").await;

    // Create
    let resp = h
        .post_auth(
            "/api/v2/channels",
            json!({
                "channel_name": "Harness Test Channel",
                "niche": "science",
                "platform": "youtube",
            }),
            &token,
        )
        .await;

    assert_eq!(resp.status(), 200, "create should return 200");
    let body: serde_json::Value = resp.json().await.unwrap();
    assert_eq!(body["status"], "ok");
    let channel_id = body["channel_id"].as_str().unwrap().to_string();

    // List
    let list_resp = h
        .get_auth("/api/v2/channels", &token)
        .await;
    assert_eq!(list_resp.status(), 200);
    let list: serde_json::Value = list_resp.json().await.unwrap();
    let channels = list["data"].as_array().unwrap();
    assert!(
        channels.iter().any(|c| c["channel_id"] == channel_id),
        "created channel should appear in list"
    );

    cleanup_channel(&h, &channel_id).await;
    h.cleanup().await;
}

#[tokio::test]
async fn test_get_channel_full_bundle() {
    let h = common::harness::GatewayHarness::new().await;
    let email = common::harness::GatewayHarness::unique_email("ch-get");
    let token = h.signup_and_get_token(&email, "Test1234!").await;

    // Create with pillar and topic rule
    let create = h
        .post_auth(
            "/api/v2/channels",
            json!({
                "channel_name": "Bundle Test",
                "niche": "tech",
                "platform": "youtube",
                "pillars": [{"name": "Education", "weight": 1.0, "examples": [], "position": 0}],
                "topic_rules": [{"kind": "avoid", "value": "politics"}],
            }),
            &token,
        )
        .await;
    let create_body: serde_json::Value = create.json().await.unwrap();
    let channel_id = create_body["channel_id"].as_str().unwrap().to_string();

    // Get full bundle
    let resp = h
        .get_auth(&format!("/api/v2/channels/{channel_id}"), &token)
        .await;
    assert_eq!(resp.status(), 200);
    let body: serde_json::Value = resp.json().await.unwrap();
    let data = &body["data"];
    assert_eq!(data["channel"]["channel_id"], channel_id);
    assert!(data["pillars"].as_array().map(|a| !a.is_empty()).unwrap_or(false));
    assert!(data["topic_rules"].as_array().map(|a| !a.is_empty()).unwrap_or(false));

    cleanup_channel(&h, &channel_id).await;
    h.cleanup().await;
}

#[tokio::test]
async fn test_patch_channel() {
    let h = common::harness::GatewayHarness::new().await;
    let email = common::harness::GatewayHarness::unique_email("ch-patch");
    let token = h.signup_and_get_token(&email, "Test1234!").await;

    let create: serde_json::Value = h
        .post_auth(
            "/api/v2/channels",
            json!({"channel_name": "Pre-Patch", "niche": "gaming", "platform": "youtube"}),
            &token,
        )
        .await
        .json()
        .await
        .unwrap();
    let channel_id = create["channel_id"].as_str().unwrap().to_string();

    // Patch
    let patch = h
        .client
        .put(format!("{}/api/v2/channels/{channel_id}", h.base_url))
        .bearer_auth(&token)
        .json(&json!({"channel_name": "Post-Patch"}))
        .send()
        .await
        .unwrap();
    assert_eq!(patch.status(), 200);
    let patch_body: serde_json::Value = patch.json().await.unwrap();
    assert_eq!(patch_body["status"], "ok");

    // Verify
    let get: serde_json::Value = h
        .get_auth(&format!("/api/v2/channels/{channel_id}"), &token)
        .await
        .json()
        .await
        .unwrap();
    assert_eq!(get["data"]["channel"]["channel_name"], "Post-Patch");

    cleanup_channel(&h, &channel_id).await;
    h.cleanup().await;
}

#[tokio::test]
async fn test_channel_status_lifecycle() {
    let h = common::harness::GatewayHarness::new().await;
    let email = common::harness::GatewayHarness::unique_email("ch-status");
    let token = h.signup_and_get_token(&email, "Test1234!").await;

    let create: serde_json::Value = h
        .post_auth(
            "/api/v2/channels",
            json!({"channel_name": "Status Test", "niche": "fitness", "platform": "youtube"}),
            &token,
        )
        .await
        .json()
        .await
        .unwrap();
    let channel_id = create["channel_id"].as_str().unwrap().to_string();

    for (action, expected_status) in [
        ("disable", "disabled"),
        ("enable", "active"),
        ("archive", "archived"),
        ("restore", "disabled"),
    ] {
        let resp = h
            .client
            .put(format!("{}/api/v2/channels/{channel_id}/{action}", h.base_url))
            .bearer_auth(&token)
            .send()
            .await
            .unwrap();
        assert_eq!(resp.status(), 200, "{action} should return 200");

        let get: serde_json::Value = h
            .get_auth(&format!("/api/v2/channels/{channel_id}"), &token)
            .await
            .json()
            .await
            .unwrap();
        assert_eq!(
            get["data"]["channel"]["status"], expected_status,
            "{action} should set status to {expected_status}"
        );
    }

    cleanup_channel(&h, &channel_id).await;
    h.cleanup().await;
}

#[tokio::test]
async fn test_pillars_crud() {
    let h = common::harness::GatewayHarness::new().await;
    let email = common::harness::GatewayHarness::unique_email("ch-pillars");
    let token = h.signup_and_get_token(&email, "Test1234!").await;

    let create: serde_json::Value = h
        .post_auth(
            "/api/v2/channels",
            json!({"channel_name": "Pillar Test", "niche": "cooking", "platform": "youtube"}),
            &token,
        )
        .await
        .json()
        .await
        .unwrap();
    let channel_id = create["channel_id"].as_str().unwrap().to_string();

    // Add pillar
    let add: serde_json::Value = h
        .post_auth(
            &format!("/api/v2/channels/{channel_id}/pillars"),
            json!({"name": "Recipes", "weight": 1.0, "examples": ["pasta"], "position": 0}),
            &token,
        )
        .await
        .json()
        .await
        .unwrap();
    assert_eq!(add["status"], "ok");
    let pillar_id = add["id"].as_i64().unwrap();

    // Update pillar
    let upd = h
        .client
        .put(format!("{}/api/v2/channels/{channel_id}/pillars/{pillar_id}", h.base_url))
        .bearer_auth(&token)
        .json(&json!({"name": "Baking", "weight": 1.5, "examples": ["bread"], "position": 1}))
        .send()
        .await
        .unwrap();
    assert_eq!(upd.status(), 200);

    // Delete pillar
    let del = h
        .client
        .delete(format!("{}/api/v2/channels/{channel_id}/pillars/{pillar_id}", h.base_url))
        .bearer_auth(&token)
        .send()
        .await
        .unwrap();
    assert_eq!(del.status(), 200);

    cleanup_channel(&h, &channel_id).await;
    h.cleanup().await;
}

#[tokio::test]
async fn test_topic_rules_and_references() {
    let h = common::harness::GatewayHarness::new().await;
    let email = common::harness::GatewayHarness::unique_email("ch-rules");
    let token = h.signup_and_get_token(&email, "Test1234!").await;

    let create: serde_json::Value = h
        .post_auth(
            "/api/v2/channels",
            json!({"channel_name": "Rules Test", "niche": "travel", "platform": "youtube"}),
            &token,
        )
        .await
        .json()
        .await
        .unwrap();
    let channel_id = create["channel_id"].as_str().unwrap().to_string();

    // Topic rule
    let rule: serde_json::Value = h
        .post_auth(
            &format!("/api/v2/channels/{channel_id}/topic-rules"),
            json!({"kind": "avoid", "value": "violence"}),
            &token,
        )
        .await
        .json()
        .await
        .unwrap();
    assert_eq!(rule["status"], "ok");
    let rule_id = rule["id"].as_i64().unwrap();

    let del_rule = h
        .client
        .delete(format!("{}/api/v2/channels/{channel_id}/topic-rules/{rule_id}", h.base_url))
        .bearer_auth(&token)
        .send()
        .await
        .unwrap();
    assert_eq!(del_rule.status(), 200);

    // Reference
    let reference: serde_json::Value = h
        .post_auth(
            &format!("/api/v2/channels/{channel_id}/references"),
            json!({"kind": "url", "label": "Inspiration", "uri": "https://example.com"}),
            &token,
        )
        .await
        .json()
        .await
        .unwrap();
    assert_eq!(reference["status"], "ok");
    let ref_id = reference["id"].as_i64().unwrap();

    let del_ref = h
        .client
        .delete(format!("{}/api/v2/channels/{channel_id}/references/{ref_id}", h.base_url))
        .bearer_auth(&token)
        .send()
        .await
        .unwrap();
    assert_eq!(del_ref.status(), 200);

    cleanup_channel(&h, &channel_id).await;
    h.cleanup().await;
}

#[tokio::test]
async fn test_drafts_lifecycle() {
    let h = common::harness::GatewayHarness::new().await;
    let email = common::harness::GatewayHarness::unique_email("ch-drafts");
    let token = h.signup_and_get_token(&email, "Test1234!").await;

    // Create draft
    let create: serde_json::Value = h
        .post_auth(
            "/api/v2/channels/drafts",
            json!({"current_step": 1, "payload": {"channel_name": "Draft Channel"}}),
            &token,
        )
        .await
        .json()
        .await
        .unwrap();
    assert_eq!(create["status"], "ok");
    let draft_id = create["id"].as_i64().unwrap();

    // Save draft
    let save = h
        .client
        .put(format!("{}/api/v2/channels/drafts/{draft_id}", h.base_url))
        .bearer_auth(&token)
        .json(&json!({"current_step": 2, "payload": {"channel_name": "Draft Channel Step 2"}}))
        .send()
        .await
        .unwrap();
    assert_eq!(save.status(), 200);

    // Get draft
    let get: serde_json::Value = h
        .get_auth(&format!("/api/v2/channels/drafts/{draft_id}"), &token)
        .await
        .json()
        .await
        .unwrap();
    assert_eq!(get["data"]["current_step"], 2);
    assert_eq!(get["data"]["payload"]["channel_name"], "Draft Channel Step 2");

    // Cleanup draft
    let _ = sqlx::query("DELETE FROM channel_drafts WHERE id=$1")
        .bind(draft_id)
        .execute(&h.pool)
        .await;
    h.cleanup().await;
}

#[tokio::test]
async fn test_field_suggest_heuristic() {
    let h = common::harness::GatewayHarness::new().await;
    let email = common::harness::GatewayHarness::unique_email("ch-suggest");
    let token = h.signup_and_get_token(&email, "Test1234!").await;

    let resp = h
        .post_auth(
            "/api/v2/channels/ai/field-suggest",
            json!({"field": "mission", "context": {"niche": "cooking", "channel_name": "Chef Life"}}),
            &token,
        )
        .await;
    assert_eq!(resp.status(), 200);
    let body: serde_json::Value = resp.json().await.unwrap();
    let suggestion = body["data"]["suggestion"].as_str().unwrap_or("");
    assert!(!suggestion.is_empty(), "field suggest should return a non-empty suggestion");
    assert_eq!(body["data"]["rationale"], "heuristic");

    h.cleanup().await;
}

#[tokio::test]
async fn test_create_channel_rejects_non_youtube_platform() {
    let h = common::harness::GatewayHarness::new().await;
    let email = common::harness::GatewayHarness::unique_email("ch-platform");
    let token = h.signup_and_get_token(&email, "Test1234!").await;

    let resp = h
        .post_auth(
            "/api/v2/channels",
            json!({"channel_name": "TikTok Test", "niche": "dance", "platform": "tiktok"}),
            &token,
        )
        .await;
    assert_eq!(resp.status(), 400, "non-youtube platform should be rejected");

    h.cleanup().await;
}

#[tokio::test]
async fn test_list_channels_excludes_archived_by_default() {
    let h = common::harness::GatewayHarness::new().await;
    let email = common::harness::GatewayHarness::unique_email("ch-archived");
    let token = h.signup_and_get_token(&email, "Test1234!").await;

    let create: serde_json::Value = h
        .post_auth(
            "/api/v2/channels",
            json!({"channel_name": "Archived Test", "niche": "history", "platform": "youtube"}),
            &token,
        )
        .await
        .json()
        .await
        .unwrap();
    let channel_id = create["channel_id"].as_str().unwrap().to_string();

    // Archive it
    h.client
        .put(format!("{}/api/v2/channels/{channel_id}/archive", h.base_url))
        .bearer_auth(&token)
        .send()
        .await
        .unwrap();

    // Default list should NOT include it
    let list: serde_json::Value = h
        .get_auth("/api/v2/channels", &token)
        .await
        .json()
        .await
        .unwrap();
    let channels = list["data"].as_array().unwrap();
    assert!(
        !channels.iter().any(|c| c["channel_id"] == channel_id),
        "archived channel should be hidden from default list"
    );

    // include_archived=true should include it
    let list_all: serde_json::Value = h
        .get_auth("/api/v2/channels?include_archived=true", &token)
        .await
        .json()
        .await
        .unwrap();
    let all = list_all["data"].as_array().unwrap();
    assert!(
        all.iter().any(|c| c["channel_id"] == channel_id),
        "archived channel should appear with include_archived=true"
    );

    cleanup_channel(&h, &channel_id).await;
    h.cleanup().await;
}
