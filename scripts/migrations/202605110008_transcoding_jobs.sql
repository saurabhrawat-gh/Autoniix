-- Wave 3: Transcoding pipeline tables
-- media_jobs  — work queue entries for each pipeline step per asset
-- media_renditions — output artifacts produced by jobs

-- media_jobs
CREATE TABLE IF NOT EXISTS media_jobs (
    id           BIGSERIAL PRIMARY KEY,
    asset_id     BIGINT       NOT NULL REFERENCES dam_assets(id) ON DELETE CASCADE,
    kind         VARCHAR(30)  NOT NULL
                 CHECK (kind IN (
                     'probe','transcode_hls','transcode_mp4',
                     'poster','waveform','embed',
                     'transcribe','autotag','safety_scan',
                     'perceptual_hash','dedup_cluster'
                 )),
    status       VARCHAR(20)  NOT NULL DEFAULT 'pending'
                 CHECK (status IN ('pending','running','done','failed','skipped')),
    priority     SMALLINT     NOT NULL DEFAULT 5,   -- lower = higher priority
    attempts     SMALLINT     NOT NULL DEFAULT 0,
    max_attempts SMALLINT     NOT NULL DEFAULT 3,
    worker_id    VARCHAR(100),                       -- hostname that claimed the job
    error        TEXT,
    result       JSONB        NOT NULL DEFAULT '{}',
    scheduled_at TIMESTAMPTZ  NOT NULL DEFAULT now(),
    started_at   TIMESTAMPTZ,
    finished_at  TIMESTAMPTZ,
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_media_jobs_pending
    ON media_jobs (priority, scheduled_at)
    WHERE status = 'pending';
CREATE INDEX IF NOT EXISTS idx_media_jobs_asset
    ON media_jobs (asset_id, kind);
CREATE INDEX IF NOT EXISTS idx_media_jobs_status
    ON media_jobs (status, created_at DESC);

-- media_renditions
CREATE TABLE IF NOT EXISTS media_renditions (
    id              BIGSERIAL PRIMARY KEY,
    asset_id        BIGINT      NOT NULL REFERENCES dam_assets(id) ON DELETE CASCADE,
    rendition_kind  VARCHAR(30) NOT NULL
                    CHECK (rendition_kind IN (
                        'proxy_hls','proxy_mp4','poster',
                        'waveform','thumbnail_strip','transcript','subtitle_srt'
                    )),
    storage_key     VARCHAR(1000),
    codec           VARCHAR(50),
    width           INT,
    height          INT,
    bitrate_kbps    INT,
    duration_ms     INT,
    bytes           BIGINT,
    metadata        JSONB       NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (asset_id, rendition_kind)   -- one rendition per kind per asset (upsert-safe)
);

CREATE INDEX IF NOT EXISTS idx_media_renditions_asset
    ON media_renditions (asset_id, rendition_kind);
