"""Track layout configuration: slot positions, names, and source mappings."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StrictInt, ValidationError, model_validator

from level_bridge.models import DASHBOARD_SLOT_COUNT, TRACK_NAME_MAX_LENGTH, SlotNumber, TrackId

logger = logging.getLogger(__name__)

MAX_AUDIO_CHANNEL = 256
MAX_CHANNELS_PER_TRACK = 2


class TrackLayoutError(ValueError):
    """Raised when the track layout file is missing or invalid."""


class TrackConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slot: SlotNumber
    id: TrackId
    name: Annotated[str, Field(min_length=1, max_length=TRACK_NAME_MAX_LENGTH)]
    logic_track_name: Annotated[str, Field(min_length=1)] | None = None
    logic_track_index: Annotated[StrictInt, Field(ge=0)] | None = None
    audio_channels: Annotated[
        list[Annotated[StrictInt, Field(ge=1, le=MAX_AUDIO_CHANNEL)]],
        Field(max_length=MAX_CHANNELS_PER_TRACK),
    ] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_channels(self) -> TrackConfig:
        if not self.name.strip():
            raise ValueError("name must not be blank")
        if len(set(self.audio_channels)) != len(self.audio_channels):
            raise ValueError("audio_channels must not repeat a channel")
        return self


class TrackLayout(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tracks: Annotated[list[TrackConfig], Field(min_length=1, max_length=DASHBOARD_SLOT_COUNT)]

    @model_validator(mode="after")
    def _check_unique(self) -> TrackLayout:
        slots = [track.slot for track in self.tracks]
        ids = [track.id for track in self.tracks]
        logic_names = [
            track.logic_track_name.strip().casefold()
            for track in self.tracks
            if track.logic_track_name is not None
        ]
        if len(set(slots)) != len(slots):
            raise ValueError("track slots must be unique")
        if len(set(ids)) != len(ids):
            raise ValueError("track ids must be unique")
        if len(set(logic_names)) != len(logic_names):
            raise ValueError("logic_track_name values must be unique")
        return self

    def by_id(self) -> dict[str, TrackConfig]:
        return {track.id: track for track in self.tracks}

    def by_slot(self) -> dict[int, TrackConfig]:
        return {track.slot: track for track in self.tracks}

    def audio_channel_map(self) -> dict[int, tuple[int, ...]]:
        """Map slot to 1-based input channels for tracks routed through the audio device."""
        return {
            track.slot: tuple(track.audio_channels)
            for track in self.tracks
            if track.audio_channels
        }

    def required_input_channels(self) -> int:
        channels = [channel for track in self.tracks for channel in track.audio_channels]
        return max(channels, default=0)


def parse_track_layout(raw: str) -> TrackLayout:
    try:
        return TrackLayout.model_validate_json(raw)
    except ValidationError as exc:
        raise TrackLayoutError(f"invalid track layout: {exc}") from exc


def load_track_layout(path: Path, fallback: Path) -> TrackLayout:
    """Load the configured layout, falling back to the committed example layout."""
    source = path
    if not path.is_file():
        logger.warning("Track layout %s not found; using example layout %s", path, fallback)
        source = fallback
    if not source.is_file():
        raise TrackLayoutError(f"track layout file not found: {source}")
    try:
        raw = source.read_text(encoding="utf-8")
        json.loads(raw)
    except (OSError, json.JSONDecodeError) as exc:
        raise TrackLayoutError(f"cannot read track layout {source}: {exc}") from exc
    layout = parse_track_layout(raw)
    logger.info("Loaded %d tracks from %s", len(layout.tracks), source)
    return layout
