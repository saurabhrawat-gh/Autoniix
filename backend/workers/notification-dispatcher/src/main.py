from __future__ import annotations

import asyncio
import signal

import asyncpg
import httpx
import structlog
import uvicorn
from fastapi import FastAPI

from .channels import default_channels
from .config import settings
from .dispatcher import Dispatcher

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging_level=20),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=False,
)

logger = structlog.get_logger()

app = FastAPI(title="Notification Dispatcher v2", version="0.1.0")

pool: asyncpg.Pool | None = None
http_client: httpx.AsyncClient | None = None
dispatcher: Dispatcher | None = None
dispatcher_task: asyncio.Task | None = None
stop_event: asyncio.Event | None = None


@app.on_event("startup")
async def startup():
    global pool, http_client, dispatcher, dispatcher_task, stop_event

    logger.info("notification-dispatcher.starting")

    pool = await asyncpg.create_pool(
        settings.database_url,
        min_size=2,
        max_size=10,
        command_timeout=30,
    )

    http_client = httpx.AsyncClient(
        timeout=httpx.Timeout(settings.http_timeout_ms / 1000.0),
        limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
    )

    channels = default_channels(http_client)
    dispatcher = Dispatcher(
        pool=pool,
        channels=channels,
        poll_interval_ms=settings.poll_interval_ms,
        stale_after_ms=settings.stale_after_ms,
        batch_size=settings.batch_size,
        max_attempts=settings.max_attempts,
        http_timeout_ms=settings.http_timeout_ms,
    )

    stop_event = asyncio.Event()
    dispatcher_task = asyncio.create_task(dispatcher.run(stop_event))

    logger.info("notification-dispatcher.started")


@app.on_event("shutdown")
async def shutdown():
    global pool, http_client, dispatcher_task, stop_event

    logger.info("notification-dispatcher.stopping")

    if stop_event:
        stop_event.set()

    if dispatcher_task:
        try:
            await asyncio.wait_for(dispatcher_task, timeout=5.0)
        except TimeoutError:
            logger.warning("dispatcher.task.timeout")
            dispatcher_task.cancel()

    if http_client:
        await http_client.aclose()

    if pool:
        await pool.close()

    logger.info("notification-dispatcher.stopped")


@app.get("/health")
async def health():
    return {"service": "notification-dispatcher-v2", "status": "ok"}


@app.get("/ready")
async def ready():
    if not pool:
        return {"ready": False, "reason": "pool_not_initialized"}
    try:
        await pool.fetchval("SELECT 1")
        return {"ready": True}
    except Exception as e:
        return {"ready": False, "reason": str(e)}


def main():
    host, port_str = settings.http_addr.rsplit(":", 1)
    port = int(port_str)

    def handle_signal(sig, frame):
        logger.info("signal.received", signal=sig)
        raise KeyboardInterrupt

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    uvicorn.run(
        app,
        host=host,
        port=port,
        log_config=None,
        access_log=False,
    )


if __name__ == "__main__":
    main()
