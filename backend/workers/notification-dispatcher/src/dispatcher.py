from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from typing import Any

import asyncpg
import structlog

from .channels import Channel, NotificationPayload

logger = structlog.get_logger()


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
        stale_cutoff = datetime.now(UTC) - self.stale_after

        async with self.pool.acquire() as conn:
            async with conn.transaction():
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
                          OR (d.status = 'failed' AND d.attempts < $2 AND d.created_at < $1)
                           )
                     ORDER BY d.created_at ASC
                     LIMIT $3
                     FOR UPDATE OF d SKIP LOCKED
                """
                pg_rows = await conn.fetch(query, stale_cutoff, self.max_attempts, self.batch_size)

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
            await self._mark_failed(r.delivery_id, f"unknown channel {r.channel!r}")
            return

        try:
            resp = await asyncio.wait_for(
                ch.send(r.notification, r.config),
                timeout=self.http_timeout.total_seconds(),
            )
            await self._mark_sent(r.delivery_id, resp)
        except Exception as e:
            await self._mark_failed(r.delivery_id, str(e))

    async def _mark_sent(self, delivery_id: int, resp: dict[str, Any]):
        try:
            await self.pool.execute(
                "UPDATE notification_deliveries SET status='sent', response=$1::jsonb, sent_at=NOW() WHERE id=$2",
                json.dumps(resp),
                delivery_id,
            )
        except Exception as e:
            logger.warning("mark.sent.failed", id=delivery_id, error=str(e))

    async def _mark_failed(self, delivery_id: int, err_msg: str):
        try:
            await self.pool.execute(
                "UPDATE notification_deliveries SET status='failed', error=$1, sent_at=NOW() WHERE id=$2",
                err_msg,
                delivery_id,
            )
        except Exception as e:
            logger.warning("mark.failed.failed", id=delivery_id, error=str(e))
