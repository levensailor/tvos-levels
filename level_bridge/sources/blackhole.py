"""Per-track VU, dBFS, and LUFS measured from a BlackHole multichannel loopback device.

Logic Pro routes each track to its own BlackHole output channel(s); this adapter opens the
matching BlackHole input with PortAudio (`sounddevice`) and measures every configured channel.
"""

from __future__ import annotations

import logging
import queue
import threading
import time
from typing import Any

import numpy as np

from level_bridge.metrics import MultiTrackAnalyzer
from level_bridge.settings import Settings
from level_bridge.store import LevelStore

logger = logging.getLogger(__name__)

SOURCE_NAME = "blackhole"
QUEUE_MAX_BLOCKS = 256
QUEUE_TIMEOUT_SECONDS = 0.25
OVERFLOW_LOG_INTERVAL_SECONDS = 10.0


class BlackHoleSource:
    def __init__(self, settings: Settings, store: LevelStore) -> None:
        self._settings = settings
        self._store = store
        self._queue: queue.Queue[np.ndarray] = queue.Queue(maxsize=QUEUE_MAX_BLOCKS)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._stream: Any = None
        self._status_flags = 0
        self._dropped_blocks = 0

    def start(self) -> None:
        channel_map = self._store.layout.audio_channel_map()
        needed = self._store.layout.required_input_channels()
        if not channel_map:
            self._fail("no tracks define audio_channels")
            return
        try:
            import sounddevice as sd
        except (ImportError, OSError) as exc:
            self._fail(f"PortAudio unavailable: {exc}")
            return

        device_index = self._find_device(sd, needed)
        if device_index is None:
            return

        analyzer = MultiTrackAnalyzer(
            channel_map=channel_map,
            input_channels=needed,
            sample_rate=self._settings.audio_sample_rate,
            floor_db=self._settings.metric_floor_db,
            vu_reference_dbfs=self._settings.vu_reference_dbfs,
        )
        try:
            self._stream = sd.InputStream(
                device=device_index,
                channels=needed,
                samplerate=self._settings.audio_sample_rate,
                blocksize=self._settings.audio_block_size,
                dtype="float32",
                callback=self._callback,
            )
            self._thread = threading.Thread(
                target=self._run, args=(analyzer,), name="blackhole-analyzer", daemon=True
            )
            self._thread.start()
            self._stream.start()
        except Exception as exc:  # noqa: BLE001 - PortAudio raises several error types
            self._stop.set()
            self._fail(f"cannot open input stream: {exc}")
            return
        self._store.set_source_status(
            SOURCE_NAME,
            connected=True,
            detail=f"{self._settings.blackhole_device_name}: {needed} channels",
        )
        logger.info("BlackHole capture started on device %s with %d channels", device_index, needed)

    def _find_device(self, sd: Any, needed: int) -> int | None:
        target = self._settings.blackhole_device_name.casefold()
        matches = [
            (index, device)
            for index, device in enumerate(sd.query_devices())
            if target in str(device.get("name", "")).casefold()
            and int(device.get("max_input_channels", 0)) > 0
        ]
        # region agent log
        try:
            import json as _j
            _devs = [{"index": i, "name": str(d.get("name")), "in": int(d.get("max_input_channels", 0)), "out": int(d.get("max_output_channels", 0)), "hostapi": d.get("hostapi"), "sr": d.get("default_samplerate")} for i, d in enumerate(sd.query_devices())]
            with open("/Users/levensailor/dev/tvos-levels/.cursor/debug-da6e9b.log", "a") as _f:
                _f.write(_j.dumps({"sessionId": "da6e9b", "runId": "run2", "hypothesisId": "G,I", "location": "blackhole.py:_find_device", "message": "CoreAudio device list and substring matches", "data": {"target": target, "devices": _devs, "match_indexes": [i for i, _ in matches], "default_devices": list(sd.default.device) if hasattr(sd.default, "device") else None}, "timestamp": int(time.time() * 1000)}, default=str) + "\n")
        except Exception:
            pass
        # endregion
        if not matches:
            self._fail(f"input device {self._settings.blackhole_device_name!r} not found")
            return None
        index, device = matches[0]
        available = int(device["max_input_channels"])
        if available < needed:
            self._fail(f"device {device['name']!r} has {available} inputs, {needed} required")
            return None
        return index

    def _fail(self, detail: str) -> None:
        logger.error("BlackHole source unavailable: %s", detail)
        self._store.set_source_status(SOURCE_NAME, connected=False, detail=detail)

    def _callback(self, indata: np.ndarray, frames: int, time_info: Any, status: Any) -> None:
        if status:
            self._status_flags += 1
        try:
            self._queue.put_nowait(indata.copy())
        except queue.Full:
            self._dropped_blocks += 1

    def _run(self, analyzer: MultiTrackAnalyzer) -> None:
        last_publish = 0.0
        last_report = time.monotonic()
        reported_flags = 0
        reported_drops = 0
        # region agent log
        _dbg_peak = None
        _dbg_last = time.monotonic()
        _dbg_blocks = 0
        # endregion
        while not self._stop.is_set():
            try:
                block = self._queue.get(timeout=QUEUE_TIMEOUT_SECONDS)
            except queue.Empty:
                continue
            # region agent log
            try:
                _blk = np.max(np.abs(block), axis=0)
                _dbg_peak = _blk if _dbg_peak is None else np.maximum(_dbg_peak, _blk)
                _dbg_blocks += 1
                if time.monotonic() - _dbg_last >= 3.0:
                    import json as _j
                    _pk = [round(float(20 * np.log10(max(v, 1e-9))), 1) for v in _dbg_peak]
                    _active = [i + 1 for i, v in enumerate(_pk) if v > -90.0]
                    with open("/Users/levensailor/dev/tvos-levels/.cursor/debug-da6e9b.log", "a") as _f:
                        _f.write(_j.dumps({"sessionId": "da6e9b", "runId": "run2", "hypothesisId": "F,G", "location": "blackhole.py:_run", "message": "per-input-channel peak dBFS over last ~3s (index 0 = channel 1)", "data": {"block_shape": list(block.shape), "blocks": _dbg_blocks, "peak_dbfs_by_channel": _pk, "channels_with_signal": _active, "channel_map": {str(k): list(v) for k, v in self._store.layout.audio_channel_map().items()}}, "timestamp": int(time.time() * 1000)}, default=str) + "\n")
                    _dbg_peak = None
                    _dbg_blocks = 0
                    _dbg_last = time.monotonic()
            except Exception:
                pass
            # endregion
            try:
                analyzer.process(block)
            except ValueError as exc:
                logger.error("Rejected audio block: %s", exc)
                continue
            periods = self._store.periods()
            now = time.monotonic()
            if now - last_publish >= periods.publish_interval_ms / 1000.0:
                last_publish = now
                self._store.update_audio_metrics(
                    analyzer.metrics(
                        periods.dbfs_peak_window_ms,
                        periods.vu_integration_ms,
                        periods.lufs_window_ms,
                    )
                )
            if now - last_report >= OVERFLOW_LOG_INTERVAL_SECONDS:
                last_report = now
                if self._status_flags != reported_flags or self._dropped_blocks != reported_drops:
                    logger.warning(
                        "Audio input irregularities: %d status flags, %d dropped blocks",
                        self._status_flags - reported_flags,
                        self._dropped_blocks - reported_drops,
                    )
                    reported_flags = self._status_flags
                    reported_drops = self._dropped_blocks

    def stop(self) -> None:
        self._stop.set()
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception as exc:  # noqa: BLE001 - shutdown must not raise
                logger.warning("Error closing BlackHole stream: %s", exc)
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        logger.info("BlackHole capture stopped")
