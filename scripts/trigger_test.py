"""Trigger a test VideoProductionWorkflow via Temporal.

Usage:
    python scripts/trigger_test.py
    python scripts/trigger_test.py --topic "Why your body shivers randomly"
"""
from __future__ import annotations

import argparse
import asyncio
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from temporalio.client import Client

from src.schemas.common import VideoParams


async def main(topic: str | None = None) -> None:
    # Connect to Temporal (use localhost since we're running outside Docker)
    host = os.getenv("TEMPORAL_HOST", "localhost:7233")
    namespace = os.getenv("TEMPORAL_NAMESPACE", "default")

    print(f"Connecting to Temporal at {host}...")
    client = await Client.connect(host, namespace=namespace)

    params = VideoParams(
        channel_id="BS001",
        content_mode="long_form",
        topic_candidates=[topic] if topic else [
            "Why your body shivers randomly",
            "5 signs your gut is unhealthy",
            "What happens when you hold your breath",
        ],
        max_cost_usd=2.50,
    )

    workflow_id = f"test-video-BS001-{asyncio.get_event_loop().time():.0f}"

    print(f"\nStarting workflow: {workflow_id}")
    print(f"  Channel: {params.channel_id}")
    print(f"  Topics:  {params.topic_candidates}")
    print(f"  Budget:  ${params.max_cost_usd}")
    print()

    handle = await client.start_workflow(
        "VideoProductionWorkflow",
        params,
        id=workflow_id,
        task_queue="video-production",
    )

    print(f"Workflow started! ID: {handle.id}")
    print(f"  View in Temporal UI: http://localhost:8080/namespaces/default/workflows/{handle.id}")
    print()
    print("Waiting for result...")

    try:
        result = await handle.result()
        print(f"\n{'='*50}")
        print(f"  RESULT: {result}")
        print(f"{'='*50}")
    except Exception as exc:
        print(f"\n  WORKFLOW FAILED: {exc}")

        # Query status
        try:
            status = await handle.query("get_status")
            print(f"  Last status: {status}")
        except Exception:
            pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Trigger a test video production workflow")
    parser.add_argument("--topic", type=str, help="Single topic to research")
    args = parser.parse_args()
    asyncio.run(main(args.topic))
