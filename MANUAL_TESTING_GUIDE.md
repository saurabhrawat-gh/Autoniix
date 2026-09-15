# Autoniix Video Production Pipeline — Manual Testing Guide

**Purpose:** End-to-end manual testing of all services via Postman  
**Date:** 2026-09-14  
**Status:** Ready for Tier 1 & 2 services, Tier 3+ in progress

---

## 📋 Prerequisites

### 1. Start All Services

```bash
cd /Users/saurabhrawat/Desktop/projects/Autoniix

# Option A: Start everything (recommended for full pipeline test)
make up

# Option B: Start only infrastructure (for individual service testing)
make infra

# Verify all services are healthy
make health
```

**Expected Output:**

```
✓ Gateway
✓ Research
✓ Script
✓ Voice
✓ Assets
✓ Thumbnail
✓ Assembly
✓ Delivery
✓ Direction
✓ Streaming Hub
✓ Notification Dispatcher
```

### 2. Postman Setup

**Import Environment:**
Create a Postman environment with these variables:

```json
{
  "name": "Autoniix Local",
  "values": [
    {
      "key": "base_url",
      "value": "http://localhost:8000",
      "enabled": true
    },
    {
      "key": "gateway_url",
      "value": "http://localhost:8000",
      "enabled": true
    },
    {
      "key": "research_url",
      "value": "http://localhost:8001",
      "enabled": true
    },
    {
      "key": "script_url",
      "value": "http://localhost:8002",
      "enabled": true
    },
    {
      "key": "voice_url",
      "value": "http://localhost:8003",
      "enabled": true
    },
    {
      "key": "assets_url",
      "value": "http://localhost:8004",
      "enabled": true
    },
    {
      "key": "thumbnail_url",
      "value": "http://localhost:8005",
      "enabled": true
    },
    {
      "key": "assembly_url",
      "value": "http://localhost:8006",
      "enabled": true
    },
    {
      "key": "delivery_url",
      "value": "http://localhost:8007",
      "enabled": true
    },
    {
      "key": "direction_url",
      "value": "http://localhost:8008",
      "enabled": true
    },
    {
      "key": "streaming_hub_url",
      "value": "http://localhost:8009",
      "enabled": true
    },
    {
      "key": "auth_token",
      "value": "",
      "enabled": true
    },
    {
      "key": "channel_id",
      "value": "test_channel_001",
      "enabled": true
    },
    {
      "key": "content_id",
      "value": "",
      "enabled": true
    },
    {
      "key": "job_id",
      "value": "",
      "enabled": true
    }
  ]
}
```

### 3. Test Data

Create a test channel in the database:

```sql
INSERT INTO channels (
    channel_id,
    channel_name,
    niche,
    target_audience,
    content_mode,
    voice_id,
    created_at
) VALUES (
    'test_channel_001',
    'Test Channel',
    'technology',
    'tech enthusiasts',
    'short',
    'inworld-default',
    NOW()
) ON CONFLICT (channel_id) DO NOTHING;
```

---

## 🧪 Testing Sequence

### Phase 0: Health Checks (All Services)

Test each service's health endpoint to ensure it's running.

#### 0.1 Gateway Health

```
GET {{gateway_url}}/health
```

**Expected Response (200 OK):**

```json
{
  "status": "healthy",
  "service": "gateway",
  "version": "0.1.0",
  "timestamp": "2026-09-14T12:00:00Z"
}
```

#### 0.2 Research Health

```
GET {{research_url}}/health
```

#### 0.3 Script Health

```
GET {{script_url}}/health
```

#### 0.4 Voice Health

```
GET {{voice_url}}/health
```

#### 0.5 Assets Health

```
GET {{assets_url}}/health
```

#### 0.6 Thumbnail Health

```
GET {{thumbnail_url}}/health
```

#### 0.7 Assembly Health

```
GET {{assembly_url}}/health
```

#### 0.8 Delivery Health

```
GET {{delivery_url}}/health
```

#### 0.9 Direction Health

```
GET {{direction_url}}/health
```

#### 0.10 Streaming Hub Health

```
GET {{streaming_hub_url}}/health
```

---

### Phase 1: Authentication & Authorization

#### 1.1 Register User (First Time Only)

