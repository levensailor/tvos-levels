"""Environment-driven bridge settings. Values come from the process environment and `.env`."""

from __future__ import annotations

import os
import shlex
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from level_bridge.models import Periods

PROJECT_ROOT = Path(__file__).resolve().parents[1]
KNOWN_SOURCES = frozenset({"json", "logic", "blackhole"})

DEFAULTS: dict[str, str] = {
    "TRACKS_CONFIG_PATH": "config/tracks.json",
    "TRACKS_EXAMPLE_PATH": "config/tracks.example.json",
    "LEVEL_SOURCES": "json",
    "BLACKHOLE_DEVICE_NAME": "BlackHole 16ch",
    "AUDIO_SAMPLE_RATE": "48000",
    "AUDIO_BLOCK_SIZE": "1024",
    "METRIC_FLOOR_DB": "-96",
    "VU_REFERENCE_DBFS": "-18",
    "DBFS_PEAK_WINDOW_MS": "300",
    "VU_INTEGRATION_MS": "300",
    "LUFS_WINDOW_MS": "400",
    "LOGIC_POLL_MS": "1000",
    "PUBLISH_INTERVAL_MS": "100",
    "STALE_AFTER_MS": "3000",
    "LOGIC_MCP_COMMAND": "LogicProMCP",
    "LOGIC_MCP_ARGS": "",
    "LOGIC_PRO_BUNDLE_ID": "com.apple.logic10",
    "LOGIC_TRACKS_RESOURCE_URI": "logic://tracks",
}


class SettingsError(ValueError):
    """Raised when an environment value is missing or out of range."""


def _value(env: Mapping[str, str], key: str) -> str:
    raw = env.get(key)
    return raw.strip() if raw is not None and raw.strip() else DEFAULTS[key]


def _int(env: Mapping[str, str], key: str, minimum: int, maximum: int) -> int:
    raw = _value(env, key)
    try:
        value = int(raw)
    except ValueError as exc:
        raise SettingsError(f"{key} must be an integer, got {raw!r}") from exc
    if not minimum <= value <= maximum:
        raise SettingsError(f"{key} must be between {minimum} and {maximum}, got {value}")
    return value


def _float(env: Mapping[str, str], key: str, minimum: float, maximum: float) -> float:
    raw = _value(env, key)
    try:
        value = float(raw)
    except ValueError as exc:
        raise SettingsError(f"{key} must be a number, got {raw!r}") from exc
    if not minimum <= value <= maximum:
        raise SettingsError(f"{key} must be between {minimum} and {maximum}, got {value}")
    return value


def _path(env: Mapping[str, str], key: str, root: Path) -> Path:
    path = Path(_value(env, key)).expanduser()
    return path if path.is_absolute() else root / path


@dataclass(frozen=True)
class Settings:
    tracks_config_path: Path
    tracks_example_path: Path
    level_sources: frozenset[str]
    blackhole_device_name: str
    audio_sample_rate: int
    audio_block_size: int
    metric_floor_db: float
    vu_reference_dbfs: float
    logic_mcp_command: str
    logic_mcp_args: tuple[str, ...]
    logic_pro_bundle_id: str
    logic_tracks_resource_uri: str
    initial_periods: Periods

    @classmethod
    def from_env(
        cls, environ: Mapping[str, str] | None = None, project_root: Path = PROJECT_ROOT
    ) -> Settings:
        env = os.environ if environ is None else environ

        sources = frozenset(
            part.strip().lower() for part in _value(env, "LEVEL_SOURCES").split(",") if part.strip()
        )
        unknown = sources - KNOWN_SOURCES
        if unknown or not sources:
            raise SettingsError(
                f"LEVEL_SOURCES must list one or more of {sorted(KNOWN_SOURCES)}, "
                f"got {sorted(unknown) or 'nothing'}"
            )

        try:
            periods = Periods(
                dbfs_peak_window_ms=_int(env, "DBFS_PEAK_WINDOW_MS", 1, 1_000_000),
                vu_integration_ms=_int(env, "VU_INTEGRATION_MS", 1, 1_000_000),
                lufs_window_ms=_int(env, "LUFS_WINDOW_MS", 1, 1_000_000),
                logic_poll_ms=_int(env, "LOGIC_POLL_MS", 1, 1_000_000),
                publish_interval_ms=_int(env, "PUBLISH_INTERVAL_MS", 1, 1_000_000),
                stale_after_ms=_int(env, "STALE_AFTER_MS", 1, 1_000_000),
            )
        except ValidationError as exc:
            raise SettingsError(f"invalid period settings: {exc}") from exc

        try:
            mcp_args = tuple(shlex.split(_value(env, "LOGIC_MCP_ARGS")))
        except ValueError as exc:
            raise SettingsError(f"LOGIC_MCP_ARGS is not valid shell syntax: {exc}") from exc

        return cls(
            tracks_config_path=_path(env, "TRACKS_CONFIG_PATH", project_root),
            tracks_example_path=_path(env, "TRACKS_EXAMPLE_PATH", project_root),
            level_sources=sources,
            blackhole_device_name=_value(env, "BLACKHOLE_DEVICE_NAME"),
            audio_sample_rate=_int(env, "AUDIO_SAMPLE_RATE", 8_000, 768_000),
            audio_block_size=_int(env, "AUDIO_BLOCK_SIZE", 64, 16_384),
            metric_floor_db=_float(env, "METRIC_FLOOR_DB", -200.0, -20.0),
            vu_reference_dbfs=_float(env, "VU_REFERENCE_DBFS", -40.0, 0.0),
            logic_mcp_command=_value(env, "LOGIC_MCP_COMMAND"),
            logic_mcp_args=mcp_args,
            logic_pro_bundle_id=_value(env, "LOGIC_PRO_BUNDLE_ID"),
            logic_tracks_resource_uri=_value(env, "LOGIC_TRACKS_RESOURCE_URI"),
            initial_periods=periods,
        )
