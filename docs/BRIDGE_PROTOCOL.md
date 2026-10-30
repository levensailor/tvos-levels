# Bridge protocol (schema version 1)

The bridge is a FastAPI service on the Mac that runs Logic Pro. The Apple TV reads it over the local network. No endpoint requires authentication.

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Liveness: `{"status": "ok", "version": "0.1.0"}` |
| `GET` | `/api/v1/config` | Slot layout, periods, and source status |
| `GET` | `/api/v1/snapshot` | Current dashboard snapshot |
| `WS` | `/api/v1/stream` | Snapshot pushed every `publish_interval_ms` |
| `POST` | `/api/v1/levels` | JSON input adapter (manual or scripted levels) |
| `GET` / `PUT` | `/api/v1/periods` | Read or tune measurement and update periods |

The Swift contract lives in [`BandLevels/BandLevels/Models/BridgeContract.swift`](../BandLevels/BandLevels/Models/BridgeContract.swift) and the Python contract in [`level_bridge/models.py`](../level_bridge/models.py). Both enforce the same ranges.

## Metrics

| Field | Meaning | Unit and range | Source |
| --- | --- | --- | --- |
| `gain` | Logic track-header fader position | normalized `0.0`–`1.0` (shown as %) | Logic Pro MCP `logic://tracks` `volume`, or JSON input |
| `vu` | Sine-calibrated RMS level relative to `VU_REFERENCE_DBFS` over `vu_integration_ms` | VU, `-200`–`+30` | BlackHole, or JSON input |
| `dbfs` | Sample peak over `dbfs_peak_window_ms` | dBFS, `-200`–`+6` | BlackHole, or JSON input |
| `lufs` | ITU-R BS.1770 K-weighted loudness over `lufs_window_ms` (400 ms = momentary) | LUFS, `-200`–`+6` | BlackHole, or JSON input |

`gain` is a fader position, not decibels. Logic Pro MCP maps the fader through Logic's own taper, so `0.8` is not a fixed dB value.

Silence is reported as `METRIC_FLOOR_DB` (default `-96`), never as negative infinity.

## Snapshot

```json
{
  "schema_version": 1,
  "sequence": 42,
  "generated_at": "2026-10-30T10:40:00.123-04:00",
  "slot_count": 16,
  "periods": {
    "dbfs_peak_window_ms": 300,
    "vu_integration_ms": 300,
    "lufs_window_ms": 400,
    "logic_poll_ms": 1000,
    "publish_interval_ms": 100,
    "stale_after_ms": 3000
  },
  "sources": [
    {"name": "blackhole", "enabled": true, "connected": true, "detail": "BlackHole 16ch: 13 channels"},
    {"name": "json", "enabled": true, "connected": true, "detail": "accepting POST /api/v1/levels"},
    {"name": "logic", "enabled": true, "connected": true, "detail": "13 tracks matched"}
  ],
  "tracks": [
    {
      "slot": 1, "track_id": "vox", "name": "VOX",
      "gain": 0.7215, "vu": -3.1, "dbfs": -9.4, "lufs": -18.2,
      "updated_at": "2026-10-30T10:40:00.101-04:00", "stale": false
    }
  ]
}
```

`tracks` lists only configured slots. The dashboard always renders `slot_count` (16) boxes in two rows of eight and marks unconfigured slots as available. A metric is `null` until a source reports it. `stale` turns true when no metric has updated within `stale_after_ms`.

## JSON input adapter

`POST /api/v1/levels` accepts levels from any local tool: a test rig, a script, or another meter bridge.

```json
{
  "schema_version": 1,
  "source": "test-rig",
  "tracks": [
    {"track_id": "vox", "gain": 0.75, "vu": -2.5, "dbfs": -8.1, "lufs": -16.4},
    {"slot": 13, "lufs": -20.0}
  ]
}
```

| Rule | Rejection |
| --- | --- |
| `schema_version` must be `1` | 422 |
| `source` matches `^[A-Za-z0-9_.-]{1,64}$` | 422 |
| 1–16 entries, each targeting exactly one of `track_id` or `slot` | 422 |
| At least one metric per entry; values are finite JSON numbers inside the ranges above | 422 |
| No duplicate targets; no unknown fields | 422 |
| Every target exists in the track layout (the whole update is rejected otherwise) | 422 |
| `json` missing from `LEVEL_SOURCES` | 409 |

Accepted updates return `202 {"accepted": 2, "sequence": 43}`. Every rejection is logged at WARNING with the reason, for example:

```text
2026-10-30T10:41:12.402-04:00 [WARNING] api.py:76 reject_invalid - Rejected POST /api/v1/levels: [{'loc': ['body', 'tracks', '0', 'gain'], 'msg': 'Input should be less than or equal to 1', 'type': 'less_than_equal'}]
```

The tvOS app validates every snapshot again before display. A rejected payload leaves the previous display untouched, shows the reason in the header, and logs it through unified logging (`subsystem` = bundle ID, category `bridge`).

## Periods

`PUT /api/v1/periods` takes the full periods object. Values are integer milliseconds.

| Field | Range (ms) | Default |
| --- | --- | --- |
| `dbfs_peak_window_ms` | 50–10000 | 300 |
| `vu_integration_ms` | 50–10000 | 300 |
| `lufs_window_ms` | 100–10000 | 400 |
| `logic_poll_ms` | 250–60000 | 1000 |
| `publish_interval_ms` | 50–5000 | 100 |
| `stale_after_ms` | 500–600000 | 3000 |

Defaults come from `.env`. Changes made from the Apple TV settings screen last until the bridge restarts.

## Track layout

`config/tracks.json` (gitignored; falls back to [`config/tracks.example.json`](../config/tracks.example.json)):

```json
{
  "tracks": [
    {"slot": 1, "id": "vox", "name": "VOX", "logic_track_name": "VOX", "audio_channels": [1]},
    {"slot": 4, "id": "guitar-1", "name": "GUITAR 1", "logic_track_index": 3, "audio_channels": [4, 5]}
  ]
}
```

| Key | Rule |
| --- | --- |
| `slot` | 1–16, unique |
| `id` | `^[a-z0-9][a-z0-9_-]{0,31}$`, unique |
| `name` | 1–32 characters, shown on the box |
| `logic_track_name` | Exact Logic track name (case-insensitive) for gain matching |
| `logic_track_index` | 0-based Logic track index, used when no name matches |
| `audio_channels` | One (mono) or two (stereo) 1-based BlackHole input channels |
