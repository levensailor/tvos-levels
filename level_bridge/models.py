"""Versioned bridge contracts shared by the JSON input, sources, and tvOS dashboard."""

from __future__ import annotations

import math
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StrictBool,
    StrictInt,
    model_validator,
)

SCHEMA_VERSION = 1
DASHBOARD_SLOT_COUNT = 16
DASHBOARD_SLOTS_PER_ROW = 8
TRACK_ID_PATTERN = r"^[a-z0-9][a-z0-9_-]{0,31}$"
SOURCE_NAME_PATTERN = r"^[A-Za-z0-9_.-]{1,64}$"
TRACK_NAME_MAX_LENGTH = 32

METRIC_FIELDS = ("gain", "vu", "dbfs", "lufs")
METRIC_DB_MIN = -200.0
GAIN_MIN = 0.0
GAIN_MAX = 1.0
VU_MAX = 30.0
DBFS_MAX = 6.0
LUFS_MAX = 6.0

DBFS_PEAK_WINDOW_LIMITS_MS = (50, 10_000)
VU_INTEGRATION_LIMITS_MS = (50, 10_000)
LUFS_WINDOW_LIMITS_MS = (100, 10_000)
LOGIC_POLL_LIMITS_MS = (250, 60_000)
PUBLISH_INTERVAL_LIMITS_MS = (50, 5_000)
STALE_AFTER_LIMITS_MS = (500, 600_000)


def _require_json_number(value: object) -> object:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError("must be a JSON number")
    if not math.isfinite(value):
        raise ValueError("must be a finite number")
    return value


JsonNumber = Annotated[float, BeforeValidator(_require_json_number)]
GainValue = Annotated[JsonNumber, Field(ge=GAIN_MIN, le=GAIN_MAX)]
VuValue = Annotated[JsonNumber, Field(ge=METRIC_DB_MIN, le=VU_MAX)]
DbfsValue = Annotated[JsonNumber, Field(ge=METRIC_DB_MIN, le=DBFS_MAX)]
LufsValue = Annotated[JsonNumber, Field(ge=METRIC_DB_MIN, le=LUFS_MAX)]
TrackId = Annotated[str, Field(pattern=TRACK_ID_PATTERN)]
SlotNumber = Annotated[StrictInt, Field(ge=1, le=DASHBOARD_SLOT_COUNT)]


def _period(limits: tuple[int, int]) -> object:
    return Field(ge=limits[0], le=limits[1])


class Periods(BaseModel):
    """Measurement and publication periods, in milliseconds."""

    model_config = ConfigDict(extra="forbid")

    dbfs_peak_window_ms: Annotated[StrictInt, _period(DBFS_PEAK_WINDOW_LIMITS_MS)]
    vu_integration_ms: Annotated[StrictInt, _period(VU_INTEGRATION_LIMITS_MS)]
    lufs_window_ms: Annotated[StrictInt, _period(LUFS_WINDOW_LIMITS_MS)]
    logic_poll_ms: Annotated[StrictInt, _period(LOGIC_POLL_LIMITS_MS)]
    publish_interval_ms: Annotated[StrictInt, _period(PUBLISH_INTERVAL_LIMITS_MS)]
    stale_after_ms: Annotated[StrictInt, _period(STALE_AFTER_LIMITS_MS)]


class TrackLevelInput(BaseModel):
    """One track's levels from the JSON input adapter."""

    model_config = ConfigDict(extra="forbid")

    track_id: TrackId | None = None
    slot: SlotNumber | None = None
    gain: GainValue | None = None
    vu: VuValue | None = None
    dbfs: DbfsValue | None = None
    lufs: LufsValue | None = None

    @model_validator(mode="after")
    def _require_target_and_metric(self) -> TrackLevelInput:
        if (self.track_id is None) == (self.slot is None):
            raise ValueError("provide exactly one of track_id or slot")
        if all(getattr(self, name) is None for name in METRIC_FIELDS):
            raise ValueError(f"provide at least one metric: {', '.join(METRIC_FIELDS)}")
        return self

    def metrics(self) -> dict[str, float]:
        values = {name: getattr(self, name) for name in METRIC_FIELDS}
        return {name: value for name, value in values.items() if value is not None}


class LevelUpdate(BaseModel):
    """Body of POST /api/v1/levels."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1]
    source: Annotated[str, Field(pattern=SOURCE_NAME_PATTERN)]
    tracks: Annotated[list[TrackLevelInput], Field(min_length=1, max_length=DASHBOARD_SLOT_COUNT)]

    @model_validator(mode="after")
    def _reject_duplicate_targets(self) -> LevelUpdate:
        seen: set[str] = set()
        for track in self.tracks:
            key = f"id:{track.track_id}" if track.track_id is not None else f"slot:{track.slot}"
            if key in seen:
                raise ValueError(f"duplicate track target {key}")
            seen.add(key)
        return self


class SourceStatus(BaseModel):
    name: str
    enabled: StrictBool
    connected: StrictBool
    detail: str


class TrackSnapshot(BaseModel):
    slot: int
    track_id: str
    name: str
    gain: float | None
    vu: float | None
    dbfs: float | None
    lufs: float | None
    updated_at: str | None
    stale: bool


class DashboardSnapshot(BaseModel):
    schema_version: int = SCHEMA_VERSION
    sequence: int
    generated_at: str
    slot_count: int = DASHBOARD_SLOT_COUNT
    periods: Periods
    sources: list[SourceStatus]
    tracks: list[TrackSnapshot]
