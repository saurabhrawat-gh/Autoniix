-- ============================================================
-- YT Automation — Full Database Schema
-- Matches 10 Google Sheets tabs: Channel_DNA (63 cols),
-- Execution_Locks, Belief_Registry, Output_Log, Feedback_Loop,
-- Performance_Memory, Prompt_Registry, Trend_Intelligence,
-- API_Usage_Tracker, System_Config + Audit_Log
-- ============================================================

-- ── Tab 1: Channel_DNA (63 columns) ────────────────────────
CREATE TABLE IF NOT EXISTS channels (
    channel_id              VARCHAR(20)   PRIMARY KEY,
    channel_name            VARCHAR(255)  NOT NULL,
    youtube_channel_id      VARCHAR(50),
    niche                   VARCHAR(100)  NOT NULL,
    sub_niche               VARCHAR(100),
    belief_territory        VARCHAR(200),
    intellectual_lens       VARCHAR(200),
    topic_domain            TEXT,
    brand_voice             VARCHAR(100),
    narrative_rhythm        VARCHAR(100),
    emotional_contract      VARCHAR(200),
    content_style           VARCHAR(100)  DEFAULT 'educational_narrative',
    content_mode            VARCHAR(20)   DEFAULT 'short',
    planned_duration        INTEGER       DEFAULT 45,
    target_word_count       INTEGER       DEFAULT 80,
    max_script_words_long   INTEGER       DEFAULT 1200,
    min_script_words_long   INTEGER       DEFAULT 1000,
    max_script_words_short  INTEGER       DEFAULT 90,
    min_script_words_short  INTEGER       DEFAULT 70,
    words_per_video_long    INTEGER       DEFAULT 1100,
    words_per_video_short   INTEGER       DEFAULT 80,
    videos_per_week_long    INTEGER       DEFAULT 1,
    videos_per_week_short   INTEGER       DEFAULT 7,
    long_form_duration      INTEGER       DEFAULT 480,
    short_form_duration     INTEGER       DEFAULT 45,
    primary_format_long     VARCHAR(100)  DEFAULT 'educational_explainer',
    primary_format_short    VARCHAR(100)  DEFAULT 'hook_fact_payoff',
    target_audience         VARCHAR(200),
    cta_style_long          VARCHAR(100)  DEFAULT 'soft_subscribe_reminder',
    cta_style_short         VARCHAR(100)  DEFAULT 'none',
    hook_length_seconds_long  INTEGER     DEFAULT 8,
    hook_length_seconds_short INTEGER     DEFAULT 2,
    retention_target_long   DECIMAL(4,2)  DEFAULT 0.45,
    retention_target_short  DECIMAL(4,2)  DEFAULT 0.85,
    forbidden_words         TEXT,
    thumbnail_style         VARCHAR(100),
    primary_color           VARCHAR(10),
    secondary_color         VARCHAR(10),
    max_thumbnail_words     INTEGER       DEFAULT 4,
    visual_only_ratio       DECIMAL(4,2)  DEFAULT 0.12,
    font_family             VARCHAR(100)  DEFAULT 'Inter',
    caption_style           VARCHAR(100)  DEFAULT 'word_highlight',
    color_grade_preset      VARCHAR(100),
    pacing_style            VARCHAR(100),
    intro_template          VARCHAR(100),
    outro_template          VARCHAR(100),
    posting_frequency       VARCHAR(50)   DEFAULT 'daily',
    weekly_day              VARCHAR(20),
    timezone                VARCHAR(50)   DEFAULT 'Asia/Kolkata',
    competitor_channels     TEXT,
    topics_queue            TEXT,
    elevenlabs_voice_id     VARCHAR(100),
    voice_stability         DECIMAL(4,2)  DEFAULT 0.50,
    voice_similarity        DECIMAL(4,2)  DEFAULT 0.75,
    voice_style             DECIMAL(4,2)  DEFAULT 0.40,
    video_template          VARCHAR(100),
    music_mood_default      VARCHAR(100),
    sfx_density             VARCHAR(50)   DEFAULT 'low',
    target_ctr              DECIMAL(5,3)  DEFAULT 0.080,
    target_avd_percent      DECIMAL(5,3)  DEFAULT 0.450,
    max_daily_api_spend     DECIMAL(8,2)  DEFAULT 5.00,
    human_review_required   VARCHAR(50)   DEFAULT 'first_10',
    status                  VARCHAR(20)   DEFAULT 'active',
    created_at              TIMESTAMPTZ   DEFAULT NOW(),
    updated_at              TIMESTAMPTZ   DEFAULT NOW()
);

