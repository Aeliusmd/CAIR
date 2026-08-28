"""Save HL7 messages to local files during dry-run (no DB writes)."""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def save_hl7_message(
    output_dir: str,
    clinic_name: str,
    submission_id: int,
    hl7_message: str,
) -> Path:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    safe_clinic = "".join(c if c.isalnum() or c in "-_" else "_" for c in clinic_name)
    path = out / f"{safe_clinic}_submission_{submission_id}.hl7"
    path.write_text(hl7_message, encoding="utf-8")
    logger.info("[DRY RUN] HL7 saved to %s", path)
    return path
