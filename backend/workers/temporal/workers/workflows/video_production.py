"""VideoProductionWorkflow — 11-phase video production pipeline.

Ported from ``go-workflows/video_production.go`` (932 lines Go → this file).

Task queue: ``video-production-v2``. All activities execute on the same
task queue, dispatched to the existing Python activity worker.

Signals:
- ``approve_video`` (bool) — human review verdict
- ``emergency_stop`` — hard cancel (auto-rejects if pending review)
- ``pause_workflow`` — pause between phases
- ``resume_workflow`` — resume after pause
- ``receive_brain_directive`` (dict) — HALT / HOLD / continue

Queries:
- ``get_status`` — current phase, cost, approval state, pause/cancel flags
"""
from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import Any

from temporalio import workflow
from temporalio.exceptions import ApplicationError

from .types import (
    RETRY_FINISH,
    RETRY_RENDER,
    RETRY_STANDARD,
    VideoParams,
    VideoResult,
    WORKFLOW_PHASES,
    add_cost,
    should_skip,
)


def _check_brain_directive(directive: dict[str, Any] | None) -> None:
    """Raise ApplicationError when the directive demands HALT or HOLD."""
    if not directive:
        return
    action = str(directive.get("action", "")).upper()
    if action not in ("HALT", "HOLD"):
        return
    reasoning = directive.get("reasoning", "no reason provided")
    msg = f"BrainHalt({action}): {reasoning}"
    if action == "HALT":
        raise ApplicationError(msg, type="BrainHaltException", non_retryable=True)
    raise ApplicationError(msg, type="BrainHaltException")


