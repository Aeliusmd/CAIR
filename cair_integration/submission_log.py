"""Structured submission status logging to a dedicated log file."""

from __future__ import annotations

import logging
from typing import Any, Optional

LOGGER_NAME = "cair.submissions"


def log_submission_event(
    status: str,
    *,
    submission_id: int,
    vaccine_id: Optional[int] = None,
    checkin_id: Optional[int] = None,
    clinic_id: Optional[int] = None,
    clinic_name: str = "",
    attempt: Optional[int] = None,
    ack_code: str = "",
    error: str = "",
    **extra: Any,
) -> None:
    """Write one line to cair_submissions.log.

    status: QUEUED | PROCESSING | SUCCESS | FAILED | RETRY
    """
    parts = [f"STATUS={status.upper()}", f"submission_id={submission_id}"]
    if vaccine_id is not None:
        parts.append(f"vaccine_id={vaccine_id}")
    if checkin_id is not None:
        parts.append(f"checkin_id={checkin_id}")
    if clinic_id is not None:
        parts.append(f"clinic_id={clinic_id}")
    if clinic_name:
        parts.append(f"clinic={clinic_name}")
    if attempt is not None:
        parts.append(f"attempt={attempt}")
    if ack_code:
        parts.append(f"ack={ack_code}")
    if error:
        parts.append(f"error={error[:500]}")
    for key, value in extra.items():
        if value is not None and value != "":
            parts.append(f"{key}={value}")

    logging.getLogger(LOGGER_NAME).info(" | ".join(parts))