-- ── Tab 2: Execution_Locks ──────────────────────────────────
CREATE TABLE IF NOT EXISTS execution_locks (
    id                  BIGSERIAL     PRIMARY KEY,
    channel_id          VARCHAR(20)   REFERENCES channels(channel_id),
    execution_week      VARCHAR(10)   NOT NULL,
    execution_id        VARCHAR(100)  UNIQUE NOT NULL,
    run_id              VARCHAR(200),
    status              VARCHAR(20)   DEFAULT 'locked',
    locked_at           TIMESTAMPTZ   DEFAULT NOW(),
    lock_expires_at     TIMESTAMPTZ,
    completed_at        TIMESTAMPTZ,
    UNIQUE(channel_id, execution_week)
);

-- ── Tab 3: Belief_Registry ──────────────────────────────────
CREATE TABLE IF NOT EXISTS belief_registry (
    belief_id           VARCHAR(50)   PRIMARY KEY,
    channel_id          VARCHAR(20)   REFERENCES channels(channel_id),
    belief              TEXT          NOT NULL,
    counter_narrative   TEXT,
    angle               VARCHAR(200),
    topic               TEXT,
    belief_status       VARCHAR(20)   DEFAULT 'available',
    times_used          INTEGER       DEFAULT 0,
    first_used_date     DATE,
    last_used_date      DATE,
    cooling_until_date  DATE,
    video_id            VARCHAR(100),
    idea_score          DECIMAL(4,2),
    created_at          TIMESTAMPTZ   DEFAULT NOW()
);

-- ── Tab 4: Output_Log (videos — 49+ columns) ───────────────
CREATE TABLE IF NOT EXISTS videos (
    id                      BIGSERIAL     PRIMARY KEY,
    content_id              VARCHAR(100)  UNIQUE NOT NULL,
    channel_id              VARCHAR(20)   REFERENCES channels(channel_id),
    status                  VARCHAR(30)   DEFAULT 'pending',
    content_mode            VARCHAR(20),
    title                   TEXT,
    topic                   TEXT,
    research_brief          JSONB         DEFAULT '{}',
    research_brief_url      TEXT,
    research_depth_score    DECIMAL(4,2),
    fact_confidence_score   DECIMAL(4,2),
    idea_data               JSONB         DEFAULT '{}',
    idea_score              DECIMAL(4,2),
    selected_hook           TEXT,
    script_base             JSONB         DEFAULT '{}',
    script_v1_url           TEXT,
    script_v2_url           TEXT,
    script_v3_url           TEXT,
    script_structure_score  DECIMAL(4,2),
    script_critic_scores    JSONB         DEFAULT '{}',
    hook_retention_score    DECIMAL(4,2),
    voice_result            JSONB         DEFAULT '{}',
    voice_duration_s        DECIMAL(8,2),
    voice_quality_score     DECIMAL(4,2),
    asset_manifest          JSONB         DEFAULT '{}',
    stock_footage_count     INTEGER       DEFAULT 0,
    generated_image_count   INTEGER       DEFAULT 0,
    thumbnail_result        JSONB         DEFAULT '{}',
    thumbnail_variants_urls TEXT,
    thumbnail_ctr_prediction DECIMAL(5,3),
    thumbnail_score         DECIMAL(4,2),
    direction_plan          JSONB         DEFAULT '{}',
    direction_plan_url      TEXT,
    direction_score         DECIMAL(4,2),
    v3_direction            JSONB         DEFAULT '{}',
    storyboard_url          TEXT,
    production_score        DECIMAL(4,2),
    render_result           JSONB         DEFAULT '{}',
    rendered_video_url      TEXT,
    render_duration_s       DECIMAL(8,2),
    delivery_result         JSONB         DEFAULT '{}',
    youtube_video_id        VARCHAR(50),
    youtube_metadata_url    TEXT,
    scores                  JSONB         DEFAULT '{}',
    quality_report          JSONB         DEFAULT '{}',
    final_composite_score   DECIMAL(4,2),
    score_report_url        TEXT,
    policy_check_result     JSONB         DEFAULT '{}',
    content_fingerprint     VARCHAR(64),
    cross_channel_similarity DECIMAL(4,2),
    checkpoint              VARCHAR(50),
    checkpoint_data_url     TEXT,
    paused_at               TIMESTAMPTZ,
    resume_from             VARCHAR(50),
    total_cost              DECIMAL(10,4) DEFAULT 0,
    idempotency_key         VARCHAR(100),
    workflow_id             VARCHAR(200),
    error_message           TEXT,
    approved_by             VARCHAR(100),
    approved_at             TIMESTAMPTZ,
    ai_disclosure           BOOLEAN       DEFAULT TRUE,
    niche_disclaimer        TEXT,
    created_at              TIMESTAMPTZ   DEFAULT NOW(),
    updated_at              TIMESTAMPTZ   DEFAULT NOW()
);

