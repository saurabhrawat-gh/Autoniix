-- ============================================================
-- Enable pgvector extension for embeddings
CREATE EXTENSION IF NOT EXISTS vector;

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

-- ── Research Intelligence: Competitor Channels ────────────
CREATE TABLE IF NOT EXISTS competitor_channels (
    id                  BIGSERIAL     PRIMARY KEY,
    channel_id          VARCHAR(20)   REFERENCES channels(channel_id),
    competitor_yt_id    VARCHAR(50)   NOT NULL,
    competitor_name     VARCHAR(255),
    niche               VARCHAR(100),
    subscriber_count    INTEGER       DEFAULT 0,
    video_count         INTEGER       DEFAULT 0,
    avg_views           INTEGER       DEFAULT 0,
    avg_view_velocity   DECIMAL(10,2) DEFAULT 0,
    outlier_ratio       DECIMAL(5,3)  DEFAULT 0,
    last_scraped_at     TIMESTAMPTZ,
    created_at          TIMESTAMPTZ   DEFAULT NOW(),
    updated_at          TIMESTAMPTZ   DEFAULT NOW(),
    UNIQUE(channel_id, competitor_yt_id)
);

-- ── Research Intelligence: Competitor Videos ──────────────
CREATE TABLE IF NOT EXISTS competitor_videos (
    id                  BIGSERIAL     PRIMARY KEY,
    competitor_yt_id    VARCHAR(50)   NOT NULL,
    video_yt_id         VARCHAR(50)   UNIQUE NOT NULL,
    title               TEXT,
    description         TEXT,
    tags                TEXT,
    published_at        TIMESTAMPTZ,
    view_count          INTEGER       DEFAULT 0,
    like_count          INTEGER       DEFAULT 0,
    comment_count       INTEGER       DEFAULT 0,
    duration_seconds    INTEGER       DEFAULT 0,
    view_velocity_24h   INTEGER       DEFAULT 0,
    view_velocity_48h   INTEGER       DEFAULT 0,
    is_outlier          BOOLEAN       DEFAULT FALSE,
    outlier_multiplier  DECIMAL(6,2)  DEFAULT 1.0,
    niche               VARCHAR(100),
    title_embedding     vector(384),
    created_at          TIMESTAMPTZ   DEFAULT NOW(),
    updated_at          TIMESTAMPTZ   DEFAULT NOW()
);

-- ── Research Intelligence: Trend Signals ──────────────────
CREATE TABLE IF NOT EXISTS trend_signals (
    id                  BIGSERIAL     PRIMARY KEY,
    niche               VARCHAR(100)  NOT NULL,
    keyword             TEXT          NOT NULL,
    source              VARCHAR(50)   NOT NULL,
    signal_type         VARCHAR(50)   NOT NULL,
    momentum_score      DECIMAL(5,2)  DEFAULT 0,
    volume_index        INTEGER       DEFAULT 0,
    related_queries     JSONB         DEFAULT '[]',
    rising_queries      JSONB         DEFAULT '[]',
    burst_score         DECIMAL(5,2)  DEFAULT 0,
    is_burst            BOOLEAN       DEFAULT FALSE,
    snapshot_date       DATE          DEFAULT CURRENT_DATE,
    raw_data            JSONB         DEFAULT '{}',
    created_at          TIMESTAMPTZ   DEFAULT NOW(),
    UNIQUE(niche, keyword, source, snapshot_date)
);

-- ── Research Intelligence: Topic Embeddings (pgvector) ────
CREATE TABLE IF NOT EXISTS topic_embeddings (
    id                  BIGSERIAL     PRIMARY KEY,
    content_id          VARCHAR(100),
    channel_id          VARCHAR(20)   REFERENCES channels(channel_id),
    text_type           VARCHAR(30)   NOT NULL,
    text_content        TEXT          NOT NULL,
    embedding           vector(384)   NOT NULL,
    simhash             BIGINT,
    created_at          TIMESTAMPTZ   DEFAULT NOW()
);

-- ── Research Intelligence: Research Features (for ML) ─────
CREATE TABLE IF NOT EXISTS research_features (
    id                  BIGSERIAL     PRIMARY KEY,
    content_id          VARCHAR(100)  NOT NULL,
    channel_id          VARCHAR(20)   REFERENCES channels(channel_id),
    topic               TEXT,
    freshness_score     DECIMAL(5,3)  DEFAULT 0,
    novelty_score       DECIMAL(5,3)  DEFAULT 0,
    trend_momentum      DECIMAL(5,3)  DEFAULT 0,
    supply_demand_gap   DECIMAL(5,3)  DEFAULT 0,
    hookability_score   DECIMAL(5,3)  DEFAULT 0,
    competitor_gap      DECIMAL(5,3)  DEFAULT 0,
    burst_score         DECIMAL(5,3)  DEFAULT 0,
    seasonality_score   DECIMAL(5,3)  DEFAULT 0,
    phrase_novelty      DECIMAL(5,3)  DEFAULT 0,
    opportunity_score   DECIMAL(5,3)  DEFAULT 0,
    model_predicted     DECIMAL(5,3),
    bandit_arm          VARCHAR(100),
    was_selected        BOOLEAN       DEFAULT FALSE,
    created_at          TIMESTAMPTZ   DEFAULT NOW()
);

