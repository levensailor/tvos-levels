from __future__ import annotations

import json
import logging

import pytest

from level_bridge.settings import PROJECT_ROOT
from level_bridge.sources.logic_mcp import (
    LogicPayloadError,
    match_gains,
    parse_logic_tracks_envelope,
)
from level_bridge.track_config import load_track_layout

EXAMPLE = PROJECT_ROOT / "config" / "tracks.example.json"


def envelope(rows: list[dict[str, object]], **extras: object) -> str:
    body: dict[str, object] = {
        "cache_age_sec": 0.2,
        "fetched_at": "2026-10-30T14:40:00Z",
        "ax_occluded": False,
        "complete": False,
        "readable": True,
        "source": "ax_live",
        "data": rows,
    }
    body.update(extras)
    return json.dumps(body)


def row(index: int, name: str, volume: object) -> dict[str, object]:
    return {
        "id": index,
        "name": name,
        "type": "audio",
        "isSelected": False,
        "volume": volume,
        "pan": 0.0,
        "automationMode": "off",
    }


def test_parses_live_rows_and_matches_by_configured_name() -> None:
    layout = load_track_layout(EXAMPLE, EXAMPLE)
    text = envelope([row(0, "VOX", 0.72), row(1, "guitar 1", 0.5), row(2, "Click", 0.9)])
    gains = match_gains(parse_logic_tracks_envelope(text), layout)
    assert gains == {1: 0.72, 4: 0.5}


def test_invalid_rows_are_rejected_and_logged(caplog: pytest.LogCaptureFixture) -> None:
    text = envelope([row(0, "VOX", 1.4), row(1, "BASS", "loud"), row(2, "KEYS", 0.3)])
    with caplog.at_level(logging.WARNING):
        readings = parse_logic_tracks_envelope(text)
    assert [reading.name for reading in readings] == ["KEYS"]
    assert caplog.text.count("Rejected Logic track row") == 2


def test_placeholder_rows_are_ignored() -> None:
    placeholder = row(0, "Track 1", 0.0) | {"placeholder": True}
    assert parse_logic_tracks_envelope(envelope([placeholder])) == []


@pytest.mark.parametrize(
    "text",
    [
        "not json",
        json.dumps([1, 2]),
        envelope([], readable=False, source="project_file"),
        envelope([], source="cache"),
        json.dumps({"source": "ax_live"}),
    ],
)
def test_untrusted_envelopes_raise(text: str) -> None:
    with pytest.raises(LogicPayloadError):
        parse_logic_tracks_envelope(text)


def test_ambiguous_names_are_skipped() -> None:
    layout = load_track_layout(EXAMPLE, EXAMPLE)
    text = envelope([row(0, "VOX", 0.2), row(5, "VOX", 0.4)])
    assert match_gains(parse_logic_tracks_envelope(text), layout) == {}
