from __future__ import annotations

import asyncio
import hashlib
import json
import random
from datetime import UTC, datetime, timedelta
from typing import Any

import asyncpg
import structlog

from .channels import Channel, NotificationPayload

logger = structlog.get_logger()

# Exponential backoff: 1s, 5s, 25s, 125s, then capped at 5m. Jittered ±25%.
_BACKOFF_BASE_S = 1.0
_BACKOFF_FACTOR = 5.0
_BACKOFF_CAP_S = 300.0


def _backoff_delay(attempt: int) -> float:
    """Compute jittered exponential backoff for ``attempt`` (1-based)."""
    raw = min(_BACKOFF_BASE_S * (_BACKOFF_FACTOR ** max(attempt - 1, 0)), _BACKOFF_CAP_S)
    jitter = random.uniform(0.75, 1.25)
    return raw * jitter


def _dedup_key(channel: str, event_type: str, channel_id: str, video_id: str, day_bucket: str) -> str:
    """Stable content-based dedup key with a day bucket to allow legit re-sends after 24h."""
    raw = f"{channel}|{event_type}|{channel_id}|{video_id}|{day_bucket}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


class DeliveryRow:
    def __init__(
        self,
        delivery_id: int,
        notification_id: int,
        channel: str,
        attempts: int,
        config: dict[str, Any],
        notification: NotificationPayload,
    ):
        self.delivery_id = delivery_id
        self.notification_id = notification_id
        self.channel = channel
        self.attempts = attempts
        self.config = config
        self.notification = notification


