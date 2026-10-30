"""Logic Pro fader gain via the community Logic Pro MCP server (`logic://tracks`).

Logic Pro MCP reads the track-header volume fader through macOS Accessibility and publishes it
as a normalized 0...1 fader contract. It is a separately installed community project, not a
first-party Apple API.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, ValidationError

from level_bridge.models import GainValue
from level_bridge.settings import Settings
from level_bridge.store import LevelStore
from level_bridge.track_config import TrackLayout

logger = logging.getLogger(__name__)

SOURCE_NAME = "logic"
INITIAL_BACKOFF_SECONDS = 1.0
MAX_BACKOFF_SECONDS = 30.0
LIVE_SOURCE = "ax_live"


class LogicPayloadError(ValueError):
    """Raised when the `logic://tracks` resource cannot be trusted."""


class _LogicTrackRow(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: Annotated[StrictInt, Field(ge=0)]
    name: str
    volume: GainValue
    placeholder: StrictBool | None = None


@dataclass(frozen=True)
class LogicTrackReading:
    index: int
    name: str
    volume: float


def parse_logic_tracks_envelope(text: str) -> list[LogicTrackReading]:
    """Validate a Logic Pro MCP `logic://tracks` envelope and return its live rows."""
    try:
        envelope = json.loads(text)
    except json.JSONDecodeError as exc:
        raise LogicPayloadError(f"resource is not JSON: {exc}") from exc
    if not isinstance(envelope, dict):
        raise LogicPayloadError("resource envelope must be a JSON object")
    source = envelope.get("source")
    if envelope.get("readable") is False or (source is not None and source != LIVE_SOURCE):
        raise LogicPayloadError(
            f"track rows were not read live (source={source!r}, reason={envelope.get('reason')!r})"
        )
    rows = envelope.get("data")
    if not isinstance(rows, list):
        raise LogicPayloadError("resource envelope has no data array")

    readings: list[LogicTrackReading] = []
    for position, row in enumerate(rows):
        try:
            parsed = _LogicTrackRow.model_validate(row)
        except ValidationError as exc:
            reasons = exc.errors(include_url=False)
            logger.warning("Rejected Logic track row %d: %s", position, reasons)
            continue
        if parsed.placeholder:
            continue
        readings.append(LogicTrackReading(index=parsed.id, name=parsed.name, volume=parsed.volume))
    return readings


def match_gains(readings: Sequence[LogicTrackReading], layout: TrackLayout) -> dict[int, float]:
    """Map Logic rows onto layout slots by configured track name, then by configured index."""
    by_name: dict[str, list[LogicTrackReading]] = {}
    for reading in readings:
        by_name.setdefault(reading.name.strip().casefold(), []).append(reading)
    by_index = {reading.index: reading for reading in readings}

    gains: dict[int, float] = {}
    for track in layout.tracks:
        match: LogicTrackReading | None = None
        if track.logic_track_name is not None:
            candidates = by_name.get(track.logic_track_name.strip().casefold(), [])
            if len(candidates) == 1:
                match = candidates[0]
            elif len(candidates) > 1:
                logger.warning(
                    "Logic track name %r is ambiguous (%d rows); slot %d skipped",
                    track.logic_track_name,
                    len(candidates),
                    track.slot,
                )
                continue
        if match is None and track.logic_track_index is not None:
            match = by_index.get(track.logic_track_index)
        if match is not None:
            gains[track.slot] = match.volume
    return gains


def resource_text(result: Any) -> str:
    for content in getattr(result, "contents", []) or []:
        text = getattr(content, "text", None)
        if isinstance(text, str):
            return text
    raise LogicPayloadError("resource response contained no text content")


class LogicGainSource:
    def __init__(self, settings: Settings, store: LevelStore) -> None:
        self._settings = settings
        self._store = store

    async def run(self) -> None:
        backoff = INITIAL_BACKOFF_SECONDS
        while True:
            try:
                await self._poll_session()
                backoff = INITIAL_BACKOFF_SECONDS
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 - any adapter failure must trigger reconnect
                logger.warning("Logic Pro MCP session ended: %s", exc)
                self._store.set_source_status(SOURCE_NAME, connected=False, detail=str(exc)[:200])
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, MAX_BACKOFF_SECONDS)

    async def _poll_session(self) -> None:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        params = StdioServerParameters(
            command=self._settings.logic_mcp_command,
            args=list(self._settings.logic_mcp_args),
            env={"LOGIC_PRO_BUNDLE_ID": self._settings.logic_pro_bundle_id},
        )
        # mcp>=2 types ReadResourceRequestParams.uri as str; a pydantic AnyUrl fails validation.
        uri = self._settings.logic_tracks_resource_uri
        logger.info("Starting Logic Pro MCP: %s", self._settings.logic_mcp_command)
        async with stdio_client(params) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                self._store.set_source_status(SOURCE_NAME, connected=True, detail="session ready")
                logger.info("Logic Pro MCP session ready")
                while True:
                    self._poll_once(resource_text(await session.read_resource(uri)))
                    await asyncio.sleep(self._store.periods().logic_poll_ms / 1000.0)

    def _poll_once(self, text: str) -> None:
        try:
            readings = parse_logic_tracks_envelope(text)
        except LogicPayloadError as exc:
            logger.warning("Rejected Logic tracks resource: %s", exc)
            self._store.set_source_status(SOURCE_NAME, connected=True, detail=str(exc)[:200])
            return
        gains = match_gains(readings, self._store.layout)
        self._store.update_gains(gains)
        self._store.set_source_status(
            SOURCE_NAME, connected=True, detail=f"{len(gains)} tracks matched"
        )
