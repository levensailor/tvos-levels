from __future__ import annotations

from pathlib import Path

import pytest

from level_bridge.env_export import startup_exports
from level_bridge.settings import Settings, SettingsError
from level_bridge.track_config import TrackLayoutError, parse_track_layout


def test_defaults_and_overrides(tmp_path: Path) -> None:
    settings = Settings.from_env({}, project_root=tmp_path)
    assert settings.level_sources == frozenset({"json"})
    assert settings.tracks_config_path == tmp_path / "config" / "tracks.json"
    assert settings.initial_periods.vu_integration_ms == 300

    env = {
        "LEVEL_SOURCES": "json, Logic",
        "LUFS_WINDOW_MS": "3000",
        "LOGIC_MCP_ARGS": "--flag 'a b'",
    }
    custom = Settings.from_env(env, project_root=tmp_path)
    assert custom.level_sources == frozenset({"json", "logic"})
    assert custom.initial_periods.lufs_window_ms == 3000
    assert custom.logic_mcp_args == ("--flag", "a b")


@pytest.mark.parametrize(
    "env",
    [
        {"LEVEL_SOURCES": "json,midi"},
        {"AUDIO_SAMPLE_RATE": "fast"},
        {"PUBLISH_INTERVAL_MS": "5"},
        {"METRIC_FLOOR_DB": "0"},
    ],
)
def test_invalid_settings_raise(env: dict[str, str], tmp_path: Path) -> None:
    with pytest.raises(SettingsError):
        Settings.from_env(env, project_root=tmp_path)


def test_port_comes_from_env_file_unless_already_set(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("PORT=8123\nUVICORN_HOST=0.0.0.0\n", encoding="utf-8")
    assert startup_exports(env_file, {}) == {"PORT": "8123", "UVICORN_HOST": "0.0.0.0"}
    assert startup_exports(env_file, {"PORT": "9000"}) == {"UVICORN_HOST": "0.0.0.0"}
    assert startup_exports(tmp_path / "absent.env", {}) == {}


def test_invalid_port_is_rejected(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("PORT=eighty\n", encoding="utf-8")
    with pytest.raises(ValueError):
        startup_exports(env_file, {})


@pytest.mark.parametrize(
    "raw",
    [
        '{"tracks": []}',
        '{"tracks": [{"slot": 17, "id": "vox", "name": "VOX"}]}',
        '{"tracks": [{"slot": 1, "id": "vox", "name": "VOX"}, '
        '{"slot": 1, "id": "b", "name": "B"}]}',
        '{"tracks": [{"slot": 1, "id": "vox", "name": " "}]}',
        '{"tracks": [{"slot": 1, "id": "vox", "name": "VOX", "audio_channels": [1, 1]}]}',
    ],
)
def test_invalid_layouts_raise(raw: str) -> None:
    with pytest.raises(TrackLayoutError):
        parse_track_layout(raw)