-- ── Research Intelligence: Performance Outcomes (labels) ──
CREATE TABLE IF NOT EXISTS performance_outcomes (
    id                  BIGSERIAL     PRIMARY KEY,
    content_id          VARCHAR(100)  UNIQUE NOT NULL,
    channel_id          VARCHAR(20)   REFERENCES channels(channel_id),
    yt_video_id         VARCHAR(50),
    impressions         INTEGER       DEFAULT 0,
    views_24h           INTEGER       DEFAULT 0,
    views_48h           INTEGER       DEFAULT 0,
    views_7d            INTEGER       DEFAULT 0,
    ctr                 DECIMAL(5,3)  DEFAULT 0,
    avg_view_duration   DECIMAL(8,2)  DEFAULT 0,
    avg_view_pct        DECIMAL(5,3)  DEFAULT 0,
    likes               INTEGER       DEFAULT 0,
    comments            INTEGER       DEFAULT 0,
    subs_gained         INTEGER       DEFAULT 0,
    engagement_rate     DECIMAL(5,3)  DEFAULT 0,
    is_success          BOOLEAN,
    success_tier        VARCHAR(20),
    fetched_at          TIMESTAMPTZ,
    created_at          TIMESTAMPTZ   DEFAULT NOW(),
    updated_at          TIMESTAMPTZ   DEFAULT NOW()
);

-- ── Research Intelligence: Model Store ────────────────────
CREATE TABLE IF NOT EXISTS ml_models (
    id                  BIGSERIAL     PRIMARY KEY,
    model_name          VARCHAR(100)  NOT NULL,
    model_version       INTEGER       DEFAULT 1,
    niche               VARCHAR(100),
    model_type          VARCHAR(50)   NOT NULL,
    model_blob          BYTEA,
    feature_names       JSONB         DEFAULT '[]',
    metrics             JSONB         DEFAULT '{}',
    training_samples    INTEGER       DEFAULT 0,
    is_active           BOOLEAN       DEFAULT TRUE,
    created_at          TIMESTAMPTZ   DEFAULT NOW(),
    UNIQUE(model_name, niche, model_version)
);

-- ── Research Intelligence: Bandit State ───────────────────
CREATE TABLE IF NOT EXISTS bandit_state (
    id                  BIGSERIAL     PRIMARY KEY,
    niche               VARCHAR(100)  NOT NULL,
    arm_name            VARCHAR(200)  NOT NULL,
    alpha               DECIMAL(10,2) DEFAULT 1,
    beta                DECIMAL(10,2) DEFAULT 1,
    pulls               INTEGER       DEFAULT 0,
    rewards             DECIMAL(10,4) DEFAULT 0,
    updated_at          TIMESTAMPTZ   DEFAULT NOW(),
    UNIQUE(niche, arm_name)
);