```
POST {{gateway_url}}/auth/register

Headers:
Content-Type: application/json

Body:
{
  "email": "test@autoniix.com",
  "password": "TestPassword123!",
  "full_name": "Test User"
}
```

**Expected Response (201 Created):**

```json
{
  "user_id": "usr_...",
  "email": "test@autoniix.com",
  "full_name": "Test User",
  "created_at": "2026-09-14T12:00:00Z"
}
```

#### 1.2 Login

```
POST {{gateway_url}}/auth/login

Headers:
Content-Type: application/json

Body:
{
  "email": "test@autoniix.com",
  "password": "TestPassword123!"
}
```

**Expected Response (200 OK):**

```json
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 3600,
  "user": {
    "user_id": "usr_...",
    "email": "test@autoniix.com",
    "full_name": "Test User"
  }
}
```

**Action:** Copy the `access_token` and set it in Postman environment variable `auth_token`

#### 1.3 Get Current User

```
GET {{gateway_url}}/auth/me

Headers:
Authorization: Bearer {{auth_token}}
```

**Expected Response (200 OK):**

```json
{
  "user_id": "usr_...",
  "email": "test@autoniix.com",
  "full_name": "Test User",
  "channels": [...]
}
```

---

### Phase 2: Research Service (T3.1 ✅)

#### 2.1 Research Topics

```
POST {{research_url}}/research

Headers:
Content-Type: application/json
Authorization: Bearer {{auth_token}}

Body:
{
  "channel_id": "{{channel_id}}",
  "content_mode": "short",
  "topic_candidates": [
    "AI trends 2026",
    "machine learning breakthroughs",
    "future of technology"
  ],
  "budget_guard": {
    "max_cost_usd": 2.50,
    "accrued_cost_usd": 0.0
  }
}
```

**Expected Response (200 OK):**

```json
{
  "status": "success",
  "research_data": {
    "selected_topic": "AI trends 2026",
    "topic_score": 8.5,
    "sources": [
      {
        "source": "youtube",
        "title": "...",
        "url": "...",
        "relevance": 0.95
      },
      {
        "source": "reddit",
        "title": "...",
        "url": "...",
        "relevance": 0.87
      }
    ],
    "trends": [...],
    "competitor_insights": [...],
    "freshness_score": 0.92,
    "saturation_score": 0.35
  },
  "cost_usd": 0.15,
  "latency_ms": 2500
}
```

**Validation:**

- ✅ Response contains `selected_topic`
- ✅ At least 3 sources returned
- ✅ Cost is within budget
- ✅ Latency < 5000ms
- ✅ Check logs for retry attempts (if any API failed)

#### 2.2 Check Similarity (Embedding Deduplication)

```
POST {{research_url}}/similarity/check

Headers:
Content-Type: application/json
Authorization: Bearer {{auth_token}}

Body:
{
  "text": "AI trends 2026",
  "channel_id": "{{channel_id}}",
  "text_type": "topic",
  "similarity_threshold": 0.35
}
```

**Expected Response (200 OK):**

```json
{
  "is_similar": true,
  "similar_topics": [
    {
      "text_content": "AI trends 2026",
      "cosine_sim": 1.0,
      "simhash": 12345,
      "hamming": 0
    }
  ],
  "max_similarity": 1.0
}
```

**Validation:**

- ✅ Duplicate topic detected (cosine_sim = 1.0)
- ✅ Embedding was reused (check database for single entry)

---

### Phase 3: Script Service (T3.2 - Pending)

#### 3.1 Generate Script

```
POST {{script_url}}/script/generate

Headers:
Content-Type: application/json
Authorization: Bearer {{auth_token}}

Body:
{
  "channel_id": "{{channel_id}}",
  "content_id": "{{content_id}}",
  "research_data": {
    "selected_topic": "AI trends 2026",
    "key_points": [
      "GPT-5 release",
      "AI regulation updates",
      "Breakthrough in AGI research"
    ]
  },
  "content_mode": "short",
  "duration_target_seconds": 60
}
```

**Expected Response (200 OK):**

