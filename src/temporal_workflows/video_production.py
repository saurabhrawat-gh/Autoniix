from __future__ import annotations

import asyncio
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ApplicationError

with workflow.unsafe.imports_passed_through():
    from src.schemas.common import VideoParams, VideoResult

_BRAIN_HALTING_ACTIONS: frozenset[str] = frozenset({"HALT", "HOLD"})

RETRY_STANDARD = RetryPolicy(
    maximum_attempts=3,
    initial_interval=timedelta(seconds=10),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(seconds=60),
    non_retryable_error_types=["BudgetExceededError", "ValidationError"],
)

RETRY_RENDER = RetryPolicy(
    maximum_attempts=2,
    initial_interval=timedelta(seconds=30),
    maximum_interval=timedelta(minutes=5),
)

RETRY_FINISH = RetryPolicy(
    maximum_attempts=3,
    initial_interval=timedelta(seconds=30),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(minutes=5),
)


WORKFLOW_PHASES = [
    "researching",
    "brand_check",
    "scripting",
    "generating_voice",
    "generating_assets",
    "directing",
    "post_production",
    "rendering",
    "finishing",
    "delivering",
    "analytics",
]


def _add_cost(budget: dict, result: dict) -> float:
    cost = result.get("cost", {}).get("cost_usd", 0)
    budget["accrued_cost_usd"] = budget.get("accrued_cost_usd", 0) + cost
    return cost


def _should_skip(phase: str, resume_from: str | None) -> bool:
    """Return True if this phase should be skipped because it was completed before the checkpoint."""
    if not resume_from:
        return False
    try:
        return WORKFLOW_PHASES.index(phase) < WORKFLOW_PHASES.index(resume_from)
    except ValueError:
        return False


