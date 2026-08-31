#!/usr/bin/env python3
"""Run one CAIR cycle in dry-run mode (read DB, build HL7, no writes).

Safe to run now — does NOT insert, update, or delete anything in the database.
Does NOT send to CAIR unless SEND_TO_CAIR=true and DRY_RUN=false.
"""

from __future__ import annotations

import logging
import sys

from cair_integration.config import get_settings
from cair_integration.logging_setup import setup_logging
from cair_integration.worker.coordinator import CairCoordinator

logger = logging.getLogger("cair_dry_run")


def main() -> int:
    settings = get_settings()
    log_path = setup_logging(settings.log_dir)

    if not settings.clinic_db_connection and not settings.master_db_connection:
        logger.error("Database not configured. Set CLINIC_DB_* (dev) or MASTER_DB_* (qa) in .env")
        return 1

    logger.info("=" * 60)
    logger.info("CAIR dry-run — single cycle")
    logger.info("Log dir: %s", log_path)
    logger.info("Submission log: %s", log_path / "cair_submissions.log")
    logger.info("=" * 60)

    coordinator = CairCoordinator(settings)
    coordinator.run_once()

    logger.info("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