```json
{
  "status": "success",
  "script": {
    "hook": "Did you know AI just changed everything in 2026?",
    "segments": [
      {
        "segment_id": "seg_001",
        "text": "GPT-5 was just released...",
        "duration_estimate_ms": 8000,
        "scene_direction": "dramatic reveal",
        "prosody_hint": "[breath] [emphasis on 'released']",
        "emphasis_words": ["GPT-5", "released"],
        "is_hero_moment": true
      },
      ...
    ],
    "cta": "Follow for more AI updates!",
    "total_duration_estimate_ms": 58000
  },
  "cost_usd": 0.05,
  "latency_ms": 3000
}
```

**Validation:**

- ✅ Hook is engaging (< 10 words)
- ✅ Segments have prosody hints
- ✅ Emphasis words identified
- ✅ Hero moments flagged
- ✅ Total duration within target (±10%)

---

### Phase 4: Voice Service (T3.3 - Pending, MAJOR)

#### 4.1 Generate Voice (with Word Alignment)

```
POST {{voice_url}}/voice/generate

Headers:
Content-Type: application/json
Authorization: Bearer {{auth_token}}

Body:
{
  "channel_id": "{{channel_id}}",
  "content_id": "{{content_id}}",
  "segments": [
    {
      "segment_id": "seg_001",
      "text": "[breath] GPT-5 was just released, and it's a game changer.",
      "emphasis_words": ["GPT-5", "released", "game changer"],
      "prosody_hint": "[breath] [emphasis on 'released']",
      "is_hero_moment": true
    }
  ],
  "voice_id": "inworld-default",
  "delivery_mode": "CREATIVE",
  "speed": 1.0
}
```

**Expected Response (200 OK):**

```json
{
  "status": "success",
  "manifest": {
    "segment_urls": [
      {
        "segment_id": "seg_001",
        "audio_url": "s3://bucket/audio/seg_001.mp3",
        "duration_ms": 7850,
        "word_alignment": [
          {
            "word": "GPT-5",
            "start_ms": 200,
            "end_ms": 650,
            "is_emphasis": true,
            "syllables": ["G", "P", "T", "five"],
            "stress_syllable_idx": 3,
            "stress_at_ms": 550
          },
          {
            "word": "was",
            "start_ms": 680,
            "end_ms": 820,
            "is_emphasis": false
          },
          ...
        ],
        "emphasis_hits": [
          {
            "word": "GPT-5",
            "at_ms": 550,
            "intensity": 0.9
          },
          {
            "word": "released",
            "at_ms": 2100,
            "intensity": 0.85
          }
        ],
        "phoneme_density": 12.5,
        "silence_ms_before": 150,
        "silence_ms_after": 200
      }
    ],
    "total_duration_ms": 7850,
    "multi_take_info": {
      "hero_takes": [
        {
          "take_id": 1,
          "score": 0.92,
          "selected": true
        },
        {
          "take_id": 2,
          "score": 0.87,
          "selected": false
        }
      ]
    }
  },
  "cost_usd": 0.25,
  "latency_ms": 5000
}
```

**Validation:**

- ✅ Word alignment present for every word
- ✅ Emphasis words have `is_emphasis: true`
- ✅ Syllable-level timing for emphasis words
- ✅ Emphasis hits extracted
- ✅ Duration measured (not estimated)
- ✅ Multi-take for hero moments
- ✅ Audio files accessible at URLs

---

### Phase 5: Assets Service (T3.4 - Pending)

#### 5.1 Select Assets (Voice-Aware)

```
POST {{assets_url}}/assets/select

Headers:
Content-Type: application/json
Authorization: Bearer {{auth_token}}

Body:
{
  "channel_id": "{{channel_id}}",
  "content_id": "{{content_id}}",
  "segments": [...],
  "voice_manifest": {
    "segment_urls": [...],
    "emphasis_hits": [
      {"word": "GPT-5", "at_ms": 550, "intensity": 0.9},
      {"word": "released", "at_ms": 2100, "intensity": 0.85}
    ]
  },
  "duration_ms": 60000
}
```

**Expected Response (200 OK):**

```json
{
  "status": "success",
  "assets": [
    {
      "asset_id": "asset_001",
      "type": "video",
      "url": "https://pexels.com/...",
      "start_ms": 0,
      "duration_ms": 8000,
      "tags": ["technology", "AI", "futuristic"]
    },
    ...
  ],
  "cut_suggestions_ms": [550, 2100, 5500, 8200],
  "cost_usd": 0.0,
  "latency_ms": 2000
}
```