class Dispatcher:
    def __init__(
        self,
        pool: asyncpg.Pool,
        channels: dict[str, Channel],
        poll_interval_ms: int,
        stale_after_ms: int,
        batch_size: int,
        max_attempts: int,
        http_timeout_ms: int,
    ):
        self.pool = pool
        self.channels = channels
        self.poll_interval = timedelta(milliseconds=poll_interval_ms)
        self.stale_after = timedelta(milliseconds=stale_after_ms)
        self.batch_size = batch_size
        self.max_attempts = max_attempts
        self.http_timeout = timedelta(milliseconds=http_timeout_ms)

    async def run(self, stop_event: asyncio.Event):
        logger.info(
            "dispatcher.start",
            poll_ms=int(self.poll_interval.total_seconds() * 1000),
            stale_ms=int(self.stale_after.total_seconds() * 1000),
            batch=self.batch_size,
        )

        await self.tick()

        while not stop_event.is_set():
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=self.poll_interval.total_seconds())
                break
            except TimeoutError:
                await self.tick()

        logger.info("dispatcher.stopped")

    async def tick(self):
        try:
            rows = await self._claim()
            if not rows:
                return

            logger.info("dispatcher.batch", size=len(rows))
            await asyncio.gather(*[self._deliver(r) for r in rows], return_exceptions=True)
        except Exception as e:
            logger.warning("dispatcher.tick.error", error=str(e))

    async def _claim(self) -> list[DeliveryRow]:
        now = datetime.now(UTC)
        stale_cutoff = now - self.stale_after

        async with self.pool.acquire() as conn:
            async with conn.transaction():
                # Eligible rows:
                #  - queued (never attempted) older than stale_cutoff
                #  - failed with attempts remaining AND next_attempt_at reached
                #    (or NULL, for pre-migration rows — treated as eligible now)
                query = """
                    SELECT d.id, d.notification_id, d.channel, d.attempts,
                           COALESCE(r.config, '{}'::jsonb) AS route_config,
                           n.event_type, n.severity, n.title,
                           COALESCE(n.body, '') AS body,
                           COALESCE(n.payload, '{}'::jsonb) AS payload,
                           COALESCE(n.channel_id, '') AS channel_id,
                           COALESCE(n.video_id, '') AS video_id
                      FROM notification_deliveries d
                      JOIN notifications n ON n.id = d.notification_id
                      LEFT JOIN notification_routes r ON r.id = d.route_id
                     WHERE (
                             (d.status = 'queued' AND d.created_at < $1)
                          OR (
                                d.status = 'failed'
                                AND d.attempts < $2
                                AND (d.next_attempt_at IS NULL OR d.next_attempt_at <= $4)
                             )
                           )
                     ORDER BY d.created_at ASC
                     LIMIT $3
                     FOR UPDATE OF d SKIP LOCKED
                """
                pg_rows = await conn.fetch(query, stale_cutoff, self.max_attempts, self.batch_size, now)

                if not pg_rows:
                    return []

                out = []
                for row in pg_rows:
                    cfg = (
                        json.loads(row["route_config"]) if isinstance(row["route_config"], str) else row["route_config"]
                    )
                    payload_data = json.loads(row["payload"]) if isinstance(row["payload"], str) else row["payload"]

                    notification = NotificationPayload(
                        event_type=row["event_type"],
                        severity=row["severity"],
                        title=row["title"],
                        body=row["body"],
                        payload=payload_data or {},
                        channel_id=row["channel_id"] or "",
                        video_id=row["video_id"] or "",
                    )

                    out.append(
                        DeliveryRow(
                            delivery_id=row["id"],
                            notification_id=row["notification_id"],
                            channel=row["channel"],
                            attempts=row["attempts"],
                            config=cfg or {},
                            notification=notification,
                        )
                    )

                ids = [r.delivery_id for r in out]
                await conn.execute(
                    "UPDATE notification_deliveries SET status='queued', attempts=attempts+1 WHERE id = ANY($1::bigint[])",
                    ids,
                )

                return out

    async def _deliver(self, r: DeliveryRow):
        ch = self.channels.get(r.channel)
        if not ch:
            await self._mark_dead_letter(r, f"unknown channel {r.channel!r}")
            return

        # Content-based dedup: skip if an identical (channel, event, target)
        # delivery already succeeded in the same UTC day. Prevents duplicate
        # Slack pings when a workflow retries.
        try:
            day_bucket = datetime.now(UTC).strftime("%Y-%m-%d")
            dedup = _dedup_key(
                r.channel,
                r.notification.event_type,
                r.notification.channel_id,
                r.notification.video_id,
                day_bucket,
            )
            existed = await self.pool.fetchval(
                "SELECT 1 FROM notification_deliveries d "
                "JOIN notifications n ON n.id = d.notification_id "
                "WHERE d.channel = $1 AND d.status = 'sent' "
                "AND n.event_type = $2 "
                "AND COALESCE(n.channel_id,'') = $3 "
                "AND COALESCE(n.video_id,'') = $4 "
                "AND n.dedupe_key = $5 "
                "AND d.id != $6 "
                "AND d.sent_at >= NOW() - INTERVAL '24 hours' "
                "LIMIT 1",
                r.channel,
                r.notification.event_type,
                r.notification.channel_id,
                r.notification.video_id,
                dedup,
                r.delivery_id,
            )
            if existed:
                logger.info("dispatcher.dedup_skip", id=r.delivery_id, dedup=dedup)
                await self.pool.execute(
                    "UPDATE notification_deliveries SET status='dropped', error='dedup', sent_at=NOW() WHERE id=$1",
                    r.delivery_id,
                )
                return
            # Best-effort: stamp the dedupe_key on the notification for future comparisons
            await self.pool.execute(
                "UPDATE notifications SET dedupe_key = $1 WHERE id = $2 AND dedupe_key IS NULL",
                dedup,
                r.notification_id,
            )
        except Exception as e:
            logger.debug("dispatcher.dedup_check_failed", error=str(e))

        try:
            resp = await asyncio.wait_for(
                ch.send(r.notification, r.config),
                timeout=self.http_timeout.total_seconds(),
            )
            await self._mark_sent(r.delivery_id, resp)
        except Exception as e:
            await self._mark_failed(r, str(e))

    async def _mark_sent(self, delivery_id: int, resp: dict[str, Any]):
        try:
            await self.pool.execute(
                "UPDATE notification_deliveries SET status='sent', response=$1::jsonb, sent_at=NOW(), "
                "next_attempt_at=NULL WHERE id=$2",
                json.dumps(resp),
                delivery_id,
            )
        except Exception as e:
            logger.warning("mark.sent.failed", id=delivery_id, error=str(e))

    async def _mark_failed(self, r: DeliveryRow, err_msg: str):
        """Mark failed with exponential backoff, or promote to dead-letter if out of attempts."""
        next_attempts = r.attempts + 1
        if next_attempts >= self.max_attempts:
            await self._mark_dead_letter(r, err_msg)
            return
        delay_s = _backoff_delay(next_attempts)
        next_at = datetime.now(UTC) + timedelta(seconds=delay_s)
        try:
            await self.pool.execute(
                "UPDATE notification_deliveries SET status='failed', error=$1, sent_at=NOW(), "
                "next_attempt_at=$2 WHERE id=$3",
                err_msg,
                next_at,
                r.delivery_id,
            )
            logger.info(
                "dispatcher.retry_scheduled",
                id=r.delivery_id,
                attempt=next_attempts,
                delay_s=round(delay_s, 1),
                next_at=next_at.isoformat(),
            )
        except Exception as e:
            logger.warning("mark.failed.failed", id=r.delivery_id, error=str(e))

    async def _mark_dead_letter(self, r: DeliveryRow, reason: str):
        """Terminal state: exhausted retries or unrecoverable error."""
        try:
            await self.pool.execute(
                "UPDATE notification_deliveries SET status='dead_letter', "
                "error=$1, dead_letter_reason=$1, sent_at=NOW(), next_attempt_at=NULL WHERE id=$2",
                reason[:2000],
                r.delivery_id,
            )
            logger.warning(
                "dispatcher.dead_letter",
                id=r.delivery_id,
                channel=r.channel,
                event=r.notification.event_type,
                reason=reason[:200],
            )
        except Exception as e:
            logger.warning("mark.dead_letter.failed", id=r.delivery_id, error=str(e))
