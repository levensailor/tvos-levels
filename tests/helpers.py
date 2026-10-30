from __future__ import annotations

from pathlib import Path

from level_bridge.settings import PROJECT_ROOT, Settings

EXAMPLE_LAYOUT = PROJECT_ROOT / "config" / "tracks.example.json"


def make_settings(tmp_path: Path, **overrides: str) -> Settings:
    env = {
        "TRACKS_CONFIG_PATH": str(tmp_path / "missing-tracks.json"),
        "TRACKS_EXAMPLE_PATH": str(EXAMPLE_LAYOUT),
        "LEVEL_SOURCES": "json",
    }
    env.update(overrides)
    return Settings.from_env(env)
