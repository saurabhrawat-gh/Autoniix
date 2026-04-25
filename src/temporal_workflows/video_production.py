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
            quality_scores["research_depth_score"] = research_data.get("research_depth_score", 7.0)

            workflow.logger.info(f"Research done: {topic}")

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
                }],
                start_to_close_timeout=timedelta(minutes=5),
                retry_policy=RETRY_STANDARD,
            )
            self._accrued_cost += _add_cost(budget, script_result)
            self._check_budget(budget)

            script_data = script_result.get("data", {})
            segments = script_data.get("segments", [])
            final_title = script_data.get("title", title)
            quality_scores["script_structure_score"] = script_data.get("script_structure_score", 7.0)
            quality_scores["hook_retention_score"] = script_data.get("hook_retention_score", 7.0)

            workflow.logger.info(f"Script done: {len(segments)} segments")

            # ── Phase 3: Voice ───────────────────────────
            await self._set_phase(content_id, "generating_voice")

            voice_result = await workflow.execute_activity(
                "voice_activity",
                args=[{
                    "content_id": content_id,
                    "channel_id": params.channel_id,
                    "content_mode": params.content_mode,
                    "voice_id": "",
                    "script_segments": [
                        {"id": s.get("id"), "section": s.get("section", "body"),
                         "narration": s.get("narration", "")}
                        for s in segments
                    ],
                }],
                start_to_close_timeout=timedelta(minutes=10),
                retry_policy=RETRY_STANDARD,
            )
            self._accrued_cost += _add_cost(budget, voice_result)
            self._check_budget(budget)

            voice_data = voice_result.get("data", {})
            quality_scores["voice_quality_score"] = voice_data.get("voice_quality_score", 7.0)
            workflow.logger.info(f"Voice done: {voice_data.get('duration_s', 0)}s")

            # ── Phase 4: Assets + Thumbnail + Music (parallel) ─
            await self._set_phase(content_id, "generating_assets")

            assets_future = workflow.execute_activity(
                "assets_activity",
                args=[{
                    "content_id": content_id,
                    "channel_id": params.channel_id,
                    "content_mode": params.content_mode,
                    "segments": [
                        {"id": s.get("id"), "scene_direction": s.get("scene_direction", ""),
                         "asset_suggestions": s.get("asset_suggestions", []),
                         "b_roll_keywords": s.get("b_roll_keywords", [])}
                        for s in segments
                    ],
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
                start_to_close_timeout=timedelta(minutes=5),
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
            quality_scores["thumbnail_score"] = thumbnail_data.get("thumbnail_score", 7.0)
            music_data = music_result.get("data", {})

            workflow.logger.info("Assets + Thumbnail + Music done")

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
                }],
                start_to_close_timeout=timedelta(minutes=3),
                retry_policy=RETRY_STANDARD,
            )
            self._accrued_cost += _add_cost(budget, direction_result)

            direction_data = direction_result.get("data", {})
            direction_v3 = direction_data.get("direction_v3", {})
            quality_scores["direction_score"] = direction_data.get("direction_score", 7.0)

            workflow.logger.info(f"Direction done: {direction_data.get('segment_count', 0)} segments")

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
            quality_scores["production_score"] = assembly_data.get("production_score", 7.0)

            workflow.logger.info(f"Render done: {video_url[:80]}")

            # ── Phase 7: Human Review Gate ───────────────
            human_review = getattr(params, "human_review_required", False)
            if human_review:
                await self._set_phase(content_id, "pending_review")
                # Wait for human signal (up to 24 hours)
                try:
                    await workflow.wait_condition(
                        lambda: self._human_approved is not None,
                        timeout=timedelta(hours=24),
                    )
                except asyncio.TimeoutError:
                    # Auto-approve after 24h timeout
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

            # Get packaging data from script
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
