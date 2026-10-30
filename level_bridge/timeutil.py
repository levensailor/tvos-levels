"""Eastern-time helpers shared by logging and the dashboard contract."""

from __future__ import annotations

import time
from datetime import datetime
from zoneinfo import ZoneInfo

EASTERN_TIMEZONE_NAME = "America/New_York"
EASTERN = ZoneInfo(EASTERN_TIMEZONE_NAME)


def eastern_isoformat(epoch_seconds: float) -> str:
    """Return an ISO 8601 timestamp with milliseconds in America/New_York."""
    return datetime.fromtimestamp(epoch_seconds, EASTERN).isoformat(timespec="milliseconds")


def now_epoch() -> float:
    return time.time()
