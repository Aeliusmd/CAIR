#!/usr/bin/env python3
"""CAIR2 background worker service.

Runs every N seconds, finds clinics with eligible outbox work,
and processes one batch per clinic using a shared worker pool.
"""

from __future__ import annotations

import logging
import time

from cair_integration.config import get_settings
from cair_integration.worker.coordinator import CairCoordinator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("cair_service")


def main() -> None:
    settings = get_settings()
    coordinator = CairCoordinator(settings)

    logger.info(
        "CAIR service started (batch=%s, workers=%s, interval=%ss)",
        settings.worker_batch_size,
        settings.worker_pool_size,
        settings.scheduler_interval_seconds,
    )

    while True:
        try:
            coordinator.run_once()
        except Exception:
            logger.exception("Coordinator run failed")

        time.sleep(settings.scheduler_interval_seconds)


if __name__ == "__main__":
    main()
