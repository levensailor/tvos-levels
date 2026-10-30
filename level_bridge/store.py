"""Thread-safe level state shared by the input adapters and the dashboard publisher."""

from __future__ import annotations

import logging
import threading
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

from level_bridge.metrics import TrackMetrics
from level_bridge.models import (
    METRIC_FIELDS,
    DashboardSnapshot,
    LevelUpdate,
    Periods,
    SourceStatus,
    TrackSnapshot,
)
from level_bridge.settings import KNOWN_SOURCES
from level_bridge.timeutil import eastern_isoformat, now_epoch
from level_bridge.track_config import TrackLayout

logger = logging.getLogger(__name__)

METRIC_DECIMALS = 2
GAIN_DECIMALS = 4


class UnknownTrackError(ValueError):
    """Raised when a level update targets a track that is not in the layout."""

    def __init__(self, targets: list[str]) -> None:
        super().__init__(f"unknown track targets: {', '.join(targets)}")
        self.targets = targets


def _rounded(metric: str, value: float | None) -> float | None:
    if value is None:
        return None
    return round(value, GAIN_DECIMALS if metric == "gain" else METRIC_DECIMALS)


def _initial_status(name: str, enabled: frozenset[str]) -> SourceStatus:
    if name not in enabled:
        return SourceStatus(name=name, enabled=False, connected=False, detail="disabled")
    if name == "json":
        return SourceStatus(
            name=name, enabled=True, connected=True, detail="accepting POST /api/v1/levels"
        )
    return SourceStatus(name=name, enabled=True, connected=False, detail="starting")


@dataclass
class _TrackLevels:
    values: dict[str, float] = field(default_factory=dict)
    updated: dict[str, float] = field(default_factory=dict)


class LevelStore:
    def __init__(
        self, layout: TrackLayout, periods: Periods, enabled_sources: Iterable[str]
    ) -> None:
        self._lock = threading.Lock()
        self._layout = layout
        self._by_id = layout.by_id()
        self._by_slot = layout.by_slot()
        self._levels = {track.slot: _TrackLevels() for track in layout.tracks}
        self._periods = periods
        self._revision = 0
        enabled = frozenset(enabled_sources)
        self._sources = {name: _initial_status(name, enabled) for name in sorted(KNOWN_SOURCES)}

    @property
    def layout(self) -> TrackLayout:
        return self._layout

    def periods(self) -> Periods:
        with self._lock:
            return self._periods

    def set_periods(self, periods: Periods) -> Periods:
        with self._lock:
            self._periods = periods
            self._revision += 1
        logger.info("Periods updated: %s", periods.model_dump())
        return periods

    def source_enabled(self, name: str) -> bool:
        with self._lock:
            return self._sources[name].enabled

    def set_source_status(self, name: str, *, connected: bool, detail: str) -> None:
        with self._lock:
            current = self._sources[name]
            if current.connected == connected and current.detail == detail:
                return
            self._sources[name] = current.model_copy(
                update={"connected": connected, "detail": detail}
            )
            self._revision += 1

    def _set_metrics(self, slot: int, metrics: Mapping[str, float], timestamp: float) -> None:
        levels = self._levels[slot]
        for name, value in metrics.items():
            levels.values[name] = value
            levels.updated[name] = timestamp

    def apply_level_update(self, update: LevelUpdate, timestamp: float | None = None) -> int:
        """Apply a validated JSON update atomically. Unknown targets reject the whole update."""
        resolved: list[tuple[int, dict[str, float]]] = []
        unknown: list[str] = []
        for entry in update.tracks:
            if entry.track_id is not None:
                track = self._by_id.get(entry.track_id)
                label = f"track_id={entry.track_id}"
            else:
                track = self._by_slot.get(entry.slot)
                label = f"slot={entry.slot}"
            if track is None:
                unknown.append(label)
            else:
                resolved.append((track.slot, entry.metrics()))
        if unknown:
            raise UnknownTrackError(unknown)
        stamp = now_epoch() if timestamp is None else timestamp
        with self._lock:
            for slot, metrics in resolved:
                self._set_metrics(slot, metrics, stamp)
            self._revision += 1
        return len(resolved)

    def update_gains(self, gains: Mapping[int, float], timestamp: float | None = None) -> None:
        stamp = now_epoch() if timestamp is None else timestamp
        with self._lock:
            for slot, gain in gains.items():
                if slot in self._levels:
                    self._set_metrics(slot, {"gain": gain}, stamp)
            self._revision += 1

    def update_audio_metrics(
        self, metrics: Mapping[int, TrackMetrics], timestamp: float | None = None
    ) -> None:
        stamp = now_epoch() if timestamp is None else timestamp
        with self._lock:
            for slot, values in metrics.items():
                if slot in self._levels:
                    self._set_metrics(
                        slot, {"vu": values.vu, "dbfs": values.dbfs, "lufs": values.lufs}, stamp
                    )
            self._revision += 1

    def snapshot(self, now: float | None = None) -> DashboardSnapshot:
        current = now_epoch() if now is None else now
        with self._lock:
            stale_after = self._periods.stale_after_ms / 1000.0
            tracks: list[TrackSnapshot] = []
            for track in sorted(self._layout.tracks, key=lambda item: item.slot):
                levels = self._levels[track.slot]
                latest = max(levels.updated.values(), default=None)
                values = {
                    name: _rounded(name, levels.values.get(name)) for name in METRIC_FIELDS
                }
                tracks.append(
                    TrackSnapshot(
                        slot=track.slot,
                        track_id=track.id,
                        name=track.name,
                        updated_at=eastern_isoformat(latest) if latest is not None else None,
                        stale=latest is None or current - latest > stale_after,
                        **values,
                    )
                )
            return DashboardSnapshot(
                sequence=self._revision,
                generated_at=eastern_isoformat(current),
                periods=self._periods,
                sources=list(self._sources.values()),
                tracks=tracks,
            )