**Validation:**

- ✅ Cut suggestions align with voice emphasis hits
- ✅ Assets cover full duration
- ✅ No gaps between assets

---

### Phase 6: Music Service (T3.5 - Pending)

#### 6.1 Select Music (Voice-Aware)

```
POST {{assets_url}}/music/select

Headers:
Content-Type: application/json
Authorization: Bearer {{auth_token}}

Body:
{
  "channel_id": "{{channel_id}}",
  "content_id": "{{content_id}}",
  "mood": "energetic",
  "duration_ms": 60000,
  "voice_manifest": {
    "total_duration_ms": 58000,
    "emphasis_hits": [...]
  }
}
```

**Expected Response (200 OK):**

```json
{
  "status": "success",
  "music": {
    "track_id": "music_001",
    "url": "s3://bucket/music/track_001.mp3",
    "duration_ms": 60000,
    "bpm": 128,
    "beat_map_ms": [0, 468, 937, 1406, ...],
    "hero_moments": [
      {
        "at_ms": 550,
        "type": "voice_beat_sync",
        "voice_word": "GPT-5",
        "music_beat_ms": 468
      }
    ]
  },
  "cost_usd": 0.0,
  "latency_ms": 1500
}
```

**Validation:**

- ✅ Beat map extracted
- ✅ Hero moments identified (voice + music sync)
- ✅ BPM matches voice WPM

---

### Phase 7: Direction Service (T3.7 - Pending)

#### 7.1 Generate Direction v3.1

```
POST {{direction_url}}/direction/generate

Headers:
Content-Type: application/json
Authorization: Bearer {{auth_token}}

Body:
{
  "channel_id": "{{channel_id}}",
  "content_id": "{{content_id}}",
  "script": {...},
  "voice_manifest": {...},
  "assets": {...},
  "music": {...},
  "thumbnail": {...}
}
```

**Expected Response (200 OK):**

```json
{
  "status": "success",
  "direction": {
    "version": "3.1",
    "timeline": [
      {
        "at_ms": 0,
        "camera": {
          "position": {"x": 0, "y": 0, "z": 5},
          "scale": 1.0,
          "rotation": 0
        },
        "ease": "easeInOutCubic"
      },
      {
        "at_ms": 500,
        "camera": {
          "position": {"x": 0, "y": 0, "z": 4.5},
          "scale": 1.1,
          "rotation": 0
        },
        "ease": "easeOutQuad"
      },
      ...
    ],
    "captions": [
      {
        "word": "GPT-5",
        "start_ms": 200,
        "end_ms": 650,
        "style": "emphasis",
        "chars": [
          {"ch": "G", "at_ms": 200},
          {"ch": "P", "at_ms": 290},
          {"ch": "T", "at_ms": 380},
          {"ch": "-", "at_ms": 470},
          {"ch": "5", "at_ms": 560}
        ]
      },
      ...
    ],
    "micro_beats": [
      {"at_ms": 550, "intensity": 0.9, "type": "zoom_punch"},
      {"at_ms": 2100, "intensity": 0.85, "type": "flash"},
      ...
    ],
    "audio_track": {
      "voice_url": "s3://...",
      "music_url": "s3://...",
      "ducking_envelope": [
        {"at_ms": 0, "music_volume_db": -12},
        {"at_ms": 200, "music_volume_db": -12},
        {"at_ms": 7850, "music_volume_db": 0},
        ...
      ]
    },
    "layers": [
      {
        "layer_id": "background",
        "z_index": 0,
        "parallax_factor": 1.0
      },
      {
        "layer_id": "foreground",
        "z_index": 10,
        "parallax_factor": 1.5
      }
    ]
  },
  "validation": {
    "timeline_density_ok": true,
    "max_keyframe_gap_ms": 500,
    "caption_coverage": 1.0
  },
  "cost_usd": 0.10,
  "latency_ms": 4000
}
```

**Validation:**

- ✅ Timeline keyframes every ≤500ms
- ✅ Captions have word-level timing
- ✅ Character-level reveal timing present
- ✅ Micro-beats aligned with voice emphasis
- ✅ Audio ducking envelope present
- ✅ Validation passes