-- ── Tab 5: Feedback_Loop ────────────────────────────────────
CREATE TABLE IF NOT EXISTS feedback_loop (
    id                      BIGSERIAL     PRIMARY KEY,
    video_id                VARCHAR(100)  REFERENCES videos(content_id),
    channel_id              VARCHAR(20)   REFERENCES channels(channel_id),
    title                   TEXT,
    idea_score              DECIMAL(4,2),
    script_score            DECIMAL(4,2),
    thumbnail_score         DECIMAL(4,2),
    hook_retention_score    DECIMAL(4,2),
    final_score             DECIMAL(4,2),
    content_mode            VARCHAR(20),
    status                  VARCHAR(30),
    render_id               VARCHAR(100),
    render_video_url        TEXT,
    yt_video_id             VARCHAR(50),
    yt_views                INTEGER       DEFAULT 0,
    yt_likes                INTEGER       DEFAULT 0,
    yt_comments             INTEGER       DEFAULT 0,
    yt_ctr                  DECIMAL(5,3),
    yt_avg_view_duration    DECIMAL(8,2),
    yt_view_velocity_48h    INTEGER       DEFAULT 0,
    engagement_rate         DECIMAL(5,3),
    performance_tier        VARCHAR(20),
    analytics_status        VARCHAR(30)   DEFAULT 'pending',
    analytics_fetched_at    TIMESTAMPTZ,
    created_at              TIMESTAMPTZ   DEFAULT NOW(),
    updated_at              TIMESTAMPTZ   DEFAULT NOW()
);

-- ── Tab 6: Performance_Memory ───────────────────────────────
CREATE TABLE IF NOT EXISTS performance_memory (
    memory_id           VARCHAR(50)   PRIMARY KEY,
    channel_id          VARCHAR(20)   REFERENCES channels(channel_id),
    learning_type       VARCHAR(50)   NOT NULL,
    learning_value      TEXT          NOT NULL,
    evidence            TEXT,
    confidence          DECIMAL(4,2)  DEFAULT 0.50,
    applicable_to       TEXT,
    used_count          INTEGER       DEFAULT 0,
    still_valid         BOOLEAN       DEFAULT TRUE,
    created_at          TIMESTAMPTZ   DEFAULT NOW(),
    updated_at          TIMESTAMPTZ   DEFAULT NOW()
);

-- ── Tab 7: Prompt_Registry ──────────────────────────────────
CREATE TABLE IF NOT EXISTS prompt_registry (
    prompt_id           VARCHAR(100)  PRIMARY KEY,
    module              VARCHAR(50)   NOT NULL,
    prompt_name         VARCHAR(200)  NOT NULL,
    system_prompt       TEXT          NOT NULL,
    user_prompt_template TEXT         NOT NULL,
    version             INTEGER       DEFAULT 1,
    is_active           BOOLEAN       DEFAULT TRUE,
    created_at          TIMESTAMPTZ   DEFAULT NOW(),
    notes               TEXT
);

-- ── Tab 8: Trend_Intelligence ───────────────────────────────
CREATE TABLE IF NOT EXISTS trend_intelligence (
    trend_id            VARCHAR(50)   PRIMARY KEY,
    channel_id          VARCHAR(20)   REFERENCES channels(channel_id),
    niche               VARCHAR(100),
    trend_type          VARCHAR(50),
    trend_title         TEXT,
    trend_description   TEXT,
    source              VARCHAR(100),
    source_url          TEXT,
    detected_at         TIMESTAMPTZ   DEFAULT NOW(),
    relevance_score     DECIMAL(4,2),
    virality_potential  DECIMAL(4,2),
    competition_level   VARCHAR(20),
    freshness           VARCHAR(20),
    status              VARCHAR(20)   DEFAULT 'active',
    used_in_video_id    VARCHAR(100),
    expires_at          TIMESTAMPTZ
);