@workflow.defn
class VideoProductionWorkflow:

    def __init__(self) -> None:
        self._human_approved: bool | None = None
        self._accrued_cost: float = 0.0
        self._current_phase: str = "init"
        self._paused: bool = False
        self._cancelled: bool = False
        self._channel_id: str = ""
        self._title: str = ""
        self._content_mode: str = ""
        self._brain_directive: dict | None = None


    @workflow.signal
    async def approve_video(self, approved: bool) -> None:
        self._human_approved = approved

    @workflow.signal
    async def emergency_stop(self) -> None:
        self._human_approved = False
        self._cancelled = True

    @workflow.signal
    async def pause_workflow(self) -> None:
        self._paused = True

    @workflow.signal
    async def resume_workflow(self) -> None:
        self._paused = False

    @workflow.signal
    async def receive_brain_directive(self, directive: dict) -> None:
        """Mid-flight Brain interruption (AE-511 / P0).

        The directive shape matches what `brain_directive_check_activity`
        returns. The workflow consumes it at the next phase boundary via
        :py:meth:`_check_brain_directive`; signals must be O(1) so this
        method only stores the value.

        Sending an empty dict (or one without a halting action) is a no-op
        — useful for clearing a stale directive without restarting.
        """
        self._brain_directive = directive or None


    @workflow.query
    def get_status(self) -> dict:
        return {
            "phase": self._current_phase,
            "accrued_cost": self._accrued_cost,
            "human_approved": self._human_approved,
            "paused": self._paused,
            "cancelled": self._cancelled,
        }


    async def _set_phase(self, content_id: str, phase: str, channel_id: str = "") -> None:
        self._current_phase = phase
        if channel_id:
            self._channel_id = channel_id
        await workflow.execute_activity(
            "update_video_status",
            args=[content_id, phase, self._channel_id, self._title, self._content_mode],
            start_to_close_timeout=timedelta(seconds=10),
        )
        await workflow.execute_activity(
            "emit_job_event",
            args=[content_id, channel_id, phase, "started", {}],
            start_to_close_timeout=timedelta(seconds=10),
        )

    async def _complete_phase(self, content_id: str, channel_id: str, phase: str,
                               cost: float = 0, detail: dict | None = None) -> None:
        await workflow.execute_activity(
            "emit_job_event",
            args=[content_id, channel_id, phase, "completed",
                  detail or {}, cost],
            start_to_close_timeout=timedelta(seconds=10),
        )

    async def _fail_phase(self, content_id: str, channel_id: str, phase: str,
                           error: str = "") -> None:
        await workflow.execute_activity(
            "emit_job_event",
            args=[content_id, channel_id, phase, "failed",
                  {"error": error}],
            start_to_close_timeout=timedelta(seconds=10),
        )

    async def _check_pause(self) -> None:
        """Block if paused; raise if cancelled. Auto-cancel after 24h if still paused."""
        if self._paused:
            try:
                await workflow.wait_condition(
                    lambda: not self._paused or self._cancelled,
                    timeout=timedelta(hours=24),
                )
            except asyncio.TimeoutError:
                self._cancelled = True
                workflow.logger.warning("Auto-cancelling workflow after 24h pause timeout")
        if self._cancelled:
            raise RuntimeError("Workflow cancelled by user")

    def _check_brain_directive(self) -> None:
        """Halt the workflow if Brain has signalled a HALT or HOLD (AE-511 / P0).

        Consumes the in-memory directive populated by
        :py:meth:`receive_brain_directive`. Does NOT touch the DB on every
        phase boundary — the activity-based check happens once at the very
        start of `run()`, and signals carry mid-flight changes from there.

        * Non-halting directives (ADVISE / NUDGE / RESUME / empty) → no-op.
        * HALT → :class:`ApplicationError` with ``non_retryable=True`` so the
          workflow fails permanently (Brain has decided this video must not ship).
        * HOLD → :class:`ApplicationError` with ``non_retryable=False`` so a
          future retry can resume once the directive is resolved.
        """
        directive = self._brain_directive
        if not directive:
            return
        action = str(directive.get("action", "")).upper()
        if action not in _BRAIN_HALTING_ACTIONS:
            return
        reasoning = directive.get("reasoning") or "no reason provided"
        decision_id = directive.get("decision_id")
        workflow.logger.warning(
            f"BrainHalt at phase={self._current_phase} action={action} "
            f"decision_id={decision_id} reasoning={reasoning!r}"
        )
        raise ApplicationError(
            f"BrainHalt({action}): {reasoning}",
            type="BrainHaltException",
            non_retryable=(action == "HALT"),
        )

    def _check_budget(self, budget: dict) -> None:
        if budget["accrued_cost_usd"] > budget["max_cost_usd"]:
            raise RuntimeError(
                f"Budget exceeded: ${budget['accrued_cost_usd']:.2f} > ${budget['max_cost_usd']:.2f}"
            )

    async def _save_phase_data(self, content_id: str, phase: str, data: dict) -> None:
        """Persist phase output data for resume-from-checkpoint."""
        try:
            await workflow.execute_activity(
                "save_checkpoint_data",
                args=[content_id, phase, data],
                start_to_close_timeout=timedelta(seconds=30),
            )
        except Exception:
            workflow.logger.warning(f"Failed to save checkpoint data for {phase} — non-critical")

    async def _load_phase_data(self, content_id: str, phase: str) -> dict:
        """Load previously saved phase output data."""
        try:
            return await workflow.execute_activity(
                "load_checkpoint_data",
                args=[content_id, phase],
                start_to_close_timeout=timedelta(seconds=30),
            )
        except Exception:
            workflow.logger.warning(f"Failed to load checkpoint data for {phase}")
            return {}


    @workflow.run
    async def run(self, params: VideoParams) -> VideoResult:
        ts = workflow.now().strftime("%Y%m%d_%H%M%S")
        env = getattr(params, "environment", "test")
        is_test_mode = env != "production"
        prefix = "TEST_VID" if is_test_mode else "VID"
        content_id = getattr(params, "content_id", None) or f"{prefix}_{params.channel_id}_{ts}"
        budget = {"max_cost_usd": params.max_cost_usd, "accrued_cost_usd": 0}
        quality_scores = {}

        if is_test_mode:
            THRESHOLDS = {
                "research_depth_score": 0.0,
                "script_structure_score": 0.0,
                "hook_retention_score": 0.0,
                "voice_quality_score": 0.0,
                "thumbnail_score": 0.0,
                "direction_score": 0.0,
                "production_score": 0.0,
                "composite_score": 0.0,
            }
        else:
            THRESHOLDS = {
                "research_depth_score": 8.0,
                "script_structure_score": 9.0,
                "hook_retention_score": 9.0,
                "voice_quality_score": 8.0,
                "thumbnail_score": 9.0,
                "direction_score": 8.5,
                "production_score": 8.0,
                "composite_score": 8.5,
            }

        try:
            ch = params.channel_id
            self._channel_id = ch
            self._content_mode = params.content_mode
            resume_from = getattr(params, "resume_from", None)

            try:
                initial_directive = await workflow.execute_activity(
                    "brain_directive_check_activity",
                    args=[ch, content_id],
                    start_to_close_timeout=timedelta(seconds=10),
                    retry_policy=RetryPolicy(maximum_attempts=2),
                )
            except Exception:
                workflow.logger.warning(
                    "brain_directive_check_activity_failed — proceeding without Brain input"
                )
                initial_directive = {}
            if initial_directive:
                self._brain_directive = initial_directive
            self._check_brain_directive()

            research_data: dict = {}
            topic: str = params.topic_candidates[0] if params.topic_candidates else "Unknown"
            title: str = topic
            brand_profile: dict = {}
            segments: list = []
            final_title: str = title
            script_data: dict = {}
            script_voice_data: dict = {}
            script_assets_data: dict = {}
            script_direction_data: dict = {}
            voice_data: dict = {}
            voice_segments_input: list = []
            assets_result: dict = {}
            thumbnail_data: dict = {}
            music_data: dict = {}
            direction_data: dict = {}
            direction_v3: dict = {}
            assembly_data: dict = {}
            video_url: str = ""
            youtube_id: str = ""
            prod_score: float = 7.0
            composite_score: float = 0.0

            if resume_from:
                workflow.logger.info(f"Resuming from phase: {resume_from}")
                for prev_phase in WORKFLOW_PHASES:
                    if prev_phase == resume_from:
                        break
                    saved = await self._load_phase_data(content_id, prev_phase)
                    if not saved:
                        continue
                    if prev_phase == "researching":
                        research_data = saved.get("research_data", {})
                        topic = saved.get("topic", topic)
                        title = saved.get("title", title)
                        self._title = title
                        quality_scores["research_depth_score"] = saved.get("research_score", 7.0)
                    elif prev_phase == "brand_check":
                        brand_profile = saved.get("brand_profile", {})
                    elif prev_phase == "scripting":
                        script_data = saved.get("script_data", {})
                        script_voice_data = saved.get("script_voice_data", {})
                        script_assets_data = saved.get("script_assets_data", {})
                        script_direction_data = saved.get("script_direction_data", {})
                        segments = saved.get("segments", [])
                        final_title = saved.get("final_title", title)
                        self._title = final_title
                        quality_scores["script_structure_score"] = saved.get("script_score", 7.0)
                        quality_scores["hook_retention_score"] = saved.get("hook_score", 7.0)
                    elif prev_phase == "generating_voice":
                        voice_data = saved.get("voice_data", {})
                        voice_segments_input = saved.get("voice_segments_input", [])
                        quality_scores["voice_quality_score"] = saved.get("voice_score", 7.0)
                    elif prev_phase == "generating_assets":
                        assets_result = saved.get("assets_result", {})
                        thumbnail_data = saved.get("thumbnail_data", {})
                        music_data = saved.get("music_data", {})
                        quality_scores["thumbnail_score"] = saved.get("thumb_score", 7.0)
                    elif prev_phase == "directing":
                        direction_data = saved.get("direction_data", {})
                        direction_v3 = saved.get("direction_v3", {})
                        quality_scores["direction_score"] = saved.get("dir_score", 7.0)
                    elif prev_phase == "post_production":
                        direction_v3 = saved.get("direction_v3", direction_v3)
                    elif prev_phase == "rendering":
                        assembly_data = saved.get("assembly_data", {})
                        video_url = saved.get("video_url", "")
                        quality_scores["production_score"] = saved.get("prod_score", 7.0)
                    elif prev_phase == "finishing":
                        video_url = saved.get("video_url", video_url)
                    workflow.logger.info(f"Restored checkpoint: {prev_phase}")

            if _should_skip("researching", resume_from):
                workflow.logger.info("Skipping researching (already completed)")
            else:
                await self._set_phase(content_id, "researching", ch)

                research = await workflow.execute_activity(
                    "research_activity",
                    args=[{
                        "channel_id": params.channel_id,
                        "content_mode": params.content_mode,
                        "topic_candidates": params.topic_candidates,
                        "content_id": content_id,
                        "budget_guard": budget,
                    }],
                    start_to_close_timeout=timedelta(minutes=5),
                    retry_policy=RETRY_STANDARD,
                )
                self._accrued_cost += _add_cost(budget, research)
                self._check_budget(budget)

                research_data = research.get("data", {})
                topic = research_data.get("selected_topic", params.topic_candidates[0] if params.topic_candidates else "Unknown")
                titles = research_data.get("title_candidates", [])
                title = titles[0] if titles else topic
                self._title = title
                research_score = research_data.get("research_depth_score", 7.0)
                quality_scores["research_depth_score"] = research_score

                if research_score < THRESHOLDS["research_depth_score"]:
                    workflow.logger.warning(
                        f"Research score {research_score} below threshold {THRESHOLDS['research_depth_score']} — proceeding with warning")

                await self._complete_phase(content_id, ch, "researching",
                                           cost=_add_cost({"accrued_cost_usd": 0}, research),
                                           detail={"topic": topic, "score": research_score})
                workflow.logger.info(f"Research done: {topic} (score: {research_score})")

                await self._save_phase_data(content_id, "researching", {
                    "research_data": research_data,
                    "topic": topic,
                    "title": title,
                    "research_score": research_score,
                })

            await self._check_pause()
            self._check_brain_directive()

            if _should_skip("brand_check", resume_from):
                workflow.logger.info("Skipping brand_check (already completed)")
            else:
                await self._set_phase(content_id, "brand_check", ch)

                brand_profile = {}
                try:
                    brand_result = await workflow.execute_activity(
                        "brand_activity",
                        args=[{
                            "channel_id": params.channel_id,
                            "action": "get_or_create",
                        }],
                        start_to_close_timeout=timedelta(seconds=30),
                        retry_policy=RETRY_STANDARD,
                    )
                    brand_profile = brand_result.get("data", {}).get("profile", {})
                    workflow.logger.info(
                        f"Brand profile loaded: consistency_baseline={brand_profile.get('consistency_baseline', 'N/A')}")
                except Exception:
                    workflow.logger.warning("Brand activity failed — non-critical, continuing")
                await self._complete_phase(content_id, ch, "brand_check")

                await self._save_phase_data(content_id, "brand_check", {
                    "brand_profile": brand_profile,
                })

            await self._check_pause()
            self._check_brain_directive()

            if _should_skip("scripting", resume_from):
                workflow.logger.info("Skipping scripting (already completed)")
            else:
                await self._set_phase(content_id, "scripting", ch)

                script_result = await workflow.execute_activity(
                    "script_activity",
                    args=[{
                        "channel_id": params.channel_id,
                        "content_mode": params.content_mode,
                        "topic": topic,
                        "title": title,
                        "research_data": research_data,
                        "budget_guard": budget,
                        "content_id": content_id,
                    }],
                    start_to_close_timeout=timedelta(minutes=8),
                    retry_policy=RETRY_STANDARD,
                )
                self._accrued_cost += _add_cost(budget, script_result)
                self._check_budget(budget)

                full_script_data = script_result.get("data", {})
                script_data = full_script_data.get("script_base", full_script_data)
                script_voice_data = full_script_data.get("script_voice", {})
                script_assets_data = full_script_data.get("script_assets", {})
                script_direction_data = full_script_data.get("script_direction", {})
                intelligence_scores = full_script_data.get("intelligence_scores", {})

                segments = script_data.get("segments", [])
                final_title = script_data.get("title", title)
                self._title = final_title
                script_score = script_data.get("script_structure_score", 7.0)
                quality_scores["script_structure_score"] = script_score
                quality_scores["hook_retention_score"] = script_data.get("hook_retention_score", 7.0)

                if script_score < THRESHOLDS["script_structure_score"]:
                    workflow.logger.warning(
                        f"Script score {script_score} below target {THRESHOLDS['script_structure_score']} "
                        f"after rewrites — proceeding (rewrite loop already exhausted)")

                await self._complete_phase(content_id, ch, "scripting",
                                           detail={"segments": len(segments), "score": script_score})
                workflow.logger.info(
                    f"Script done: {len(segments)} segments, score: {script_score}, "
                    f"rewrites: {script_data.get('rewrite_count', 0)}, "
                    f"intelligence: {intelligence_scores}")

                await self._save_phase_data(content_id, "scripting", {
                    "script_data": script_data,
                    "script_voice_data": script_voice_data,
                    "script_assets_data": script_assets_data,
                    "script_direction_data": script_direction_data,
                    "segments": segments,
                    "final_title": final_title,
                    "script_score": script_score,
                    "hook_score": quality_scores.get("hook_retention_score", 7.0),
                })

            await self._check_pause()
            self._check_brain_directive()

            if _should_skip("generating_voice", resume_from):
                workflow.logger.info("Skipping generating_voice (already completed)")
            else:
                await self._set_phase(content_id, "generating_voice", ch)

                voice_prosody_segs = script_voice_data.get("segments", []) if isinstance(script_voice_data, dict) else []
                voice_segments_input = []
                for i, s in enumerate(segments):
                    seg_input = {
                        "id": s.get("id"),
                        "section": s.get("section", "body"),
                        "narration": s.get("narration", "") or s.get("text", ""),
                        "emotion": s.get("emotion", ""),
                        "emphasis_words": s.get("emphasis_words", []),
                    }
                    if i < len(voice_prosody_segs):
                        prosody = voice_prosody_segs[i]
                        seg_input["tts_params"] = prosody.get("tts_params", {})
                        seg_input["dominant_emotion"] = prosody.get("dominant_emotion", "")
                        if not seg_input["emphasis_words"] and prosody.get("emphasis_words"):
                            seg_input["emphasis_words"] = prosody["emphasis_words"]
                    voice_segments_input.append(seg_input)

                voice_result = await workflow.execute_activity(
                    "voice_activity",
                    args=[{
                        "content_id": content_id,
                        "channel_id": params.channel_id,
                        "content_mode": params.content_mode,
                        "voice_id": "",
                        "script_segments": voice_segments_input,
                    }],
                    start_to_close_timeout=timedelta(minutes=10),
                    retry_policy=RETRY_STANDARD,
                )
                self._accrued_cost += _add_cost(budget, voice_result)
                self._check_budget(budget)

                voice_data = voice_result.get("data", {})
                voice_score = voice_data.get("voice_quality_score", 7.0)
                quality_scores["voice_quality_score"] = voice_score

                if voice_score < THRESHOLDS["voice_quality_score"]:
                    workflow.logger.warning(
                        f"Voice score {voice_score} below threshold {THRESHOLDS['voice_quality_score']}")

                await self._complete_phase(content_id, ch, "generating_voice",
                                           detail={"duration_s": voice_data.get("duration_s", 0), "score": voice_score})
                workflow.logger.info(f"Voice done: {voice_data.get('duration_s', 0)}s (score: {voice_score})")

                await self._save_phase_data(content_id, "generating_voice", {
                    "voice_data": voice_data,
                    "voice_segments_input": voice_segments_input,
                    "voice_score": voice_score,
                })

            await self._check_pause()
            self._check_brain_directive()

            if _should_skip("generating_assets", resume_from):
                workflow.logger.info("Skipping generating_assets (already completed)")
            else:
                await self._set_phase(content_id, "generating_assets", ch)

                asset_intel_segs = script_assets_data.get("segments", []) if isinstance(script_assets_data, dict) else []
                assets_segments_input = []
                for i, s in enumerate(segments):
                    seg_input = {
                        "id": s.get("id"),
                        "scene_direction": s.get("scene_direction", ""),
                        "asset_suggestions": s.get("asset_suggestions", []),
                        "b_roll_keywords": s.get("b_roll_keywords", []),
                        "emotion": s.get("emotion", ""),
                    }
                    if i < len(asset_intel_segs):
                        intel = asset_intel_segs[i]
                        seg_input["primary_query"] = intel.get("primary_query", "")
                        seg_input["alternate_queries"] = intel.get("alternate_queries", [])
                        seg_input["shot_type"] = intel.get("shot_type", "")
                        seg_input["mood"] = intel.get("mood", {})
                    assets_segments_input.append(seg_input)

                assets_future = workflow.execute_activity(
                    "assets_activity",
                    args=[{
                        "content_id": content_id,
                        "channel_id": params.channel_id,
                        "content_mode": params.content_mode,
                        "segments": assets_segments_input,
                    }],
                    start_to_close_timeout=timedelta(minutes=15),
                    retry_policy=RETRY_STANDARD,
                )

                if is_test_mode:
                    music_future = workflow.execute_activity(
                        "music_activity",
                        args=[{
                            "content_id": content_id,
                            "channel_id": params.channel_id,
                            "mood": "",
                            "duration_s": voice_data.get("duration_s", 45.0),
                        }],
                        start_to_close_timeout=timedelta(minutes=2),
                        retry_policy=RETRY_STANDARD,
                    )

                    assets_result, music_result = await asyncio.gather(
                        assets_future, music_future)
                    self._accrued_cost += _add_cost(budget, assets_result)
                    self._check_budget(budget)

                    thumbnail_result = {"data": {
                        "thumbnail_score": 10.0,
                        "regeneration_count": 0,
                        "selected_thumbnail": {"url": ""},
                    }, "cost": {"cost_usd": 0.0}}
                    thumbnail_data = thumbnail_result.get("data", {})
                    thumb_score = thumbnail_data.get("thumbnail_score", 7.0)
                    quality_scores["thumbnail_score"] = thumb_score
                    music_data = music_result.get("data", {})
                else:
                    thumbnail_future = workflow.execute_activity(
                        "thumbnail_activity",
                        args=[{
                            "content_id": content_id,
                            "channel_id": params.channel_id,
                            "title": final_title,
                            "topic": topic,
                            "niche": "",
                        }],
                        start_to_close_timeout=timedelta(minutes=10),
                        retry_policy=RETRY_STANDARD,
                    )

                    music_future = workflow.execute_activity(
                        "music_activity",
                        args=[{
                            "content_id": content_id,
                            "channel_id": params.channel_id,
                            "mood": "",
                            "duration_s": voice_data.get("duration_s", 45.0),
                        }],
                        start_to_close_timeout=timedelta(minutes=2),
                        retry_policy=RETRY_STANDARD,
                    )

                    assets_result, thumbnail_result, music_result = await asyncio.gather(
                        assets_future, thumbnail_future, music_future)
                    self._accrued_cost += _add_cost(budget, assets_result)
                    self._accrued_cost += _add_cost(budget, thumbnail_result)
                    self._check_budget(budget)

                    thumbnail_data = thumbnail_result.get("data", {})
                    thumb_score = thumbnail_data.get("thumbnail_score", 7.0)
                    quality_scores["thumbnail_score"] = thumb_score
                    music_data = music_result.get("data", {})

                if thumb_score < THRESHOLDS["thumbnail_score"]:
                    workflow.logger.warning(
                        f"Thumbnail score {thumb_score} below target {THRESHOLDS['thumbnail_score']} "
                        f"after regenerations — proceeding")

                await self._complete_phase(content_id, ch, "generating_assets",
                                           detail={"thumb_score": thumb_score})
                workflow.logger.info(
                    f"Assets + Thumbnail + Music done (thumb score: {thumb_score}, "
                    f"regens: {thumbnail_data.get('regeneration_count', 0)})")

                await self._save_phase_data(content_id, "generating_assets", {
                    "assets_result": assets_result,
                    "thumbnail_data": thumbnail_data,
                    "music_data": music_data,
                    "thumb_score": quality_scores.get("thumbnail_score", 7.0),
                })

            await self._check_pause()
            self._check_brain_directive()

            if _should_skip("directing", resume_from):
                workflow.logger.info("Skipping directing (already completed)")
            else:
                await self._set_phase(content_id, "directing", ch)

                direction_result = await workflow.execute_activity(
                    "direction_activity",
                    args=[{
                        "content_id": content_id,
                        "channel_id": params.channel_id,
                        "content_mode": params.content_mode,
                        "title": final_title,
                        "script_segments": segments,
                        "voice_manifest": voice_data,
                        "asset_manifest": assets_result.get("data", {}).get("manifest", []),
                        "thumbnail_result": thumbnail_data,
                        "music_data": music_data,
                        "script_direction_hint": script_direction_data,
                    }],
                    start_to_close_timeout=timedelta(minutes=3),
                    retry_policy=RETRY_STANDARD,
                )
                self._accrued_cost += _add_cost(budget, direction_result)

                direction_data = direction_result.get("data", {})
                direction_v3 = direction_data.get("direction_v3", {})
                dir_score = direction_data.get("direction_score", 7.0)
                quality_scores["direction_score"] = dir_score

                if dir_score < THRESHOLDS["direction_score"]:
                    workflow.logger.warning(
                        f"Direction score {dir_score} below threshold {THRESHOLDS['direction_score']}")

                await self._complete_phase(content_id, ch, "directing",
                                           detail={"score": dir_score})
                workflow.logger.info(
                    f"Direction done: {direction_data.get('segment_count', 0)} segments "
                    f"(score: {dir_score})")

                await self._save_phase_data(content_id, "directing", {
                    "direction_data": direction_data,
                    "direction_v3": direction_v3,
                    "dir_score": dir_score,
                })

            await self._check_pause()
            self._check_brain_directive()

            if _should_skip("post_production", resume_from):
                workflow.logger.info("Skipping post_production (already completed)")
            else:
                await self._set_phase(content_id, "post_production", ch)

                try:
                    editor_result = await workflow.execute_activity(
                        "editor_activity",
                        args=[{
                            "content_id": content_id,
                            "channel_id": params.channel_id,
                            "direction_v3": direction_v3,
                            "voice_manifest": voice_data,
                            "brand_profile": brand_profile,
                        }],
                        start_to_close_timeout=timedelta(minutes=3),
                        retry_policy=RETRY_STANDARD,
                    )

                    editor_data = editor_result.get("data", {})
                    if editor_data.get("optimized_direction"):
                        direction_v3 = editor_data["optimized_direction"]
                        workflow.logger.info(
                            f"Editor applied: pacing_optimized={editor_data.get('pacing_optimized', False)}, "
                            f"qc_passed={editor_data.get('qc_passed', False)}, "
                            f"qc_score={editor_data.get('qc_score', 'N/A')}")
                    else:
                        workflow.logger.info("Editor returned no optimized direction — using original")

                except Exception as editor_err:
                    workflow.logger.warning(f"Editor activity failed — using original direction: {editor_err}")
                await self._complete_phase(content_id, ch, "post_production")

                await self._save_phase_data(content_id, "post_production", {
                    "direction_v3": direction_v3,
                })

            await self._check_pause()
            self._check_brain_directive()

            if _should_skip("rendering", resume_from):
                workflow.logger.info("Skipping rendering (already completed)")
            else:
                await self._set_phase(content_id, "rendering", ch)

                assembly_result = await workflow.execute_activity(
                    "assembly_activity",
                    args=[{
                        "content_id": content_id,
                        "channel_id": params.channel_id,
                        "content_mode": params.content_mode,
                        "title": final_title,
                        "direction_v3": direction_v3,
                        "thumbnail_url": thumbnail_data.get("selected_thumbnail", {}).get("url", ""),
                        "environment": env,
                    }],
                    start_to_close_timeout=timedelta(hours=1),
                    heartbeat_timeout=timedelta(minutes=2),
                    retry_policy=RETRY_RENDER,
                )

                assembly_data = assembly_result.get("data", {})
                video_url = assembly_data.get("video_url", "")
                prod_score = assembly_data.get("production_score", 7.0)
                quality_scores["production_score"] = prod_score

                await self._complete_phase(content_id, ch, "rendering",
                                           detail={"video_url": video_url[:80], "score": prod_score})
                workflow.logger.info(f"Render done: {video_url[:80]} (score: {prod_score})")

                await self._save_phase_data(content_id, "rendering", {
                    "assembly_data": assembly_data,
                    "video_url": video_url,
                    "prod_score": prod_score,
                })

            await self._check_pause()
            self._check_brain_directive()

            if _should_skip("finishing", resume_from):
                workflow.logger.info("Skipping finishing (already completed)")
            elif video_url:
                await self._set_phase(content_id, "finishing", ch)

                finishing_result = await workflow.execute_activity(
                    "finishing_activity",
                    args=[{
                        "content_id": content_id,
                        "channel_id": params.channel_id,
                        "video_url": video_url,
                    }],
                    start_to_close_timeout=timedelta(minutes=10),
                    heartbeat_timeout=timedelta(minutes=3),
                    retry_policy=RETRY_FINISH,
                )

                fin_data = finishing_result.get("data", {})
                finished_url = fin_data.get("finished_url", "")
                if finished_url and not fin_data.get("skipped"):
                    video_url = finished_url
                    workflow.logger.info(
                        f"Finishing applied: {video_url[:80]} "
                        f"(preset {fin_data.get('preset_used')})")
                else:
                    workflow.logger.info("Finishing skipped — delivering raw render")

                await self._complete_phase(
                    content_id, ch, "finishing",
                    detail={"skipped": bool(fin_data.get("skipped")),
                            "preset": fin_data.get("preset_used")})

                await self._save_phase_data(content_id, "finishing", {
                    "video_url": video_url,
                    "finishing": fin_data,
                })
            else:
                workflow.logger.info("Finishing skipped — no rendered video_url")

            score_values = [v for v in quality_scores.values() if isinstance(v, (int, float))]
            composite_score = round(sum(score_values) / len(score_values), 1) if score_values else 0

            quality_scores["composite_score"] = composite_score
            needs_human_review = (
                composite_score < THRESHOLDS["composite_score"]
                or prod_score < THRESHOLDS["production_score"]
                or getattr(params, "human_review_required", False)
            )

            workflow.logger.info(
                f"Quality composite: {composite_score}, "
                f"needs_review: {needs_human_review}, "
                f"scores: {quality_scores}")

            if needs_human_review:
                await self._set_phase(content_id, "pending_review", ch)

                await workflow.execute_activity(
                    "send_notification",
                    args=[{
                        "type": "human_review_required",
                        "content_id": content_id,
                        "channel_id": params.channel_id,
                        "topic": topic,
                        "composite_score": composite_score,
                        "quality_scores": quality_scores,
                        "failed_gates": [
                            k for k, v in quality_scores.items()
                            if isinstance(v, (int, float)) and k in THRESHOLDS and v < THRESHOLDS[k]
                        ],
                    }],
                    start_to_close_timeout=timedelta(seconds=30),
                )

                try:
                    await workflow.wait_condition(
                        lambda: self._human_approved is not None,
                        timeout=timedelta(hours=24),
                    )
                except asyncio.TimeoutError:
                    self._human_approved = True

                if not self._human_approved:
                    await self._set_phase(content_id, "rejected", ch)
                    return VideoResult(
                        status="rejected",
                        content_id=content_id,
                        youtube_video_id="",
                        cost=self._accrued_cost,
                    )

            await self._check_pause()
            self._check_brain_directive()

            packaging = script_data.get("packaging", {})
            description = packaging.get("description", script_data.get("description", ""))
            tags = packaging.get("tags", script_data.get("tags", []))

            if _should_skip("delivering", resume_from):
                workflow.logger.info("Skipping delivering (already completed)")
            else:
                await self._set_phase(content_id, "delivering", ch)

                if is_test_mode:
                    youtube_id = "TEST_SKIP"
                    workflow.logger.info("Test mode — computing metadata without YouTube upload")
                    try:
                        await workflow.execute_activity(
                            "compute_metadata_activity",
                            args=[{
                                "content_id": content_id,
                                "channel_id": params.channel_id,
                                "content_mode": params.content_mode,
                                "title": final_title,
                                "description": description,
                                "tags": tags,
                                "niche": "",
                                "quality_scores": quality_scores,
                                "is_short": params.content_mode == "short",
                            }],
                            start_to_close_timeout=timedelta(minutes=2),
                            retry_policy=RETRY_STANDARD,
                        )
                    except Exception as meta_err:
                        workflow.logger.warning(f"Metadata computation failed (non-critical): {meta_err}")
                    await self._complete_phase(content_id, ch, "delivering",
                                               detail={"youtube_id": youtube_id, "skipped": True, "reason": "test_mode"})
                else:
                    delivery_result = await workflow.execute_activity(
                        "delivery_activity",
                        args=[{
                            "content_id": content_id,
                            "channel_id": params.channel_id,
                            "content_mode": params.content_mode,
                            "title": final_title,
                            "description": description,
                            "tags": tags,
                            "video_url": video_url,
                            "thumbnail_url": thumbnail_data.get("selected_thumbnail", {}).get("url", ""),
                            "privacy_status": "private",
                            "is_short": params.content_mode == "short",
                            "quality_scores": quality_scores,
                            "human_review_required": False,
                        }],
                        start_to_close_timeout=timedelta(minutes=10),
                        retry_policy=RETRY_STANDARD,
                    )

                    youtube_id = delivery_result.get("data", {}).get("youtube_video_id", "")
                    await self._complete_phase(content_id, ch, "delivering",
                                               detail={"youtube_id": youtube_id})
                    workflow.logger.info(f"Delivered: https://youtu.be/{youtube_id}")

            if _should_skip("analytics", resume_from):
                workflow.logger.info("Skipping analytics (already completed)")
            else:
                should_run_analytics = bool(youtube_id) and youtube_id != "TEST_SKIP"
                if should_run_analytics:
                    await self._set_phase(content_id, "analytics", ch)
                    try:
                        await workflow.execute_activity(
                            "analytics_activity",
                            args=[{
                                "channel_id": params.channel_id,
                                "youtube_video_ids": [youtube_id],
                            }],
                            start_to_close_timeout=timedelta(seconds=120),
                        )
                        await self._complete_phase(content_id, ch, "analytics")
                    except Exception as analytics_exc:
                        workflow.logger.warning(f"Analytics activity failed — non-critical, continuing: {analytics_exc}")
                        await self._complete_phase(content_id, ch, "analytics")
                else:
                    workflow.logger.info(
                        "Analytics phase skipped — no real YouTube upload to measure",
                        youtube_id=youtube_id,
                    )

            if brand_profile:
                try:
                    await workflow.execute_activity(
                        "brand_activity",
                        args=[{
                            "action": "consistency",
                            "channel_id": params.channel_id,
                            "content_id": content_id,
                            "title": final_title,
                            "description": description,
                            "tags": tags,
                            "quality_scores": quality_scores,
                        }],
                        start_to_close_timeout=timedelta(seconds=30),
                    )
                except Exception:
                    workflow.logger.warning("Brand consistency check failed — non-critical")

            final_status = "test_delivered" if is_test_mode else "delivered"
            await self._set_phase(content_id, final_status, ch)
            await self._complete_phase(content_id, ch, final_status,
                                       cost=self._accrued_cost,
                                       detail={"youtube_id": youtube_id, "composite_score": composite_score,
                                               "environment": env})

            return VideoResult(
                status=final_status,
                content_id=content_id,
                youtube_video_id=youtube_id,
                cost=self._accrued_cost,
            )

        except Exception as exc:
            workflow.logger.error(f"Pipeline failed: {exc}")
            self._current_phase = "failed"
            try:
                await workflow.execute_activity(
                    "update_video_status",
                    args=[content_id, "failed", self._channel_id, self._title, self._content_mode],
                    start_to_close_timeout=timedelta(seconds=10),
                )
                await self._fail_phase(content_id, ch, self._current_phase, str(exc))
            except Exception:
                pass
            raise

        finally:
            try:
                await workflow.execute_activity(
                    "release_channel_lock",
                    args=[params.channel_id],
                    start_to_close_timeout=timedelta(seconds=10),
                )
            except Exception:
                pass