---

### Phase 8: Assembly Service (T3.8 - Pending)

#### 8.1 Assemble Video

```
POST {{assembly_url}}/assembly/render

Headers:
Content-Type: application/json
Authorization: Bearer {{auth_token}}

Body:
{
  "channel_id": "{{channel_id}}",
  "content_id": "{{content_id}}",
  "direction": {...},
  "quality": "preview"
}
```

**Expected Response (202 Accepted):**

```json
{
  "status": "queued",
  "job_id": "job_render_001",
  "estimated_duration_seconds": 120
}
```

**Action:** Copy `job_id` to Postman environment variable

#### 8.2 Check Render Status

```
GET {{assembly_url}}/assembly/status/{{job_id}}

Headers:
Authorization: Bearer {{auth_token}}
```

**Expected Response (200 OK):**

```json
{
  "job_id": "job_render_001",
  "status": "rendering",
  "progress": 0.45,
  "current_phase": "compositing",
  "estimated_completion_seconds": 60
}
```

**Poll every 10 seconds until status = "completed"**

#### 8.3 Get Rendered Video

```
GET {{assembly_url}}/assembly/result/{{job_id}}

Headers:
Authorization: Bearer {{auth_token}}
```

**Expected Response (200 OK):**

```json
{
  "job_id": "job_render_001",
  "status": "completed",
  "video_url": "s3://bucket/videos/video_001.mp4",
  "thumbnail_url": "s3://bucket/thumbnails/thumb_001.jpg",
  "duration_ms": 58500,
  "resolution": "1080x1920",
  "file_size_bytes": 15728640,
  "cost_usd": 0.5,
  "render_time_seconds": 95
}
```

**Validation:**

- ✅ Video file accessible
- ✅ Duration matches script
- ✅ Resolution correct (1080x1920 for shorts)
- ✅ File size reasonable (< 50MB for 60s short)

---

### Phase 9: Delivery Service (T3.10 - Pending)

#### 9.1 Upload to YouTube

```
POST {{delivery_url}}/delivery/youtube/upload

Headers:
Content-Type: application/json
Authorization: Bearer {{auth_token}}

Body:
{
  "channel_id": "{{channel_id}}",
  "content_id": "{{content_id}}",
  "video_url": "s3://bucket/videos/video_001.mp4",
  "metadata": {
    "title": "AI Trends 2026: What You Need to Know",
    "description": "Discover the latest AI breakthroughs...",
    "tags": ["AI", "technology", "2026", "trends"],
    "category": "Science & Technology",
    "privacy": "private"
  },
  "scheduled_publish_time": null
}
```

**Expected Response (202 Accepted):**

```json
{
  "status": "uploading",
  "job_id": "job_upload_001",
  "estimated_duration_seconds": 180
}
```

#### 9.2 Check Upload Status

```
GET {{delivery_url}}/delivery/status/{{job_id}}

Headers:
Authorization: Bearer {{auth_token}}
```

**Expected Response (200 OK):**

```json
{
  "job_id": "job_upload_001",
  "status": "completed",
  "youtube_video_id": "dQw4w9WgXcQ",
  "youtube_url": "https://youtube.com/watch?v=dQw4w9WgXcQ",
  "upload_time_seconds": 145
}
```

**Validation:**

- ✅ YouTube video ID returned
- ✅ Video accessible on YouTube
- ✅ Metadata correct

---

### Phase 10: Streaming Hub (Real-Time Events)

#### 10.1 Subscribe to SSE Stream

```
GET {{streaming_hub_url}}/sse/subscribe?channel_id={{channel_id}}

Headers:
Authorization: Bearer {{auth_token}}
Accept: text/event-stream
```

**Expected Response (200 OK, streaming):**

```
event: job.research.started
data: {"content_id": "...", "timestamp": "..."}

event: job.research.completed
data: {"content_id": "...", "cost_usd": 0.15, "timestamp": "..."}

event: job.script.started
data: {"content_id": "...", "timestamp": "..."}

...
```

**Validation:**

- ✅ Events received in real-time
- ✅ Connection stays open
- ✅ Events have correct structure

#### 10.2 Subscribe to WebSocket

```
WS {{streaming_hub_url}}/ws?channel_id={{channel_id}}&token={{auth_token}}
```