-- ── Tab 9: API_Usage_Tracker ────────────────────────────────
CREATE TABLE IF NOT EXISTS api_usage (
    id                  BIGSERIAL     PRIMARY KEY,
    date                DATE          DEFAULT CURRENT_DATE,
    content_id          VARCHAR(100),
    channel_id          VARCHAR(20),
    service             VARCHAR(50)   NOT NULL,
    provider            VARCHAR(50)   NOT NULL,
    model               VARCHAR(100),
    openai_tokens_in    INTEGER       DEFAULT 0,
    openai_tokens_out   INTEGER       DEFAULT 0,
    openai_cost         DECIMAL(10,6) DEFAULT 0,
    claude_tokens_in    INTEGER       DEFAULT 0,
    claude_tokens_out   INTEGER       DEFAULT 0,
    claude_cost         DECIMAL(10,6) DEFAULT 0,
    gemini_tokens       INTEGER       DEFAULT 0,
    gemini_cost         DECIMAL(10,6) DEFAULT 0,
    elevenlabs_chars    INTEGER       DEFAULT 0,
    dalle_calls         INTEGER       DEFAULT 0,
    youtube_api_units   INTEGER       DEFAULT 0,
    pixabay_calls       INTEGER       DEFAULT 0,
    pexels_calls        INTEGER       DEFAULT 0,
    serpapi_calls        INTEGER       DEFAULT 0,
    remotion_renders    INTEGER       DEFAULT 0,
    tokens_in           INTEGER       DEFAULT 0,
    tokens_out          INTEGER       DEFAULT 0,
    cost_usd            DECIMAL(10,6) DEFAULT 0,
    latency_ms          INTEGER       DEFAULT 0,
    total_cost          DECIMAL(10,6) DEFAULT 0,
    success             BOOLEAN       DEFAULT TRUE,
    error_message       TEXT,
    created_at          TIMESTAMPTZ   DEFAULT NOW()
);

-- ── Tab 10: System_Config ───────────────────────────────────
CREATE TABLE IF NOT EXISTS system_config (
    config_key          VARCHAR(100)  PRIMARY KEY,
    config_value        TEXT          NOT NULL,
    description         TEXT,
    updated_by          VARCHAR(100)  DEFAULT 'system',
    updated_at          TIMESTAMPTZ   DEFAULT NOW()
);

-- ── Audit_Log ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS audit_log (
    id               BIGSERIAL     PRIMARY KEY,
    actor            VARCHAR(200)  NOT NULL,
    action           VARCHAR(100)  NOT NULL,
    resource_type    VARCHAR(50),
    resource_id      VARCHAR(200),
    details          JSONB         DEFAULT '{}',
    created_at       TIMESTAMPTZ   DEFAULT NOW()
);

-- ════════════════════════════════════════════════════════════
-- INDEXES
-- ════════════════════════════════════════════════════════════
CREATE INDEX IF NOT EXISTS idx_channels_niche         ON channels(niche);
CREATE INDEX IF NOT EXISTS idx_channels_status        ON channels(status);
CREATE INDEX IF NOT EXISTS idx_exec_locks_channel     ON execution_locks(channel_id);
CREATE INDEX IF NOT EXISTS idx_exec_locks_week        ON execution_locks(execution_week);
CREATE INDEX IF NOT EXISTS idx_beliefs_channel        ON belief_registry(channel_id);
CREATE INDEX IF NOT EXISTS idx_beliefs_status         ON belief_registry(belief_status);
CREATE INDEX IF NOT EXISTS idx_videos_channel         ON videos(channel_id);
CREATE INDEX IF NOT EXISTS idx_videos_status          ON videos(status);
CREATE INDEX IF NOT EXISTS idx_videos_created         ON videos(created_at);
CREATE INDEX IF NOT EXISTS idx_videos_fingerprint     ON videos(content_fingerprint);
CREATE INDEX IF NOT EXISTS idx_videos_workflow        ON videos(workflow_id);
CREATE INDEX IF NOT EXISTS idx_videos_checkpoint      ON videos(checkpoint);
CREATE INDEX IF NOT EXISTS idx_feedback_channel       ON feedback_loop(channel_id);
CREATE INDEX IF NOT EXISTS idx_feedback_video         ON feedback_loop(video_id);
CREATE INDEX IF NOT EXISTS idx_perf_memory_channel    ON performance_memory(channel_id);
CREATE INDEX IF NOT EXISTS idx_perf_memory_type       ON performance_memory(learning_type);
CREATE INDEX IF NOT EXISTS idx_prompts_module         ON prompt_registry(module);
CREATE INDEX IF NOT EXISTS idx_trends_channel         ON trend_intelligence(channel_id);
CREATE INDEX IF NOT EXISTS idx_trends_niche           ON trend_intelligence(niche);
CREATE INDEX IF NOT EXISTS idx_trends_status          ON trend_intelligence(status);
CREATE INDEX IF NOT EXISTS idx_usage_content          ON api_usage(content_id);
CREATE INDEX IF NOT EXISTS idx_usage_date             ON api_usage(date);
CREATE INDEX IF NOT EXISTS idx_usage_provider         ON api_usage(provider);
CREATE INDEX IF NOT EXISTS idx_audit_actor            ON audit_log(actor);
CREATE INDEX IF NOT EXISTS idx_audit_created          ON audit_log(created_at);
CREATE INDEX IF NOT EXISTS idx_audit_resource         ON audit_log(resource_type, resource_id);
