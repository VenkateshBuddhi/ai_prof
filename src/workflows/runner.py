# src/workflows/runner.py
"""Standalone workflow runner — polls Medplum for due Tasks and executes them.

Run:
    uv run python -m src.workflows.runner --once     # single pass (testing)
    uv run python -m src.workflows.runner            # poll forever

Environment:
    MEDPLUM_CLIENT_ID / MEDPLUM_CLIENT_SECRET     (required)
    WORKFLOW_POLL_SECONDS   poll interval, default 30
    REMINDER_LEAD_MINUTES   see engine.py (default 1440)
    NOTIFY_CHANNELS         see notifications.py (default "record")
"""
from __future__ import annotations

import argparse
import asyncio
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ENV_PATH = os.path.join(BASE_DIR, ".env")


def _load_env() -> None:
    if not os.path.exists(ENV_PATH):
        return
    with open(ENV_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            os.environ.setdefault(key.strip(), val.strip().strip("'").strip('"'))


async def _run(once: bool) -> None:
    import logging
    from src.database.medplum_client import get_medplum_client
    from src.workflows import engine

    logger = logging.getLogger("WorkflowRunner")
    if not get_medplum_client():
        print("Medplum not configured (set MEDPLUM_CLIENT_ID/SECRET). Aborting.")
        return

    interval = int(os.environ.get("WORKFLOW_POLL_SECONDS", "30"))
    logger.info("Workflow runner started (interval=%ss, once=%s)", interval, once)
    while True:
        counts = await engine.process_due_tasks()
        if counts.get("due"):
            logger.info("processed due tasks: %s", counts)
        if once:
            print(f"single pass complete: {counts}")
            return
        await asyncio.sleep(interval)


def main() -> None:
    parser = argparse.ArgumentParser(description="Workflow runner (executes due reminder/notification Tasks)")
    parser.add_argument("--once", action="store_true", help="Run a single pass and exit")
    args = parser.parse_args()
    _load_env()
    from src.logging_setup import setup_logging
    setup_logging()
    asyncio.run(_run(args.once))


if __name__ == "__main__":
    main()