**Send:**

```json
{
  "type": "subscribe",
  "channel_id": "{{channel_id}}"
}
```

**Receive:**

```json
{
  "type": "event",
  "event": {
    "id": "evt_001",
    "type": "job.voice.completed",
    "workspace_id": "{{channel_id}}",
    "ts": 1726315200000,
    "data": {
      "content_id": "...",
      "cost_usd": 0.25
    }
  }
}
```

**Validation:**

- ✅ Heartbeat pings every 30s
- ✅ Events received in real-time
- ✅ Connection resilient to network blips

---

### Phase 11: End-to-End Pipeline Test

#### 11.1 Trigger Full Pipeline

```
POST {{gateway_url}}/pipeline/trigger

Headers:
Content-Type: application/json
Authorization: Bearer {{auth_token}}

Body:
{
  "channel_id": "{{channel_id}}",
  "topic_candidates": [
    "AI trends 2026",
    "machine learning breakthroughs"
  ],
  "content_mode": "short",
  "quality": "preview",
  "auto_publish": false
}
```

**Expected Response (202 Accepted):**

```json
{
  "status": "pipeline_started",
  "content_id": "cnt_001",
  "job_id": "job_pipeline_001",
  "estimated_duration_minutes": 15
}
```

**Action:** Copy `content_id` and `job_id` to environment

#### 11.2 Monitor Pipeline Progress

```
GET {{gateway_url}}/pipeline/status/{{job_id}}

Headers:
Authorization: Bearer {{auth_token}}
```

**Expected Response (200 OK):**

```json
{
  "job_id": "job_pipeline_001",
  "content_id": "cnt_001",
  "status": "in_progress",
  "current_phase": "voice",
  "phases": {
    "research": {
      "status": "completed",
      "cost_usd": 0.15,
      "duration_seconds": 3
    },
    "script": {
      "status": "completed",
      "cost_usd": 0.05,
      "duration_seconds": 4
    },
    "voice": {
      "status": "in_progress",
      "progress": 0.6,
      "estimated_completion_seconds": 5
    },
    "assets": { "status": "pending" },
    "music": { "status": "pending" },
    "direction": { "status": "pending" },
    "assembly": { "status": "pending" },
    "delivery": { "status": "pending" }
  },
  "total_cost_usd": 0.2,
  "elapsed_seconds": 120,
  "estimated_remaining_seconds": 780
}
```

**Poll every 30 seconds until status = "completed"**

#### 11.3 Get Final Result

```
GET {{gateway_url}}/pipeline/result/{{job_id}}

Headers:
Authorization: Bearer {{auth_token}}
```

**Expected Response (200 OK):**

```json
{
  "job_id": "job_pipeline_001",
  "content_id": "cnt_001",
  "status": "completed",
  "video": {
    "video_url": "s3://bucket/videos/video_001.mp4",
    "thumbnail_url": "s3://bucket/thumbnails/thumb_001.jpg",
    "duration_ms": 58500,
    "resolution": "1080x1920"
  },
  "youtube": {
    "video_id": "dQw4w9WgXcQ",
    "url": "https://youtube.com/watch?v=dQw4w9WgXcQ",
    "status": "private"
  },
  "costs": {
    "research": 0.15,
    "script": 0.05,
    "voice": 0.25,
    "assets": 0.0,
    "music": 0.0,
    "direction": 0.1,
    "assembly": 0.5,
    "delivery": 0.05,
    "total": 1.1
  },
  "timings": {
    "research": 3,
    "script": 4,
    "voice": 8,
    "assets": 2,
    "music": 2,
    "direction": 5,
    "assembly": 95,
    "delivery": 145,
    "total": 264
  }
}
```

**Validation:**

- ✅ All phases completed successfully
- ✅ Video accessible and playable
- ✅ YouTube upload successful
- ✅ Total cost within expected range ($1-2)
- ✅ Total time < 20 minutes

---

## 📊 Success Criteria

### Service-Level Checks

For each service, verify:

- ✅ **Health endpoint** returns 200 OK
- ✅ **Response time** < 5 seconds (except assembly/delivery)
- ✅ **Error handling** graceful (returns proper error codes)
- ✅ **Retry logic** works (check logs for retry attempts)
- ✅ **Validation** rejects invalid inputs
- ✅ **Cost tracking** accurate
- ✅ **Logging** structured and informative

