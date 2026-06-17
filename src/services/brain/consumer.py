"""Brain event consumer — listens for pipeline events and triggers analysis.

Subscribes to:
  * ``pipeline.video.complete`` — a video finished (success or with caveats)
  * ``pipeline.video.failed``   — a video workflow terminated with an error

On each event the consumer:
  1. Reads channel signals via :mod:`analyser`
  2. Runs the decision engine via :mod:`engine`
  3. If a decision was written, publishes ``brain.directive`` on the event bus
  4. If ``brain.advisory_mode`` is FALSE, sends a Temporal signal to the
     running workflow (if ``workflow_id`` is present in the envelope)

The consumer loop is resilient — handler exceptions are caught + logged so
one bad envelope never breaks the subscriber loop (the event bus already
handles envelope-level validation).

AE-P1 / Brain Service.
"""
from __future__ import annotations

import asyncio
import json

import structlog

from src.events.bus import publish, subscribe
from src.events.topics import Topic
from src.flags import get_flag
from src.services.brain.analyser import analyse_channel
from src.services.brain.engine import evaluate

logger = structlog.get_logger()

_SOURCE = "brain-service"


async def handle_pipeline_event(envelope: dict) -> None:
    """Dispatch handler for both video.complete and video.failed topics.

    When ``brain.memory_recall.enabled`` is TRUE we route through
    :class:`BrainAgent.run` so RAG recall over past ``brain_decisions``
    enriches the reasoning field. When FALSE we keep the legacy
    analyse → evaluate sequence — bit-for-bit identical behaviour.
    """
    payload = envelope.get("payload", {})
    channel_id = envelope.get("scope_id") or payload.get("channel_id", "")
    content_id = payload.get("content_id")
    topic = envelope.get("topic", "")

    if not channel_id:
        logger.warning("brain.consumer.missing_channel_id", envelope=envelope)
        return

    logger.info(
        "brain.consumer.received",
        topic=topic,
        channel_id=channel_id,
        content_id=content_id,
    )

    use_agent = await get_flag("brain.memory_recall.enabled", default=False)
    if use_agent:
        # Agent path: framework owns observe→recall→reason→decide→act.
        # The agent publishes the directive itself, so we return early.
        from src.services.brain.agent import BrainAgent
        await BrainAgent().run(
            {"channel_id": channel_id, "content_id": content_id}
        )
        return

    signals = await analyse_channel(channel_id)
    decision = await evaluate(signals, content_id=content_id)

    if decision is None:
        return

    # Publish directive event so downstream subscribers can react.
    try:
        await publish(
            Topic.BRAIN_DIRECTIVE,
            scope="video" if content_id else "channel",
            scope_id=content_id or channel_id,
            payload={
                "decision_id": decision["id"],
                "decision_type": decision["decision_type"],
                "directive": decision["directive"],
                "reasoning": decision.get("reasoning", ""),
                "confidence": float(decision.get("confidence") or 0),
            },
            source_service=_SOURCE,
            confidence=float(decision.get("confidence") or 0),
        )
    except Exception as exc:
        logger.warning(
            "brain.consumer.directive_publish_failed",
            decision_id=decision["id"],
            error=str(exc),
        )

    # Signal the Temporal workflow if advisory mode is OFF and workflow_id known.
    advisory = await get_flag("brain.advisory_mode", default=True)
    if not advisory and content_id:
        workflow_id = payload.get("workflow_id") or f"video-production-{content_id}"
        await _signal_workflow(workflow_id, decision)


async def _signal_workflow(workflow_id: str, decision: dict) -> None:
    """Send ``receive_brain_directive`` signal to the Temporal workflow."""
    try:
        from temporalio.client import Client  # type: ignore

        client = await Client.connect("localhost:7233")
        handle = client.get_workflow_handle(workflow_id)
        await handle.signal("receive_brain_directive", decision["directive"])
        logger.info(
            "brain.consumer.workflow_signalled",
            workflow_id=workflow_id,
            decision_id=decision["id"],
        )
    except Exception as exc:
        logger.warning(
            "brain.consumer.signal_failed",
            workflow_id=workflow_id,
            error=str(exc),
        )


async def run_consumer(stop_event: asyncio.Event | None = None) -> None:
    """Run the pipeline event consumer loop.

    Subscribes to both pipeline topics and dispatches to :func:`handle_pipeline_event`.
    Blocks until *stop_event* is set or the process is interrupted.
    """
    topics = [Topic.PIPELINE_VIDEO_COMPLETE, Topic.PIPELINE_VIDEO_FAILED]
    logger.info("brain.consumer.starting", topics=[t.value for t in topics])
    await subscribe(topics, handle_pipeline_event, stop_event=stop_event)
    logger.info("brain.consumer.stopped")
