"""Retry scheduling for failed CAIR submissions."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone


def calculate_next_retry(attempt_count: int) -> datetime:
    """Exponential backoff: 5, 15, 30, 60, 120 minutes."""
    delays_minutes = [5, 15, 30, 60, 120]
    index = min(attempt_count - 1, len(delays_minutes) - 1)
    delay = delays_minutes[max(index, 0)]
    return datetime.now(timezone.utc) + timedelta(minutes=delay)