### Pipeline-Level Checks

- ✅ **End-to-end success** (all phases complete)
- ✅ **Data flow** correct (each phase uses previous output)
- ✅ **Event streaming** real-time updates
- ✅ **Concurrency** multiple jobs don't interfere
- ✅ **Idempotency** re-running same request doesn't duplicate
- ✅ **Error recovery** failed phase can be retried
- ✅ **Cost control** total cost within budget

### Quality Checks

- ✅ **Video quality** meets expectations
- ✅ **Audio sync** perfect (no drift)
- ✅ **Captions** word-perfect timing
- ✅ **Transitions** smooth (no jarring cuts)
- ✅ **Music** synced with voice emphasis
- ✅ **Thumbnail** eye-catching and relevant

---

## 🐛 Troubleshooting

### Common Issues

#### Services Not Starting

```bash
# Check Docker logs
docker compose logs -f <service-name>

# Restart specific service
docker compose restart <service-name>

# Rebuild if code changed
make rebuild-svc SVC=<service-name>
```

#### Database Connection Errors

```bash
# Check Postgres is running
docker compose ps postgres-app

# Check connection
psql -U autoniix -d autoniix_app -c "SELECT 1"

# Run migrations
make migrate
```

#### Redis Connection Errors

```bash
# Check Redis is running
docker compose ps redis

# Test connection
redis-cli ping
```

#### Authentication Failures

```bash
# Verify JWT secret is set
echo $JWT_SECRET

# Check token expiry
# Tokens expire after 1 hour, re-login if needed
```

#### API Rate Limits

- YouTube: 10,000 quota units/day
- News API: 100 requests/day (free tier)
- Pexels: 200 requests/hour

**Solution:** Use mock providers for testing (`make use-test`)

---

## 📝 Test Results Template

Use this template to document your test results:

```markdown
# Test Run: YYYY-MM-DD HH:MM

## Environment

- Branch: main
- Commit: abc123
- Services: All running
- Mode: Local development

## Phase 0: Health Checks

- [ ] Gateway: ✅ / ❌
- [ ] Research: ✅ / ❌
- [ ] Script: ✅ / ❌
- [ ] Voice: ✅ / ❌
- [ ] Assets: ✅ / ❌
- [ ] Thumbnail: ✅ / ❌
- [ ] Assembly: ✅ / ❌
- [ ] Delivery: ✅ / ❌
- [ ] Direction: ✅ / ❌
- [ ] Streaming Hub: ✅ / ❌

## Phase 1: Authentication

- [ ] Register: ✅ / ❌
- [ ] Login: ✅ / ❌
- [ ] Get User: ✅ / ❌

## Phase 2: Research (T3.1)

- [ ] Research Topics: ✅ / ❌
- [ ] Check Similarity: ✅ / ❌
- [ ] Retry Logic: ✅ / ❌ (check logs)
- [ ] Response Validation: ✅ / ❌

## Phase 3-10: Individual Services

[Continue for each service...]

## Phase 11: End-to-End Pipeline

- [ ] Trigger Pipeline: ✅ / ❌
- [ ] Monitor Progress: ✅ / ❌
- [ ] Get Final Result: ✅ / ❌
- [ ] Video Quality: ✅ / ❌
- [ ] Total Cost: $X.XX
- [ ] Total Time: X minutes

## Issues Found

1. [Issue description]
   - Service: [service name]
   - Severity: High / Medium / Low
   - Steps to reproduce: [...]
   - Expected: [...]
   - Actual: [...]

## Notes

[Any additional observations]
```

---

## 🚀 Next Steps After Testing

Once manual testing is complete:

1. **Document Issues** — Create tickets for any bugs found
2. **Update Tests** — Add automated tests for edge cases discovered
3. **Performance Tuning** — Optimize slow services
4. **Cost Optimization** — Review API usage and caching opportunities
5. **Production Readiness** — Deploy to staging, then production

---

**Created by:** Devin AI Agent  
**Date:** 2026-09-14  
**Status:** Ready for use (Tier 1 & 2 complete, Tier 3+ in progress)
