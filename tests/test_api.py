from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from level_bridge.api import create_app
from level_bridge.models import DASHBOARD_SLOT_COUNT, SCHEMA_VERSION
from tests.helpers import make_settings

LEVELS = "/api/v1/levels"


def valid_update(**track: Any) -> dict[str, Any]:
    entry = {"track_id": "vox", "gain": 0.75, "vu": -2.5, "dbfs": -8.1, "lufs": -16.4}
    entry.update(track)
    return {"schema_version": SCHEMA_VERSION, "source": "test-rig", "tracks": [entry]}


def track(snapshot: dict[str, Any], slot: int) -> dict[str, Any]:
    return next(item for item in snapshot["tracks"] if item["slot"] == slot)


def test_health_and_config(client: TestClient) -> None:
    assert client.get("/health").json()["status"] == "ok"
    config = client.get("/api/v1/config").json()
    assert config["slot_count"] == DASHBOARD_SLOT_COUNT
    assert len(config["tracks"]) == 13
    assert config["tracks"][0] == {"slot": 1, "track_id": "vox", "name": "VOX"}


def test_snapshot_lists_configured_tracks_without_levels(client: TestClient) -> None:
    snapshot = client.get("/api/v1/snapshot").json()
    assert snapshot["schema_version"] == SCHEMA_VERSION
    assert snapshot["slot_count"] == 16
    assert [item["slot"] for item in snapshot["tracks"]] == list(range(1, 14))
    first = track(snapshot, 1)
    assert first["gain"] is None and first["stale"] is True and first["updated_at"] is None
    assert {source["name"] for source in snapshot["sources"]} == {"json", "logic", "blackhole"}


def test_valid_payload_updates_matching_track_box(client: TestClient) -> None:
    response = client.post(LEVELS, json=valid_update())
    assert response.status_code == 202
    assert response.json()["accepted"] == 1

    snapshot = client.get("/api/v1/snapshot").json()
    vox = track(snapshot, 1)
    assert (vox["gain"], vox["vu"], vox["dbfs"], vox["lufs"]) == (0.75, -2.5, -8.1, -16.4)
    assert vox["stale"] is False
    assert track(snapshot, 2)["gain"] is None


def test_slot_targeting_and_partial_metrics(client: TestClient) -> None:
    body = {"schema_version": 1, "source": "rig", "tracks": [{"slot": 13, "lufs": -20}]}
    assert client.post(LEVELS, json=body).status_code == 202
    overheads = track(client.get("/api/v1/snapshot").json(), 13)
    assert overheads["lufs"] == -20 and overheads["gain"] is None


@pytest.mark.parametrize(
    "body",
    [
        valid_update(gain=1.5),
        valid_update(gain="loud"),
        valid_update(gain=True),
        valid_update(dbfs=12),
        valid_update(track_id="VOX"),
        valid_update(extra_field=1),
        valid_update(slot=1),
        {"schema_version": 2, "source": "rig", "tracks": [{"track_id": "vox", "gain": 0.1}]},
        {"schema_version": 1, "source": "rig", "tracks": []},
        {"schema_version": 1, "source": "rig", "tracks": [{"track_id": "vox"}]},
        {
            "schema_version": 1,
            "source": "rig",
            "tracks": [{"track_id": "vox", "gain": 0.1}, {"track_id": "vox", "gain": 0.2}],
        },
    ],
)
def test_invalid_payloads_are_rejected_and_logged(
    client: TestClient, body: dict[str, Any], caplog: pytest.LogCaptureFixture
) -> None:
    before = client.get("/api/v1/snapshot").json()
    with caplog.at_level(logging.WARNING):
        response = client.post(LEVELS, json=body)
    assert response.status_code == 422
    assert "Rejected POST /api/v1/levels" in caplog.text
    assert client.get("/api/v1/snapshot").json()["tracks"] == before["tracks"]


def test_malformed_json_is_rejected_and_logged(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.WARNING):
        response = client.post(
            LEVELS,
            content=b'{"schema_version": 1, "tracks": [',
            headers={"content-type": "application/json"},
        )
    assert response.status_code == 422
    assert "Rejected POST /api/v1/levels" in caplog.text


def test_unknown_track_rejects_whole_update(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    body = valid_update()
    body["tracks"].append({"track_id": "theremin", "gain": 0.4})
    with caplog.at_level(logging.WARNING):
        response = client.post(LEVELS, json=body)
    assert response.status_code == 422
    assert "theremin" in caplog.text
    assert track(client.get("/api/v1/snapshot").json(), 1)["gain"] is None


def test_periods_can_be_tuned_and_are_validated(client: TestClient) -> None:
    periods = client.get("/api/v1/periods").json()
    periods["lufs_window_ms"] = 3000
    assert client.put("/api/v1/periods", json=periods).json()["lufs_window_ms"] == 3000
    assert client.get("/api/v1/snapshot").json()["periods"]["lufs_window_ms"] == 3000

    periods["publish_interval_ms"] = 10
    assert client.put("/api/v1/periods", json=periods).status_code == 422
    periods["publish_interval_ms"] = "100"
    assert client.put("/api/v1/periods", json=periods).status_code == 422


def test_websocket_streams_snapshots(client: TestClient) -> None:
    client.post(LEVELS, json=valid_update())
    with client.websocket_connect("/api/v1/stream") as websocket:
        message = websocket.receive_json()
    assert message["slot_count"] == 16
    assert track(message, 1)["gain"] == 0.75


def test_json_input_can_be_disabled(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    settings = make_settings(tmp_path, LEVEL_SOURCES="logic")
    test_client = TestClient(create_app(settings))
    with caplog.at_level(logging.WARNING):
        response = test_client.post(LEVELS, json=valid_update())
    assert response.status_code == 409
    assert "json source disabled" in caplog.text
