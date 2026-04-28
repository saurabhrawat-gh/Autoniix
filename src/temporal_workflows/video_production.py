from __future__ import annotations

import asyncio
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from src.schemas.common import VideoParams, VideoResult

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


def _add_cost(budget: dict, result: dict) -> float:
    cost = result.get("cost", {}).get("cost_usd", 0)
    budget["accrued_cost_usd"] = budget.get("accrued_cost_usd", 0) + cost
    return cost


@workflow.defn
class VideoProductionWorkflow:

    def __init__(self) -> None:
        self._human_approved: bool | None = None
        self._accrued_cost: float = 0.0
        self._current_phase: str = "init"

    # ── Signals ──────────────────────────────────────────

    @workflow.signal
    async def approve_video(self, approved: bool) -> None:
        self._human_approved = approved

    @workflow.signal
    async def emergency_stop(self) -> None:
        self._human_approved = False

    # ── Queries ──────────────────────────────────────────

    @workflow.query
    def get_status(self) -> dict:
        return {
            "phase": self._current_phase,
            "accrued_cost": self._accrued_cost,
            "human_approved": self._human_approved,
        }

    # ── Helpers ──────────────────────────────────────────

    async def _set_phase(self, content_id: str, phase: str) -> None:
        self._current_phase = phase
        await workflow.execute_activity(
            "update_video_status",
            args=[content_id, phase],
            start_to_close_timeout=timedelta(seconds=10),
        )

    def _check_budget(self, budget: dict) -> None:
        if budget["accrued_cost_usd"] > budget["max_cost_usd"]:
            raise RuntimeError(
                f"Budget exceeded: ${budget['accrued_cost_usd']:.2f} > ${budget['max_cost_usd']:.2f}"
            )

    # ── Main Pipeline ────────────────────────────────────

    @workflow.run
    async def run(self, params: VideoParams) -> VideoResult:
        ts = workflow.now().strftime("%Y%m%d_%H%M")
        content_id = f"VID_{params.channel_id}_{ts}"
        budget = {"max_cost_usd": params.max_cost_usd, "accrued_cost_usd": 0}
        quality_scores = {}

        # Quality thresholds (critical = 9.0, supporting = 8.0)
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
            # ── Phase 1: Research ────────────────────────
            await self._set_phase(content_id, "researching")

            research = await workflow.execute_activity(
                "research_activity",
                args=[{
                    "channel_id": params.channel_id,
                    "content_mode": params.content_mode,
                    "topic_candidates": params.topic_candidates,
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
            research_score = research_data.get("research_depth_score", 7.0)
            quality_scores["research_depth_score"] = research_score

            # Quality gate: research
            if research_score < THRESHOLDS["research_depth_score"]:
                workflow.logger.warning(
                    f"Research score {research_score} below threshold {THRESHOLDS['research_depth_score']} — proceeding with warning")

            workflow.logger.info(f"Research done: {topic} (score: {research_score})")

            # ── Phase 1B: Brand Identity ──────────────────
            await self._set_phase(content_id, "brand_check")

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

            # ── Phase 2: Script ──────────────────────────
            await self._set_phase(content_id, "scripting")

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

            # Multi-view response: {script_base, script_voice, script_assets, script_direction}
            full_script_data = script_result.get("data", {})
            script_data = full_script_data.get("script_base", full_script_data)
            script_voice_data = full_script_data.get("script_voice", {})
            script_assets_data = full_script_data.get("script_assets", {})
            script_direction_data = full_script_data.get("script_direction", {})
            intelligence_scores = full_script_data.get("intelligence_scores", {})

            segments = script_data.get("segments", [])
            final_title = script_data.get("title", title)
            script_score = script_data.get("script_structure_score", 7.0)
            quality_scores["script_structure_score"] = script_score
            quality_scores["hook_retention_score"] = script_data.get("hook_retention_score", 7.0)

            # Quality gate: script (hard gate — score must be reasonable)
            if script_score < THRESHOLDS["script_structure_score"]:
                workflow.logger.warning(
                    f"Script score {script_score} below target {THRESHOLDS['script_structure_score']} "
                    f"after rewrites — proceeding (rewrite loop already exhausted)")

            workflow.logger.info(
                f"Script done: {len(segments)} segments, score: {script_score}, "
                f"rewrites: {script_data.get('rewrite_count', 0)}, "
                f"intelligence: {intelligence_scores}")

            # ── Phase 3: Voice ───────────────────────────
            await self._set_phase(content_id, "generating_voice")

            # Build voice segments with prosody data from Script Intelligence
            voice_prosody_segs = script_voice_data.get("segments", []) if isinstance(script_voice_data, dict) else []
            voice_segments_input = []
            for i, s in enumerate(segments):
                seg_input = {
                    "id": s.get("id"),
                    "section": s.get("section", "body"),
                    "narration": s.get("narration", ""),
                    "emotion": s.get("emotion", ""),
                    "emphasis_words": s.get("emphasis_words", []),
                }
                # Enrich with prosody engine data if available
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

            workflow.logger.info(f"Voice done: {voice_data.get('duration_s', 0)}s (score: {voice_score})")

            # ── Phase 4: Assets + Thumbnail + Music (parallel) ─
            await self._set_phase(content_id, "generating_assets")

            # Build asset segments enriched with Script Intelligence queries
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
                # Enrich with asset engine queries if available
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

            workflow.logger.info(
                f"Assets + Thumbnail + Music done (thumb score: {thumb_score}, "
                f"regens: {thumbnail_data.get('regeneration_count', 0)})")

            # ── Phase 5: Direction ───────────────────────
            await self._set_phase(content_id, "directing")

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

            workflow.logger.info(
                f"Direction done: {direction_data.get('segment_count', 0)} segments "
                f"(score: {dir_score})")

            # ── Phase 5B: Editor / Post-Production ────────
            await self._set_phase(content_id, "post_production")

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
                # Apply editor optimizations back to direction_v3
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

            # ── Phase 6: Assembly (Remotion render) ──────
            await self._set_phase(content_id, "rendering")

            assembly_result = await workflow.execute_activity(
                "assembly_activity",
                args=[{
                    "content_id": content_id,
                    "channel_id": params.channel_id,
                    "content_mode": params.content_mode,
                    "title": final_title,
                    "direction_v3": direction_v3,
                    "thumbnail_url": thumbnail_data.get("selected_thumbnail", {}).get("url", ""),
                }],
                start_to_close_timeout=timedelta(hours=1),
                heartbeat_timeout=timedelta(minutes=2),
                retry_policy=RETRY_RENDER,
            )

            assembly_data = assembly_result.get("data", {})
            video_url = assembly_data.get("video_url", "")
            prod_score = assembly_data.get("production_score", 7.0)
            quality_scores["production_score"] = prod_score

            workflow.logger.info(f"Render done: {video_url[:80]} (score: {prod_score})")

            # ── Phase 7: Compute Composite & Human Review Gate ─
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
                await self._set_phase(content_id, "pending_review")

                # Notify
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

                # Wait for human signal (up to 24 hours)
                try:
                    await workflow.wait_condition(
                        lambda: self._human_approved is not None,
                        timeout=timedelta(hours=24),
                    )
                except asyncio.TimeoutError:
                    self._human_approved = True

                if not self._human_approved:
                    await self._set_phase(content_id, "rejected")
                    return VideoResult(
                        status="rejected",
                        content_id=content_id,
                        youtube_video_id="",
                        cost=self._accrued_cost,
                    )

            # ── Phase 8: Delivery ────────────────────────
            await self._set_phase(content_id, "delivering")

            packaging = script_data.get("packaging", {})
            description = packaging.get("description", script_data.get("description", ""))
            tags = packaging.get("tags", script_data.get("tags", []))

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
            workflow.logger.info(f"Delivered: https://youtu.be/{youtube_id}")

            # ── Phase 9: Analytics + Intelligence Feedback ──
            await self._set_phase(content_id, "analytics")

            try:
                await workflow.execute_activity(
                    "analytics_activity",
                    args=[{
                        "content_id": content_id,
                        "channel_id": params.channel_id,
                        "youtube_video_id": youtube_id,
                        "quality_scores": quality_scores,
                        "total_cost": self._accrued_cost,
                    }],
                    start_to_close_timeout=timedelta(seconds=30),
                )
            except Exception:
                workflow.logger.warning("Analytics activity failed — non-critical, continuing")

            # Brand consistency check on final output
            if brand_profile:
                try:
                    await workflow.execute_activity(
                        "brand_consistency_activity",
                        args=[{
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

            # ── Done ─────────────────────────────────────
            await self._set_phase(content_id, "delivered")

            return VideoResult(
                status="delivered",
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
                    args=[content_id, "failed"],
                    start_to_close_timeout=timedelta(seconds=10),
                )
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