@workflow.defn(name="VideoProductionWorkflow")
class VideoProductionWorkflow:
    """Orchestrates the 11-phase video production pipeline."""

    def __init__(self) -> None:
        # ── Mutable workflow state ─────────────────────────────────────────
        self._human_approved: bool | None = None
        self._accrued_cost: float = 0.0
        self._current_phase: str = "init"
        self._paused: bool = False
        self._cancelled: bool = False
        self._brain_directive: dict[str, Any] | None = None

    # ── Signal handlers ─────────────────────────────────────────────────────

    @workflow.signal(name="approve_video")
    def approve_video(self, approved: bool) -> None:
        self._human_approved = bool(approved)

    @workflow.signal(name="emergency_stop")
    def emergency_stop(self) -> None:
        self._human_approved = False
        self._cancelled = True

    @workflow.signal(name="pause_workflow")
    def pause_workflow(self) -> None:
        self._paused = True

    @workflow.signal(name="resume_workflow")
    def resume_workflow(self) -> None:
        self._paused = False

    @workflow.signal(name="receive_brain_directive")
    def receive_brain_directive(self, directive: dict[str, Any] | None) -> None:
        self._brain_directive = directive if directive else None

    # ── Query handler ───────────────────────────────────────────────────────

    @workflow.query(name="get_status")
    def get_status(self) -> dict[str, Any]:
        return {
            "phase": self._current_phase,
            "accrued_cost": self._accrued_cost,
            "human_approved": self._human_approved,
            "paused": self._paused,
            "cancelled": self._cancelled,
        }

    # ── Internal helpers ────────────────────────────────────────────────────

    async def _check_pause(self) -> None:
        if self._paused:
            try:
                await workflow.wait_condition(
                    lambda: not self._paused or self._cancelled,
                    timeout=timedelta(hours=24),
                )
            except TimeoutError:
                # 24h without resume — auto-cancel
                self._cancelled = True
                workflow.logger.warn("auto-cancelling workflow after 24 h pause timeout")
        if self._cancelled:
            raise ApplicationError(
                "workflow cancelled by user",
                type="WorkflowCancelled",
                non_retryable=True,
            )

    def _check_brain(self) -> None:
        _check_brain_directive(self._brain_directive)

    # ── Main run ────────────────────────────────────────────────────────────

    @workflow.run
    async def run(self, params: VideoParams) -> VideoResult:
        log = workflow.logger

        # Derived constants
        ts = workflow.now().strftime("%Y%m%d_%H%M%S")
        env = params.environment or "test"
        is_test = env != "production"
        prefix = "TEST_VID" if is_test else "VID"
        content_id = params.content_id or f"{prefix}_{params.channel_id}_{ts}"
        ch = params.channel_id
        max_cost_usd = params.max_cost_usd
        resume_from = params.resume_from

        thresholds: dict[str, float] = {
            "research_depth_score": 8.0,
            "script_structure_score": 9.0,
            "hook_retention_score": 9.0,
            "voice_quality_score": 8.0,
            "thumbnail_score": 9.0,
            "direction_score": 8.5,
            "production_score": 8.0,
            "composite_score": 8.5,
        }
        if is_test:
            thresholds = {k: 0.0 for k in thresholds}

        # Working variables
        quality_scores: dict[str, float] = {}
        research_data: dict[str, Any] = {}
        topic = params.topic_candidates[0] if params.topic_candidates else ""
        title = topic
        brand_profile: dict[str, Any] = {}
        segments: list[Any] = []
        final_title = title
        script_data: dict[str, Any] = {}
        script_voice_data: dict[str, Any] = {}
        script_assets_data: dict[str, Any] = {}
        script_direction_data: dict[str, Any] = {}
        voice_data: dict[str, Any] = {}
        voice_segments_input: list[Any] = []
        assets_result: dict[str, Any] = {}
        thumbnail_data: dict[str, Any] = {}
        music_data: dict[str, Any] = {}
        direction_v3: dict[str, Any] = {}
        video_url = ""
        youtube_id = ""
        prod_score = 7.0
        description = ""
        tags: list[Any] = []

        async def set_phase(phase: str) -> None:
            self._current_phase = phase
            try:
                await workflow.execute_activity(
                    "update_video_status",
                    content_id,
                    phase,
                    ch,
                    final_title,
                    params.content_mode,
                    start_to_close_timeout=timedelta(seconds=10),
                )
            except Exception:  # noqa: BLE001 — non-critical status writes
                pass
            try:
                await workflow.execute_activity(
                    "emit_job_event",
                    content_id,
                    ch,
                    phase,
                    "started",
                    {},
                    start_to_close_timeout=timedelta(seconds=10),
                )
            except Exception:  # noqa: BLE001
                pass

        async def complete_phase(
            phase: str, cost: float, detail: dict[str, Any] | None
        ) -> None:
            try:
                await workflow.execute_activity(
                    "emit_job_event",
                    content_id,
                    ch,
                    phase,
                    "completed",
                    detail or {},
                    cost,
                    start_to_close_timeout=timedelta(seconds=10),
                )
            except Exception:  # noqa: BLE001
                pass

        async def save_phase(phase: str, data: dict[str, Any]) -> None:
            try:
                await workflow.execute_activity(
                    "save_checkpoint_data",
                    content_id,
                    phase,
                    data,
                    start_to_close_timeout=timedelta(seconds=30),
                )
            except Exception as exc:  # noqa: BLE001
                log.warn(
                    "save_checkpoint_data failed (non-critical)",
                    extra={"phase": phase, "error": str(exc)},
                )

        async def load_phase(phase: str) -> dict[str, Any]:
            try:
                return await workflow.execute_activity(
                    "load_checkpoint_data",
                    content_id,
                    phase,
                    start_to_close_timeout=timedelta(seconds=30),
                )
            except Exception:  # noqa: BLE001
                return {}

        # ── Initial Brain directive check ──────────────────────────────────
        try:
            init_dir = await workflow.execute_activity(
                "brain_directive_check_activity",
                ch,
                content_id,
                start_to_close_timeout=timedelta(seconds=10),
                retry_policy=RETRY_STANDARD,
            )
            if init_dir:
                self._brain_directive = init_dir
        except Exception:  # noqa: BLE001
            log.warn("brain_directive_check_activity failed — proceeding without Brain input")

        self._check_brain()

        # ── Restore checkpoints when resuming ──────────────────────────────
        if resume_from:
            log.info("resuming from phase", extra={"phase": resume_from})
            for prev_phase in WORKFLOW_PHASES:
                if prev_phase == resume_from:
                    break
                saved = await load_phase(prev_phase)
                if not saved:
                    continue
                if prev_phase == "researching":
                    research_data = saved.get("research_data") or {}
                    topic = saved.get("topic", topic)
                    title = saved.get("title", title)
                    quality_scores["research_depth_score"] = float(
                        saved.get("research_score", 7.0)
                    )
                elif prev_phase == "brand_check":
                    brand_profile = saved.get("brand_profile") or {}
                elif prev_phase == "scripting":
                    script_data = saved.get("script_data") or {}
                    script_voice_data = saved.get("script_voice_data") or {}
                    script_assets_data = saved.get("script_assets_data") or {}
                    script_direction_data = saved.get("script_direction_data") or {}
                    segments = saved.get("segments") or []
                    final_title = saved.get("final_title", title)
                    quality_scores["script_structure_score"] = float(
                        saved.get("script_score", 7.0)
                    )
                    quality_scores["hook_retention_score"] = float(
                        saved.get("hook_score", 7.0)
                    )
                elif prev_phase == "generating_voice":
                    voice_data = saved.get("voice_data") or {}
                    voice_segments_input = saved.get("voice_segments_input") or []
                    quality_scores["voice_quality_score"] = float(
                        saved.get("voice_score", 7.0)
                    )
                elif prev_phase == "generating_assets":
                    assets_result = saved.get("assets_result") or {}
                    thumbnail_data = saved.get("thumbnail_data") or {}
                    music_data = saved.get("music_data") or {}
                    quality_scores["thumbnail_score"] = float(
                        saved.get("thumb_score", 7.0)
                    )
                elif prev_phase == "directing":
                    direction_v3 = saved.get("direction_v3") or {}
                    quality_scores["direction_score"] = float(
                        saved.get("dir_score", 7.0)
                    )
                elif prev_phase == "post_production":
                    dv3 = saved.get("direction_v3")
                    if dv3:
                        direction_v3 = dv3
                elif prev_phase == "rendering":
                    video_url = saved.get("video_url", "")
                    prod_score = float(saved.get("prod_score", 7.0))
                    quality_scores["production_score"] = prod_score
                elif prev_phase == "finishing":
                    video_url = saved.get("video_url", video_url)
                log.info("restored checkpoint", extra={"phase": prev_phase})

        try:
            # ── PHASE: researching ─────────────────────────────────────────
            if should_skip("researching", resume_from):
                log.info("skipping researching (already completed)")
            else:
                await set_phase("researching")
                research = await workflow.execute_activity(
                    "research_activity",
                    {
                        "channel_id": params.channel_id,
                        "content_mode": params.content_mode,
                        "topic_candidates": list(params.topic_candidates),
                        "content_id": content_id,
                        "budget_guard": {
                            "max_cost_usd": max_cost_usd,
                            "accrued_cost_usd": self._accrued_cost,
                        },
                    },
                    start_to_close_timeout=timedelta(minutes=5),
                    retry_policy=RETRY_STANDARD,
                )
                self._accrued_cost += add_cost(research)
                if self._accrued_cost > max_cost_usd:
                    raise ApplicationError(
                        f"budget exceeded: ${self._accrued_cost:.2f} > ${max_cost_usd:.2f}",
                        type="BudgetExceededError",
                        non_retryable=True,
                    )

                research_data = research.get("data") or {}
                if params.topic_candidates:
                    topic = research_data.get("selected_topic", params.topic_candidates[0])
                titles = research_data.get("title_candidates") or []
                title = titles[0] if titles and isinstance(titles[0], str) else topic
                research_score = float(research_data.get("research_depth_score", 7.0))
                quality_scores["research_depth_score"] = research_score
                if research_score < thresholds["research_depth_score"]:
                    log.warn("research score below threshold", extra={"score": research_score})
                await complete_phase(
                    "researching",
                    add_cost(research),
                    {"topic": topic, "score": research_score},
                )
                log.info("research done", extra={"topic": topic, "score": research_score})
                await save_phase(
                    "researching",
                    {
                        "research_data": research_data,
                        "topic": topic,
                        "title": title,
                        "research_score": research_score,
                    },
                )
            await self._check_pause()
            self._check_brain()

            # ── PHASE: brand_check ─────────────────────────────────────────
            if should_skip("brand_check", resume_from):
                log.info("skipping brand_check (already completed)")
            else:
                await set_phase("brand_check")
                try:
                    brand_result = await workflow.execute_activity(
                        "brand_activity",
                        {"channel_id": params.channel_id, "action": "get_or_create"},
                        start_to_close_timeout=timedelta(seconds=30),
                        retry_policy=RETRY_STANDARD,
                    )
                    brand_profile = (brand_result.get("data") or {}).get("profile") or {}
                except Exception:  # noqa: BLE001
                    log.warn("brand activity failed — non-critical, continuing")
                await complete_phase("brand_check", 0.0, None)
                await save_phase("brand_check", {"brand_profile": brand_profile})
            await self._check_pause()
            self._check_brain()

            # ── PHASE: scripting ───────────────────────────────────────────
            if should_skip("scripting", resume_from):
                log.info("skipping scripting (already completed)")
            else:
                await set_phase("scripting")
                script_result = await workflow.execute_activity(
                    "script_activity",
                    {
                        "channel_id": params.channel_id,
                        "content_mode": params.content_mode,
                        "topic": topic,
                        "title": title,
                        "research_data": research_data,
                        "content_id": content_id,
                        "budget_guard": {
                            "max_cost_usd": max_cost_usd,
                            "accrued_cost_usd": self._accrued_cost,
                        },
                    },
                    start_to_close_timeout=timedelta(minutes=8),
                    retry_policy=RETRY_STANDARD,
                )
                self._accrued_cost += add_cost(script_result)
                if self._accrued_cost > max_cost_usd:
                    raise ApplicationError(
                        f"budget exceeded: ${self._accrued_cost:.2f} > ${max_cost_usd:.2f}",
                        type="BudgetExceededError",
                        non_retryable=True,
                    )
                full_script_data = script_result.get("data") or {}
                script_base = full_script_data.get("script_base")
                script_data = script_base if script_base else full_script_data
                script_voice_data = full_script_data.get("script_voice") or {}
                script_assets_data = full_script_data.get("script_assets") or {}
                script_direction_data = full_script_data.get("script_direction") or {}
                segments = script_data.get("segments") or []
                final_title = script_data.get("title", title)
                script_score = float(script_data.get("script_structure_score", 7.0))
                quality_scores["script_structure_score"] = script_score
                quality_scores["hook_retention_score"] = float(
                    script_data.get("hook_retention_score", 7.0)
                )
                if script_score < thresholds["script_structure_score"]:
                    log.warn("script score below target — proceeding", extra={"score": script_score})
                await complete_phase(
                    "scripting", 0.0, {"segments": len(segments), "score": script_score}
                )
                log.info("script done", extra={"segments": len(segments), "score": script_score})
                await save_phase(
                    "scripting",
                    {
                        "script_data": script_data,
                        "script_voice_data": script_voice_data,
                        "script_assets_data": script_assets_data,
                        "script_direction_data": script_direction_data,
                        "segments": segments,
                        "final_title": final_title,
                        "script_score": script_score,
                        "hook_score": quality_scores["hook_retention_score"],
                    },
                )
            await self._check_pause()
            self._check_brain()

            # ── PHASE: generating_voice ────────────────────────────────────
            if should_skip("generating_voice", resume_from):
                log.info("skipping generating_voice (already completed)")
            else:
                await set_phase("generating_voice")
                voice_prosody_segs = script_voice_data.get("segments") or []
                voice_segments_input = []
                for i, s in enumerate(segments):
                    sm = s if isinstance(s, dict) else {}
                    seg_input: dict[str, Any] = {
                        "id": sm.get("id"),
                        "section": sm.get("section", "body"),
                        "narration": sm.get("narration") or sm.get("text", ""),
                        "emotion": sm.get("emotion", ""),
                        "emphasis_words": sm.get("emphasis_words") or [],
                    }
                    if i < len(voice_prosody_segs):
                        prosody = voice_prosody_segs[i]
                        if isinstance(prosody, dict):
                            seg_input["tts_params"] = prosody.get("tts_params") or {}
                            seg_input["dominant_emotion"] = prosody.get(
                                "dominant_emotion", ""
                            )
                            if not seg_input["emphasis_words"]:
                                seg_input["emphasis_words"] = (
                                    prosody.get("emphasis_words") or []
                                )
                    voice_segments_input.append(seg_input)

                voice_result = await workflow.execute_activity(
                    "voice_activity",
                    {
                        "content_id": content_id,
                        "channel_id": params.channel_id,
                        "content_mode": params.content_mode,
                        "voice_id": "",
                        "script_segments": voice_segments_input,
                    },
                    start_to_close_timeout=timedelta(minutes=10),
                    retry_policy=RETRY_STANDARD,
                )
                self._accrued_cost += add_cost(voice_result)
                if self._accrued_cost > max_cost_usd:
                    raise ApplicationError(
                        f"budget exceeded: ${self._accrued_cost:.2f} > ${max_cost_usd:.2f}",
                        type="BudgetExceededError",
                        non_retryable=True,
                    )
                voice_data = voice_result.get("data") or {}
                voice_score = float(voice_data.get("voice_quality_score", 7.0))
                quality_scores["voice_quality_score"] = voice_score
                if voice_score < thresholds["voice_quality_score"]:
                    log.warn("voice score below threshold", extra={"score": voice_score})
                await complete_phase(
                    "generating_voice",
                    0.0,
                    {"duration_s": voice_data.get("duration_s"), "score": voice_score},
                )
                log.info("voice done", extra={"score": voice_score})
                await save_phase(
                    "generating_voice",
                    {
                        "voice_data": voice_data,
                        "voice_segments_input": voice_segments_input,
                        "voice_score": voice_score,
                    },
                )
            await self._check_pause()
            self._check_brain()

            # ── PHASE: generating_assets (parallel: assets + thumbnail + music) ─
            if should_skip("generating_assets", resume_from):
                log.info("skipping generating_assets (already completed)")
            else:
                await set_phase("generating_assets")
                asset_intel_segs = script_assets_data.get("segments") or []
                assets_segments_input: list[Any] = []
                for i, s in enumerate(segments):
                    sm = s if isinstance(s, dict) else {}
                    seg_input: dict[str, Any] = {
                        "id": sm.get("id"),
                        "scene_direction": sm.get("scene_direction", ""),
                        "asset_suggestions": sm.get("asset_suggestions") or [],
                        "b_roll_keywords": sm.get("b_roll_keywords") or [],
                        "emotion": sm.get("emotion", ""),
                    }
                    if i < len(asset_intel_segs):
                        intel = asset_intel_segs[i]
                        if isinstance(intel, dict):
                            seg_input["primary_query"] = intel.get("primary_query", "")
                            seg_input["alternate_queries"] = (
                                intel.get("alternate_queries") or []
                            )
                            seg_input["shot_type"] = intel.get("shot_type", "")
                            seg_input["mood"] = intel.get("mood") or {}
                    assets_segments_input.append(seg_input)

                duration_s = float(voice_data.get("duration_s", 45.0))

                # Launch parallel activities
                assets_task = workflow.execute_activity(
                    "assets_activity",
                    {
                        "content_id": content_id,
                        "channel_id": params.channel_id,
                        "content_mode": params.content_mode,
                        "segments": assets_segments_input,
                    },
                    start_to_close_timeout=timedelta(minutes=15),
                    retry_policy=RETRY_STANDARD,
                )
                music_task = workflow.execute_activity(
                    "music_activity",
                    {
                        "content_id": content_id,
                        "channel_id": params.channel_id,
                        "mood": "",
                        "duration_s": duration_s,
                    },
                    start_to_close_timeout=timedelta(minutes=2),
                    retry_policy=RETRY_STANDARD,
                )

                thumb_score = 10.0
                music_res: dict[str, Any] | None = None
                thumb_res: dict[str, Any] | None = None
                if not is_test:
                    thumb_task = workflow.execute_activity(
                        "thumbnail_activity",
                        {
                            "content_id": content_id,
                            "channel_id": params.channel_id,
                            "title": final_title,
                            "topic": topic,
                            "niche": "",
                        },
                        start_to_close_timeout=timedelta(minutes=10),
                        retry_policy=RETRY_STANDARD,
                    )
                    # asset failure aborts; music/thumb failures are handled below
                    assets_result, music_settled, thumb_settled = await asyncio.gather(
                        assets_task, music_task, thumb_task, return_exceptions=True
                    )
                    if isinstance(assets_result, BaseException):
                        raise assets_result
                    if isinstance(music_settled, BaseException):
                        log.warn(
                            "music activity failed (non-critical)",
                            extra={"error": str(music_settled)},
                        )
                    else:
                        music_res = music_settled
                    if isinstance(thumb_settled, BaseException):
                        raise thumb_settled
                    thumb_res = thumb_settled
                else:
                    assets_result, music_settled = await asyncio.gather(
                        assets_task, music_task, return_exceptions=True
                    )
                    if isinstance(assets_result, BaseException):
                        raise assets_result
                    if isinstance(music_settled, BaseException):
                        log.warn(
                            "music activity failed (non-critical)",
                            extra={"error": str(music_settled)},
                        )
                    else:
                        music_res = music_settled

                self._accrued_cost += add_cost(assets_result)
                if self._accrued_cost > max_cost_usd:
                    raise ApplicationError(
                        f"budget exceeded: ${self._accrued_cost:.2f} > ${max_cost_usd:.2f}",
                        type="BudgetExceededError",
                        non_retryable=True,
                    )

                if music_res:
                    music_data = music_res.get("data") or {}

                if is_test:
                    thumbnail_data = {
                        "thumbnail_score": 10.0,
                        "regeneration_count": 0,
                        "selected_thumbnail": {"url": ""},
                    }
                else:
                    self._accrued_cost += add_cost(thumb_res)
                    thumbnail_data = (thumb_res or {}).get("data") or {}
                    thumb_score = float(thumbnail_data.get("thumbnail_score", 7.0))
                quality_scores["thumbnail_score"] = thumb_score
                if thumb_score < thresholds["thumbnail_score"]:
                    log.warn(
                        "thumbnail score below target — proceeding",
                        extra={"score": thumb_score},
                    )
                await complete_phase(
                    "generating_assets", 0.0, {"thumb_score": thumb_score}
                )
                log.info(
                    "assets + thumbnail + music done", extra={"thumb_score": thumb_score}
                )
                await save_phase(
                    "generating_assets",
                    {
                        "assets_result": assets_result,
                        "thumbnail_data": thumbnail_data,
                        "music_data": music_data,
                        "thumb_score": thumb_score,
                    },
                )
            await self._check_pause()
            self._check_brain()

            # ── PHASE: directing ───────────────────────────────────────────
            if should_skip("directing", resume_from):
                log.info("skipping directing (already completed)")
            else:
                await set_phase("directing")
                asset_manifest = (assets_result.get("data") or {}).get("manifest") or []
                dir_result = await workflow.execute_activity(
                    "direction_activity",
                    {
                        "content_id": content_id,
                        "channel_id": params.channel_id,
                        "content_mode": params.content_mode,
                        "title": final_title,
                        "script_segments": segments,
                        "voice_manifest": voice_data,
                        "asset_manifest": asset_manifest,
                        "thumbnail_result": thumbnail_data,
                        "music_data": music_data,
                        "script_direction_hint": script_direction_data,
                    },
                    start_to_close_timeout=timedelta(minutes=3),
                    retry_policy=RETRY_STANDARD,
                )
                self._accrued_cost += add_cost(dir_result)
                direction_data = dir_result.get("data") or {}
                direction_v3 = direction_data.get("direction_v3") or {}
                dir_score = float(direction_data.get("direction_score", 7.0))
                quality_scores["direction_score"] = dir_score
                if dir_score < thresholds["direction_score"]:
                    log.warn("direction score below threshold", extra={"score": dir_score})
                await complete_phase("directing", 0.0, {"score": dir_score})
                log.info("direction done", extra={"score": dir_score})
                await save_phase(
                    "directing", {"direction_v3": direction_v3, "dir_score": dir_score}
                )
            await self._check_pause()
            self._check_brain()

            # ── PHASE: post_production (editor optimization) ───────────────
            if should_skip("post_production", resume_from):
                log.info("skipping post_production (already completed)")
            else:
                await set_phase("post_production")
                try:
                    editor_result = await workflow.execute_activity(
                        "editor_activity",
                        {
                            "content_id": content_id,
                            "channel_id": params.channel_id,
                            "direction_v3": direction_v3,
                            "voice_manifest": voice_data,
                            "brand_profile": brand_profile,
                        },
                        start_to_close_timeout=timedelta(minutes=3),
                        retry_policy=RETRY_STANDARD,
                    )
                    editor_data = editor_result.get("data") or {}
                    opt = editor_data.get("optimized_direction")
                    if opt:
                        direction_v3 = opt
                        log.info(
                            "editor applied",
                            extra={"pacing_optimized": editor_data.get("pacing_optimized")},
                        )
                    else:
                        log.info("editor returned no optimized direction — using original")
                except Exception as exc:  # noqa: BLE001
                    log.warn(
                        "editor activity failed — using original direction",
                        extra={"error": str(exc)},
                    )
                await complete_phase("post_production", 0.0, None)
                await save_phase("post_production", {"direction_v3": direction_v3})
            await self._check_pause()
            self._check_brain()

            # ── PHASE: rendering (1-hour heartbeat activity) ───────────────
            if should_skip("rendering", resume_from):
                log.info("skipping rendering (already completed)")
            else:
                await set_phase("rendering")
                assembly_res = await workflow.execute_activity(
                    "assembly_activity",
                    {
                        "content_id": content_id,
                        "channel_id": params.channel_id,
                        "content_mode": params.content_mode,
                        "title": final_title,
                        "direction_v3": direction_v3,
                        "thumbnail_url": (thumbnail_data.get("selected_thumbnail") or {}).get(
                            "url", ""
                        ),
                        "environment": env,
                    },
                    start_to_close_timeout=timedelta(hours=1),
                    heartbeat_timeout=timedelta(minutes=2),
                    retry_policy=RETRY_RENDER,
                )
                assembly_data = assembly_res.get("data") or {}
                video_url = assembly_data.get("video_url", "")
                prod_score = float(assembly_data.get("production_score", 7.0))
                quality_scores["production_score"] = prod_score
                await complete_phase(
                    "rendering", 0.0, {"video_url": video_url, "score": prod_score}
                )
                log.info("render done", extra={"video_url": video_url, "score": prod_score})
                await save_phase(
                    "rendering",
                    {
                        "assembly_data": assembly_data,
                        "video_url": video_url,
                        "prod_score": prod_score,
                    },
                )
            await self._check_pause()
            self._check_brain()

            # ── PHASE: finishing ───────────────────────────────────────────
            if should_skip("finishing", resume_from):
                log.info("skipping finishing (already completed)")
            elif video_url:
                await set_phase("finishing")
                fin_res = await workflow.execute_activity(
                    "finishing_activity",
                    {
                        "content_id": content_id,
                        "channel_id": params.channel_id,
                        "video_url": video_url,
                    },
                    start_to_close_timeout=timedelta(minutes=10),
                    heartbeat_timeout=timedelta(minutes=3),
                    retry_policy=RETRY_FINISH,
                )
                fin_data = fin_res.get("data") or {}
                fin_url = fin_data.get("finished_url", "")
                if fin_url and not fin_data.get("skipped"):
                    video_url = fin_url
                    log.info(
                        "finishing applied",
                        extra={
                            "video_url": video_url,
                            "preset": fin_data.get("preset_used"),
                        },
                    )
                else:
                    log.info("finishing skipped — delivering raw render")
                await complete_phase(
                    "finishing",
                    0.0,
                    {"skipped": fin_data.get("skipped"), "preset": fin_data.get("preset_used")},
                )
                await save_phase(
                    "finishing", {"video_url": video_url, "finishing": fin_data}
                )
            else:
                log.info("finishing skipped — no rendered video_url")

            # ── Composite quality score ────────────────────────────────────
            composite_score = 0.0
            if quality_scores:
                composite_score = round(
                    sum(quality_scores.values()) / len(quality_scores), 1
                )
            quality_scores["composite_score"] = composite_score
            needs_human_review = (
                composite_score < thresholds["composite_score"]
                or prod_score < thresholds["production_score"]
                or params.human_review_required
            )
            log.info(
                "quality composite",
                extra={"score": composite_score, "needs_review": needs_human_review},
            )

            if needs_human_review:
                await set_phase("pending_review")
                failed_gates = [
                    k for k, v in quality_scores.items()
                    if k in thresholds and v < thresholds[k]
                ]
                try:
                    await workflow.execute_activity(
                        "send_notification",
                        {
                            "type": "human_review_required",
                            "content_id": content_id,
                            "channel_id": params.channel_id,
                            "topic": topic,
                            "composite_score": composite_score,
                            "quality_scores": quality_scores,
                            "failed_gates": failed_gates,
                        },
                        start_to_close_timeout=timedelta(seconds=30),
                    )
                except Exception:  # noqa: BLE001
                    pass

                try:
                    await workflow.wait_condition(
                        lambda: self._human_approved is not None,
                        timeout=timedelta(hours=24),
                    )
                except TimeoutError:
                    # 24h without a verdict — auto-approve (matches Go behavior)
                    self._human_approved = True

                if not self._human_approved:
                    await set_phase("rejected")
                    return VideoResult(
                        status="rejected",
                        content_id=content_id,
                        cost=self._accrued_cost,
                    )

            await self._check_pause()
            self._check_brain()

            # ── Packaging metadata ─────────────────────────────────────────
            packaging = script_data.get("packaging") or {}
            description = packaging.get("description") or script_data.get("description", "")
            tags = packaging.get("tags") or script_data.get("tags") or []

            # ── PHASE: delivering ──────────────────────────────────────────
            if should_skip("delivering", resume_from):
                log.info("skipping delivering (already completed)")
            else:
                await set_phase("delivering")
                if is_test:
                    youtube_id = "TEST_SKIP"
                    log.info("test mode — skipping YouTube upload")
                    try:
                        await workflow.execute_activity(
                            "compute_metadata_activity",
                            {
                                "content_id": content_id,
                                "channel_id": params.channel_id,
                                "content_mode": params.content_mode,
                                "title": final_title,
                                "description": description,
                                "tags": list(tags),
                                "niche": "",
                                "quality_scores": quality_scores,
                                "is_short": params.content_mode == "short",
                            },
                            start_to_close_timeout=timedelta(minutes=2),
                            retry_policy=RETRY_STANDARD,
                        )
                    except Exception:  # noqa: BLE001
                        pass
                    await complete_phase(
                        "delivering",
                        0.0,
                        {"youtube_id": youtube_id, "skipped": True, "reason": "test_mode"},
                    )
                else:
                    deliv_result = await workflow.execute_activity(
                        "delivery_activity",
                        {
                            "content_id": content_id,
                            "channel_id": params.channel_id,
                            "content_mode": params.content_mode,
                            "title": final_title,
                            "description": description,
                            "tags": list(tags),
                            "video_url": video_url,
                            "thumbnail_url": (
                                thumbnail_data.get("selected_thumbnail") or {}
                            ).get("url", ""),
                            "privacy_status": "private",
                            "is_short": params.content_mode == "short",
                            "quality_scores": quality_scores,
                            "human_review_required": False,
                        },
                        start_to_close_timeout=timedelta(minutes=10),
                        retry_policy=RETRY_STANDARD,
                    )
                    youtube_id = (deliv_result.get("data") or {}).get("youtube_video_id", "")
                    await complete_phase("delivering", 0.0, {"youtube_id": youtube_id})
                    log.info("delivered", extra={"youtube_id": youtube_id})

            # ── PHASE: analytics ───────────────────────────────────────────
            if should_skip("analytics", resume_from):
                log.info("skipping analytics (already completed)")
            elif youtube_id and youtube_id != "TEST_SKIP":
                await set_phase("analytics")
                try:
                    await workflow.execute_activity(
                        "analytics_activity",
                        {
                            "channel_id": params.channel_id,
                            "youtube_video_ids": [youtube_id],
                        },
                        start_to_close_timeout=timedelta(seconds=120),
                    )
                except Exception as exc:  # noqa: BLE001
                    log.warn(
                        "analytics activity failed — non-critical",
                        extra={"error": str(exc)},
                    )
                await complete_phase("analytics", 0.0, None)
            else:
                log.info("analytics phase skipped — no real YouTube upload")

            # ── Brand consistency (best-effort) ────────────────────────────
            if brand_profile:
                try:
                    await workflow.execute_activity(
                        "brand_activity",
                        {
                            "action": "consistency",
                            "channel_id": params.channel_id,
                            "content_id": content_id,
                            "title": final_title,
                            "description": description,
                            "tags": list(tags),
                            "quality_scores": quality_scores,
                        },
                        start_to_close_timeout=timedelta(seconds=30),
                    )
                except Exception:  # noqa: BLE001
                    pass

            # ── Final status ───────────────────────────────────────────────
            final_status = "test_delivered" if is_test else "delivered"
            await set_phase(final_status)
            await complete_phase(
                final_status,
                self._accrued_cost,
                {
                    "youtube_id": youtube_id,
                    "composite_score": composite_score,
                    "environment": env,
                },
            )
            return VideoResult(
                status=final_status,
                content_id=content_id,
                youtube_video_id=youtube_id,
                cost=self._accrued_cost,
            )
        finally:
            # Always release channel lock
            try:
                await workflow.execute_activity(
                    "release_channel_lock",
                    params.channel_id,
                    start_to_close_timeout=timedelta(seconds=10),
                )
            except Exception:  # noqa: BLE001
                pass