-- ── Research Intelligence: Phrase Bank ────────────────────
CREATE TABLE IF NOT EXISTS phrase_bank (
    id                  BIGSERIAL     PRIMARY KEY,
    niche               VARCHAR(100)  NOT NULL,
    phrase              TEXT          NOT NULL,
    source              VARCHAR(50),
    frequency           INTEGER       DEFAULT 1,
    is_rising           BOOLEAN       DEFAULT FALSE,
    first_seen          DATE          DEFAULT CURRENT_DATE,
    last_seen           DATE          DEFAULT CURRENT_DATE,
    UNIQUE(niche, phrase)
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

-- ── Research Intelligence Indexes ─────────────────────────
CREATE INDEX IF NOT EXISTS idx_comp_channels_channel   ON competitor_channels(channel_id);
CREATE INDEX IF NOT EXISTS idx_comp_channels_niche     ON competitor_channels(niche);
CREATE INDEX IF NOT EXISTS idx_comp_videos_yt_id       ON competitor_videos(competitor_yt_id);
CREATE INDEX IF NOT EXISTS idx_comp_videos_niche       ON competitor_videos(niche);
CREATE INDEX IF NOT EXISTS idx_comp_videos_outlier     ON competitor_videos(is_outlier) WHERE is_outlier = TRUE;
CREATE INDEX IF NOT EXISTS idx_comp_videos_published   ON competitor_videos(published_at);
CREATE INDEX IF NOT EXISTS idx_trend_signals_niche     ON trend_signals(niche);
CREATE INDEX IF NOT EXISTS idx_trend_signals_date      ON trend_signals(snapshot_date);
CREATE INDEX IF NOT EXISTS idx_trend_signals_burst     ON trend_signals(is_burst) WHERE is_burst = TRUE;
CREATE INDEX IF NOT EXISTS idx_topic_emb_channel       ON topic_embeddings(channel_id);
CREATE INDEX IF NOT EXISTS idx_topic_emb_type          ON topic_embeddings(text_type);
CREATE INDEX IF NOT EXISTS idx_research_feat_channel   ON research_features(channel_id);
CREATE INDEX IF NOT EXISTS idx_research_feat_content   ON research_features(content_id);
CREATE INDEX IF NOT EXISTS idx_perf_outcomes_channel   ON performance_outcomes(channel_id);
CREATE INDEX IF NOT EXISTS idx_perf_outcomes_success   ON performance_outcomes(is_success);
CREATE INDEX IF NOT EXISTS idx_ml_models_active        ON ml_models(model_name, niche) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_bandit_niche            ON bandit_state(niche);
CREATE INDEX IF NOT EXISTS idx_phrase_bank_niche       ON phrase_bank(niche);
CREATE INDEX IF NOT EXISTS idx_phrase_bank_rising      ON phrase_bank(is_rising) WHERE is_rising = TRUE;

-- ── Script Intelligence: Script Features (for ML) ──────────
CREATE TABLE IF NOT EXISTS script_features (
    id                      BIGSERIAL     PRIMARY KEY,
    content_id              VARCHAR(100)  NOT NULL,
    channel_id              VARCHAR(20)   REFERENCES channels(channel_id),
    topic                   TEXT,
    -- Structural features
    segment_count           INTEGER       DEFAULT 0,
    word_count              INTEGER       DEFAULT 0,
    avg_sentence_length     DECIMAL(5,2)  DEFAULT 0,
    sentence_length_variance DECIMAL(5,2) DEFAULT 0,
    -- Retention features
    hook_strength           DECIMAL(5,3)  DEFAULT 0,
    curiosity_loop_count    INTEGER       DEFAULT 0,
    open_loop_ratio         DECIMAL(5,3)  DEFAULT 0,
    pattern_interrupt_freq  DECIMAL(5,3)  DEFAULT 0,
    but_therefore_ratio     DECIMAL(5,3)  DEFAULT 0,
    -- Linguistic features
    contraction_rate        DECIMAL(5,3)  DEFAULT 0,
    question_density        DECIMAL(5,3)  DEFAULT 0,
    specificity_score       DECIMAL(5,3)  DEFAULT 0,
    readability_score       DECIMAL(5,2)  DEFAULT 0,
    -- Emotional features
    emotion_variance        DECIMAL(5,3)  DEFAULT 0,
    emphasis_density        DECIMAL(5,3)  DEFAULT 0,
    emotional_arc_score     DECIMAL(5,3)  DEFAULT 0,
    -- Quality scores (from critique)
    overall_script_score    DECIMAL(4,2)  DEFAULT 0,
    hook_retention_score    DECIMAL(4,2)  DEFAULT 0,
    -- Bandit context
    hook_style_used         VARCHAR(100),
    pacing_strategy_used    VARCHAR(100),
    was_selected            BOOLEAN       DEFAULT FALSE,
    created_at              TIMESTAMPTZ   DEFAULT NOW()
);

-- ── Script Intelligence: Script Outcomes (labels for ML) ───
CREATE TABLE IF NOT EXISTS script_outcomes (
    id                      BIGSERIAL     PRIMARY KEY,
    content_id              VARCHAR(100)  UNIQUE NOT NULL,
    channel_id              VARCHAR(20)   REFERENCES channels(channel_id),
    yt_video_id             VARCHAR(50),
    -- YouTube metrics (fetched 48h post-publish)
    impressions             INTEGER       DEFAULT 0,
    views_48h               INTEGER       DEFAULT 0,
    ctr                     DECIMAL(5,3)  DEFAULT 0,
    avg_view_pct            DECIMAL(5,3)  DEFAULT 0,
    avg_view_duration_s     DECIMAL(8,2)  DEFAULT 0,
    likes                   INTEGER       DEFAULT 0,
    comments                INTEGER       DEFAULT 0,
    -- Retention curve (sampled at 10 points: 0%, 10%, ..., 90%)
    retention_curve         JSONB         DEFAULT '[]',
    -- Computed labels
    engagement_rate         DECIMAL(5,3)  DEFAULT 0,
    is_success              BOOLEAN,
    success_tier            VARCHAR(20),
    -- What contributed
    hook_style_used         VARCHAR(100),
    pacing_strategy_used    VARCHAR(100),
    fetched_at              TIMESTAMPTZ,
    created_at              TIMESTAMPTZ   DEFAULT NOW(),
    updated_at              TIMESTAMPTZ   DEFAULT NOW()
);

-- ── Script Intelligence: Model Store ────────────────────────
CREATE TABLE IF NOT EXISTS script_models (
    id                      BIGSERIAL     PRIMARY KEY,
    model_name              VARCHAR(100)  NOT NULL,
    model_version           INTEGER       DEFAULT 1,
    niche                   VARCHAR(100),
    model_type              VARCHAR(50)   NOT NULL,
    model_blob              BYTEA,
    feature_names           JSONB         DEFAULT '[]',
    metrics                 JSONB         DEFAULT '{}',
    training_samples        INTEGER       DEFAULT 0,
    is_active               BOOLEAN       DEFAULT TRUE,
    created_at              TIMESTAMPTZ   DEFAULT NOW(),
    UNIQUE(model_name, niche, model_version)
);

-- ── Script Intelligence: Bandit State ───────────────────────
CREATE TABLE IF NOT EXISTS script_bandit_state (
    id                      BIGSERIAL     PRIMARY KEY,
    niche                   VARCHAR(100)  NOT NULL,
    bandit_type             VARCHAR(50)   NOT NULL,
    arm_name                VARCHAR(200)  NOT NULL,
    alpha                   DECIMAL(10,2) DEFAULT 1,
    beta                    DECIMAL(10,2) DEFAULT 1,
    pulls                   INTEGER       DEFAULT 0,
    rewards                 DECIMAL(10,4) DEFAULT 0,
    avg_reward              DECIMAL(8,4)  DEFAULT 0,
    updated_at              TIMESTAMPTZ   DEFAULT NOW(),
    UNIQUE(niche, bandit_type, arm_name)
);

-- ── Script Intelligence Indexes ─────────────────────────────
CREATE INDEX IF NOT EXISTS idx_script_feat_content    ON script_features(content_id);
CREATE INDEX IF NOT EXISTS idx_script_feat_channel    ON script_features(channel_id);
CREATE INDEX IF NOT EXISTS idx_script_out_content     ON script_outcomes(content_id);
CREATE INDEX IF NOT EXISTS idx_script_out_channel     ON script_outcomes(channel_id);
CREATE INDEX IF NOT EXISTS idx_script_out_success     ON script_outcomes(is_success);
CREATE INDEX IF NOT EXISTS idx_script_models_active   ON script_models(model_name, niche) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_script_bandit_niche    ON script_bandit_state(niche, bandit_type);

-- ══════════════════════════════════════════════════════════
-- ── Brand Identity Intelligence ──────────────────────────
-- ══════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS brand_profiles (
    id                      BIGSERIAL     PRIMARY KEY,
    channel_id              VARCHAR(20)   UNIQUE REFERENCES channels(channel_id),
    -- Visual identity
    color_palette           JSONB         DEFAULT '{}',
    fonts                   JSONB         DEFAULT '{}',
    logo_url                TEXT,
    watermark_url           TEXT,
    thumbnail_style_rules   JSONB         DEFAULT '{}',
    -- Voice identity
    voice_fingerprint       JSONB         DEFAULT '{}',
    vocabulary_whitelist    JSONB         DEFAULT '[]',
    vocabulary_blacklist    JSONB         DEFAULT '[]',
    speaking_style          JSONB         DEFAULT '{}',
    -- Content personality
    humor_level             DECIMAL(3,2)  DEFAULT 0.5,
    formality_level         DECIMAL(3,2)  DEFAULT 0.5,
    energy_level            DECIMAL(3,2)  DEFAULT 0.7,
    -- Templates
    intro_template_url      TEXT,
    outro_template_url      TEXT,
    lower_third_style       JSONB         DEFAULT '{}',
    -- Motion & editing style
    preferred_transitions   JSONB         DEFAULT '[]',
    pacing_profile          JSONB         DEFAULT '{}',
    camera_style_weights    JSONB         DEFAULT '{}',
    -- Multi-persona support
    personas                JSONB         DEFAULT '[]',
    active_persona          VARCHAR(100)  DEFAULT 'default',
    -- Computed
    brand_embedding         vector(384),
    consistency_score       DECIMAL(4,2)  DEFAULT 0,
    created_at              TIMESTAMPTZ   DEFAULT NOW(),
    updated_at              TIMESTAMPTZ   DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS brand_assets (
    id                      BIGSERIAL     PRIMARY KEY,
    channel_id              VARCHAR(20)   REFERENCES channels(channel_id),
    asset_type              VARCHAR(50)   NOT NULL,
    asset_name              VARCHAR(200),
    asset_url               TEXT          NOT NULL,
    metadata                JSONB         DEFAULT '{}',
    is_active               BOOLEAN       DEFAULT TRUE,
    created_at              TIMESTAMPTZ   DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS brand_style_history (
    id                      BIGSERIAL     PRIMARY KEY,
    channel_id              VARCHAR(20)   REFERENCES channels(channel_id),
    snapshot_date           DATE          NOT NULL,
    style_features          JSONB         DEFAULT '{}',
    performance_correlation JSONB         DEFAULT '{}',
    created_at              TIMESTAMPTZ   DEFAULT NOW(),
    UNIQUE(channel_id, snapshot_date)
);

-- ══════════════════════════════════════════════════════════
-- ── Voice Intelligence ───────────────────────────────────
-- ══════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS voice_features (
    id                      BIGSERIAL     PRIMARY KEY,
    content_id              VARCHAR(100)  NOT NULL,
    channel_id              VARCHAR(20)   REFERENCES channels(channel_id),
    segment_id              VARCHAR(50),
    -- TTS params used
    tts_provider            VARCHAR(50),
    stability               DECIMAL(4,3),
    similarity_boost        DECIMAL(4,3),
    style                   DECIMAL(4,3),
    speed                   DECIMAL(4,3),
    emotion                 VARCHAR(50),
    -- Audio quality metrics (local analysis)
    snr_db                  DECIMAL(6,2),
    rms_energy              DECIMAL(8,6),
    zero_crossing_rate      DECIMAL(8,6),
    spectral_centroid       DECIMAL(10,2),
    duration_s              DECIMAL(8,3),
    wpm                     DECIMAL(6,2),
    -- Quality scores
    audio_quality_score     DECIMAL(4,2)  DEFAULT 0,
    naturalness_score       DECIMAL(4,2)  DEFAULT 0,
    created_at              TIMESTAMPTZ   DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS voice_outcomes (
    id                      BIGSERIAL     PRIMARY KEY,
    content_id              VARCHAR(100)  UNIQUE NOT NULL,
    channel_id              VARCHAR(20)   REFERENCES channels(channel_id),
    avg_view_duration_s     DECIMAL(8,2)  DEFAULT 0,
    retention_at_30pct      DECIMAL(5,3)  DEFAULT 0,
    retention_at_50pct      DECIMAL(5,3)  DEFAULT 0,
    retention_at_70pct      DECIMAL(5,3)  DEFAULT 0,
    is_good_retention       BOOLEAN,
    created_at              TIMESTAMPTZ   DEFAULT NOW(),
    updated_at              TIMESTAMPTZ   DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS voice_models (
    id                      BIGSERIAL     PRIMARY KEY,
    model_name              VARCHAR(100)  NOT NULL,
    model_version           INTEGER       DEFAULT 1,
    niche                   VARCHAR(100),
    model_type              VARCHAR(50)   NOT NULL,
    model_blob              BYTEA,
    feature_names           JSONB         DEFAULT '[]',
    metrics                 JSONB         DEFAULT '{}',
    training_samples        INTEGER       DEFAULT 0,
    is_active               BOOLEAN       DEFAULT TRUE,
    created_at              TIMESTAMPTZ   DEFAULT NOW(),
    UNIQUE(model_name, niche, model_version)
);

-- ══════════════════════════════════════════════════════════
-- ── Asset Intelligence ───────────────────────────────────
-- ══════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS asset_library (
    id                      BIGSERIAL     PRIMARY KEY,
    query_hash              VARCHAR(64)   NOT NULL,
    query_text              TEXT          NOT NULL,
    provider                VARCHAR(50)   NOT NULL,
    provider_asset_id       VARCHAR(200),
    asset_url               TEXT          NOT NULL,
    minio_key               TEXT,
    asset_type              VARCHAR(50)   DEFAULT 'stock_video',
    -- Quality features
    resolution_width        INTEGER       DEFAULT 0,
    resolution_height       INTEGER       DEFAULT 0,
    duration_s              DECIMAL(8,2)  DEFAULT 0,
    dominant_colors         JSONB         DEFAULT '[]',
    quality_score           DECIMAL(4,2)  DEFAULT 7.0,
    relevance_score         DECIMAL(4,2)  DEFAULT 7.0,
    -- Usage tracking
    use_count               INTEGER       DEFAULT 0,
    last_used_at            TIMESTAMPTZ,
    -- Embedding for similarity
    query_embedding         vector(384),
    license_type            VARCHAR(100),
    tags                    TEXT,
    created_at              TIMESTAMPTZ   DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS asset_search_log (
    id                      BIGSERIAL     PRIMARY KEY,
    content_id              VARCHAR(100),
    channel_id              VARCHAR(20)   REFERENCES channels(channel_id),
    segment_id              VARCHAR(50),
    query_text              TEXT,
    provider                VARCHAR(50),
    results_count           INTEGER       DEFAULT 0,
    selected_asset_id       VARCHAR(200),
    used_cache              BOOLEAN       DEFAULT FALSE,
    used_dalle_fallback     BOOLEAN       DEFAULT FALSE,
    search_time_ms          INTEGER       DEFAULT 0,
    created_at              TIMESTAMPTZ   DEFAULT NOW()
);

-- ══════════════════════════════════════════════════════════
-- ── Thumbnail Intelligence ───────────────────────────────
-- ══════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS thumbnail_features (
    id                      BIGSERIAL     PRIMARY KEY,
    content_id              VARCHAR(100)  NOT NULL,
    channel_id              VARCHAR(20)   REFERENCES channels(channel_id),
    variant_id              INTEGER       DEFAULT 0,
    -- Composition features (local analysis)
    has_face                BOOLEAN       DEFAULT FALSE,
    face_area_ratio         DECIMAL(5,3)  DEFAULT 0,
    text_area_ratio         DECIMAL(5,3)  DEFAULT 0,
    dominant_color_rgb      VARCHAR(20),
    color_contrast_score    DECIMAL(4,2)  DEFAULT 0,
    brightness_score        DECIMAL(4,2)  DEFAULT 0,
    saturation_score        DECIMAL(4,2)  DEFAULT 0,
    rule_of_thirds_score    DECIMAL(4,2)  DEFAULT 0,
    -- Text features
    text_word_count         INTEGER       DEFAULT 0,
    text_font_size_ratio    DECIMAL(5,3)  DEFAULT 0,
    -- Scores
    local_composition_score DECIMAL(4,2)  DEFAULT 0,
    vision_qc_score         DECIMAL(4,2),
    predicted_ctr           DECIMAL(6,4)  DEFAULT 0,
    -- Embedding
    thumbnail_embedding     vector(384),
    created_at              TIMESTAMPTZ   DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS thumbnail_outcomes (
    id                      BIGSERIAL     PRIMARY KEY,
    content_id              VARCHAR(100)  UNIQUE NOT NULL,
    channel_id              VARCHAR(20)   REFERENCES channels(channel_id),
    actual_ctr              DECIMAL(6,4),
    impressions             INTEGER       DEFAULT 0,
    clicks                  INTEGER       DEFAULT 0,
    ctr_percentile          DECIMAL(5,2),
    is_above_avg_ctr        BOOLEAN,
    created_at              TIMESTAMPTZ   DEFAULT NOW(),
    updated_at              TIMESTAMPTZ   DEFAULT NOW()
);

-- ══════════════════════════════════════════════════════════
-- ── Direction Intelligence ───────────────────────────────
-- ══════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS direction_features (
    id                      BIGSERIAL     PRIMARY KEY,
    content_id              VARCHAR(100)  NOT NULL,
    channel_id              VARCHAR(20)   REFERENCES channels(channel_id),
    segment_count           INTEGER       DEFAULT 0,
    unique_scene_presets    INTEGER       DEFAULT 0,
    unique_camera_types     INTEGER       DEFAULT 0,
    avg_segment_duration_ms INTEGER       DEFAULT 0,
    has_motion_design       BOOLEAN       DEFAULT FALSE,
    transition_variety      INTEGER       DEFAULT 0,
    used_script_v3_hint     BOOLEAN       DEFAULT FALSE,
    llm_tokens_used         INTEGER       DEFAULT 0,
    direction_score         DECIMAL(4,2)  DEFAULT 0,
    created_at              TIMESTAMPTZ   DEFAULT NOW()
);

-- ══════════════════════════════════════════════════════════
-- ── Editor / Post-Production Intelligence ────────────────
-- ══════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS editor_sessions (
    id                      BIGSERIAL     PRIMARY KEY,
    content_id              VARCHAR(100)  NOT NULL,
    channel_id              VARCHAR(20)   REFERENCES channels(channel_id),
    -- Adjustments made
    pacing_adjustments      JSONB         DEFAULT '[]',
    transition_changes      JSONB         DEFAULT '[]',
    audio_mix_config        JSONB         DEFAULT '{}',
    color_grade_applied     VARCHAR(100),
    captions_generated      BOOLEAN       DEFAULT FALSE,
    caption_word_count      INTEGER       DEFAULT 0,
    -- Quality
    pre_edit_score          DECIMAL(4,2)  DEFAULT 0,
    post_edit_score         DECIMAL(4,2)  DEFAULT 0,
    total_adjustments       INTEGER       DEFAULT 0,
    edit_time_ms            INTEGER       DEFAULT 0,
    created_at              TIMESTAMPTZ   DEFAULT NOW()
);

-- ══════════════════════════════════════════════════════════
-- ── Assembly Intelligence ────────────────────────────────
-- ══════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS assembly_render_log (
    id                      BIGSERIAL     PRIMARY KEY,
    content_id              VARCHAR(100)  NOT NULL,
    channel_id              VARCHAR(20)   REFERENCES channels(channel_id),
    render_id               VARCHAR(200),
    -- Render params
    codec                   VARCHAR(50)   DEFAULT 'h264',
    quality                 VARCHAR(50)   DEFAULT 'high',
    segment_count           INTEGER       DEFAULT 0,
    direction_complexity    DECIMAL(4,2)  DEFAULT 0,
    -- Result
    render_success          BOOLEAN       DEFAULT FALSE,
    render_duration_s       DECIMAL(10,2) DEFAULT 0,
    video_duration_s        DECIMAL(10,2) DEFAULT 0,
    retry_count             INTEGER       DEFAULT 0,
    error_category          VARCHAR(100),
    -- Prediction
    predicted_success_prob  DECIMAL(5,3),
    production_score        DECIMAL(4,2)  DEFAULT 0,
    created_at              TIMESTAMPTZ   DEFAULT NOW()
);

-- ══════════════════════════════════════════════════════════
-- ── Delivery Intelligence ────────────────────────────────
-- ══════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS delivery_features (
    id                      BIGSERIAL     PRIMARY KEY,
    content_id              VARCHAR(100)  NOT NULL,
    channel_id              VARCHAR(20)   REFERENCES channels(channel_id),
    -- Timing
    upload_hour_utc         INTEGER,
    upload_day_of_week      INTEGER,
    optimal_hour_predicted  INTEGER,
    -- Metadata features
    title_word_count        INTEGER       DEFAULT 0,
    title_has_number        BOOLEAN       DEFAULT FALSE,
    title_has_question      BOOLEAN       DEFAULT FALSE,
    title_power_words       INTEGER       DEFAULT 0,
    description_length      INTEGER       DEFAULT 0,
    tag_count               INTEGER       DEFAULT 0,
    -- SEO
    seo_score               DECIMAL(4,2)  DEFAULT 0,
    keyword_density         DECIMAL(5,3)  DEFAULT 0,
    -- Outcome
    first_hour_views        INTEGER,
    first_day_views         INTEGER,
    created_at              TIMESTAMPTZ   DEFAULT NOW(),
    updated_at              TIMESTAMPTZ   DEFAULT NOW()
);

-- ══════════════════════════════════════════════════════════
-- ── Analytics Patterns (cross-service learning) ──────────
-- ══════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS analytics_patterns (
    id                      BIGSERIAL     PRIMARY KEY,
    channel_id              VARCHAR(20)   REFERENCES channels(channel_id),
    pattern_type            VARCHAR(100)  NOT NULL,
    pattern_key             VARCHAR(200)  NOT NULL,
    pattern_data            JSONB         DEFAULT '{}',
    confidence              DECIMAL(5,3)  DEFAULT 0,
    sample_count            INTEGER       DEFAULT 0,
    last_validated          TIMESTAMPTZ,
    created_at              TIMESTAMPTZ   DEFAULT NOW(),
    updated_at              TIMESTAMPTZ   DEFAULT NOW(),
    UNIQUE(channel_id, pattern_type, pattern_key)
);

-- ══════════════════════════════════════════════════════════
-- ── Intelligence Indexes ─────────────────────────────────
-- ══════════════════════════════════════════════════════════

CREATE INDEX IF NOT EXISTS idx_brand_profiles_channel   ON brand_profiles(channel_id);
CREATE INDEX IF NOT EXISTS idx_brand_assets_channel     ON brand_assets(channel_id);
CREATE INDEX IF NOT EXISTS idx_brand_assets_type        ON brand_assets(asset_type);
CREATE INDEX IF NOT EXISTS idx_brand_history_channel    ON brand_style_history(channel_id);

CREATE INDEX IF NOT EXISTS idx_voice_feat_content       ON voice_features(content_id);
CREATE INDEX IF NOT EXISTS idx_voice_feat_channel       ON voice_features(channel_id);
CREATE INDEX IF NOT EXISTS idx_voice_out_content        ON voice_outcomes(content_id);
CREATE INDEX IF NOT EXISTS idx_voice_models_active      ON voice_models(model_name, niche) WHERE is_active = TRUE;

CREATE INDEX IF NOT EXISTS idx_asset_lib_hash           ON asset_library(query_hash);
CREATE INDEX IF NOT EXISTS idx_asset_lib_provider       ON asset_library(provider);
CREATE INDEX IF NOT EXISTS idx_asset_lib_quality        ON asset_library(quality_score DESC);
CREATE INDEX IF NOT EXISTS idx_asset_search_content     ON asset_search_log(content_id);

CREATE INDEX IF NOT EXISTS idx_thumb_feat_content       ON thumbnail_features(content_id);
CREATE INDEX IF NOT EXISTS idx_thumb_feat_channel       ON thumbnail_features(channel_id);
CREATE INDEX IF NOT EXISTS idx_thumb_out_content        ON thumbnail_outcomes(content_id);
CREATE INDEX IF NOT EXISTS idx_thumb_out_ctr            ON thumbnail_outcomes(is_above_avg_ctr) WHERE is_above_avg_ctr = TRUE;

CREATE INDEX IF NOT EXISTS idx_dir_feat_content         ON direction_features(content_id);
CREATE INDEX IF NOT EXISTS idx_editor_sess_content      ON editor_sessions(content_id);
CREATE INDEX IF NOT EXISTS idx_assembly_render_content  ON assembly_render_log(content_id);
CREATE INDEX IF NOT EXISTS idx_delivery_feat_content    ON delivery_features(content_id);
CREATE INDEX IF NOT EXISTS idx_analytics_patterns_ch    ON analytics_patterns(channel_id, pattern_type);

-- ── A/B Testing Framework ─────────────────────────────────
-- ══════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS experiments (
    id                      BIGSERIAL     PRIMARY KEY,
    experiment_name         VARCHAR(200)  UNIQUE NOT NULL,
    description             TEXT,
    variants                JSONB         NOT NULL DEFAULT '[]',
    traffic_pct             REAL          DEFAULT 100.0,
    target_metric           VARCHAR(100)  DEFAULT 'views',
    status                  VARCHAR(20)   DEFAULT 'draft',
    winning_variant         VARCHAR(100),
    started_at              TIMESTAMPTZ,
    ended_at                TIMESTAMPTZ,
    created_at              TIMESTAMPTZ   DEFAULT NOW(),
    updated_at              TIMESTAMPTZ   DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS experiment_assignments (
    id                      BIGSERIAL     PRIMARY KEY,
    experiment_name         VARCHAR(200)  REFERENCES experiments(experiment_name),
    content_id              VARCHAR(100)  NOT NULL,
    channel_id              VARCHAR(20),
    variant_name            VARCHAR(100)  NOT NULL,
    assigned_at             TIMESTAMPTZ   DEFAULT NOW(),
    UNIQUE(experiment_name, content_id)
);

CREATE TABLE IF NOT EXISTS experiment_outcomes (
    id                      BIGSERIAL     PRIMARY KEY,
    experiment_name         VARCHAR(200)  REFERENCES experiments(experiment_name),
    content_id              VARCHAR(100)  NOT NULL,
    variant_name            VARCHAR(100)  NOT NULL,
    metrics                 JSONB         NOT NULL DEFAULT '{}',
    recorded_at             TIMESTAMPTZ   DEFAULT NOW(),
    UNIQUE(experiment_name, content_id)
);

CREATE INDEX IF NOT EXISTS idx_exp_assign_exp         ON experiment_assignments(experiment_name);
CREATE INDEX IF NOT EXISTS idx_exp_assign_content     ON experiment_assignments(content_id);
CREATE INDEX IF NOT EXISTS idx_exp_outcome_exp        ON experiment_outcomes(experiment_name);

-- ── Intelligence Observability ────────────────────────────
-- ══════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS intelligence_metrics (
    id                      BIGSERIAL     PRIMARY KEY,
    service_name            VARCHAR(50)   NOT NULL,
    content_id              VARCHAR(100),
    channel_id              VARCHAR(20),
    decision_point          VARCHAR(100)  NOT NULL,
    path_taken              VARCHAR(50)   NOT NULL,
    local_score             REAL,
    llm_cost_usd            REAL          DEFAULT 0,
    cost_saved_usd          REAL          DEFAULT 0,
    latency_ms              INTEGER,
    model_version           VARCHAR(50),
    metadata                JSONB         DEFAULT '{}',
    created_at              TIMESTAMPTZ   DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS model_health (
    id                      BIGSERIAL     PRIMARY KEY,
    model_name              VARCHAR(100)  NOT NULL,
    niche                   VARCHAR(100),
    training_rows           INTEGER       DEFAULT 0,
    last_trained_at         TIMESTAMPTZ,
    accuracy_metric         REAL,
    drift_detected          BOOLEAN       DEFAULT FALSE,
    drift_score             REAL,
    last_checked_at         TIMESTAMPTZ   DEFAULT NOW(),
    status                  VARCHAR(20)   DEFAULT 'untrained',
    created_at              TIMESTAMPTZ   DEFAULT NOW(),
    updated_at              TIMESTAMPTZ   DEFAULT NOW(),
    UNIQUE(model_name, niche)
);

CREATE INDEX IF NOT EXISTS idx_intel_metrics_service   ON intelligence_metrics(service_name, decision_point);
CREATE INDEX IF NOT EXISTS idx_intel_metrics_time      ON intelligence_metrics(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_model_health_name       ON model_health(model_name, niche);

-- ── pgvector Indexes (IVFFlat for ANN search) ─────────────
-- These require data to build; create with small nlist for initial use
CREATE INDEX IF NOT EXISTS idx_topic_emb_vector        ON topic_embeddings USING ivfflat (embedding vector_cosine_ops) WITH (lists = 10);
CREATE INDEX IF NOT EXISTS idx_comp_video_emb_vector   ON competitor_videos USING ivfflat (title_embedding vector_cosine_ops) WITH (lists = 10);
