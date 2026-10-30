"""Per-track peak dBFS, VU, and momentary LUFS (ITU-R BS.1770 K-weighting) measurement."""

from __future__ import annotations

import math
from collections import deque
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import numpy as np
from scipy.signal import lfilter

LUFS_OFFSET_DB = -0.691
SINE_PEAK_TO_RMS_DB = 20.0 * math.log10(math.sqrt(2.0))
MAX_HISTORY_MS = 10_000

# ITU-R BS.1770-4 K-weighting prefilter parameters (high shelf, then RLB high-pass).
SHELF_GAIN_DB = 3.999843853973347
SHELF_CENTER_HZ = 1681.974450955533
SHELF_Q = 0.7071752369554196
SHELF_BOOST_EXPONENT = 0.4996667741545416
HIGHPASS_CENTER_HZ = 38.13547087602444
HIGHPASS_Q = 0.5003270373238773

Biquad = tuple[np.ndarray, np.ndarray]


def k_weighting_coefficients(sample_rate: float) -> tuple[Biquad, Biquad]:
    """Return (shelf, high-pass) biquad coefficients for the given sample rate."""
    k = math.tan(math.pi * SHELF_CENTER_HZ / sample_rate)
    vh = 10.0 ** (SHELF_GAIN_DB / 20.0)
    vb = vh**SHELF_BOOST_EXPONENT
    a0 = 1.0 + k / SHELF_Q + k * k
    shelf_b = np.array(
        [
            (vh + vb * k / SHELF_Q + k * k) / a0,
            2.0 * (k * k - vh) / a0,
            (vh - vb * k / SHELF_Q + k * k) / a0,
        ]
    )
    shelf_a = np.array([1.0, 2.0 * (k * k - 1.0) / a0, (1.0 - k / SHELF_Q + k * k) / a0])

    k = math.tan(math.pi * HIGHPASS_CENTER_HZ / sample_rate)
    denominator = 1.0 + k / HIGHPASS_Q + k * k
    highpass_b = np.array([1.0, -2.0, 1.0])
    highpass_a = np.array(
        [1.0, 2.0 * (k * k - 1.0) / denominator, (1.0 - k / HIGHPASS_Q + k * k) / denominator]
    )
    return (shelf_b, shelf_a), (highpass_b, highpass_a)


def level_db(power_ratio_db: float, floor_db: float) -> float:
    return max(floor_db, power_ratio_db)


def amplitude_to_db(amplitude: float, floor_db: float) -> float:
    if amplitude <= 0.0 or not math.isfinite(amplitude):
        return floor_db
    return max(floor_db, 20.0 * math.log10(amplitude))


@dataclass(frozen=True)
class BlockSummary:
    frames: int
    peak: float
    mean_square_sum: float
    weighted_square_sum: float


@dataclass(frozen=True)
class TrackMetrics:
    dbfs: float
    vu: float
    lufs: float


class MultiTrackAnalyzer:
    """Accumulates per-block summaries and reports windowed metrics for each mapped slot."""

    def __init__(
        self,
        channel_map: Mapping[int, Sequence[int]],
        input_channels: int,
        sample_rate: int,
        floor_db: float,
        vu_reference_dbfs: float,
        history_ms: int = MAX_HISTORY_MS,
    ) -> None:
        if input_channels < 1:
            raise ValueError("input_channels must be at least 1")
        for slot, channels in channel_map.items():
            if not channels or any(not 1 <= channel <= input_channels for channel in channels):
                raise ValueError(f"slot {slot} maps channels outside 1..{input_channels}")
        self._columns = {
            slot: [channel - 1 for channel in channels] for slot, channels in channel_map.items()
        }
        self._input_channels = input_channels
        self._sample_rate = sample_rate
        self._floor_db = floor_db
        self._vu_reference_dbfs = vu_reference_dbfs
        self._max_frames = int(sample_rate * history_ms / 1000)
        shelf, highpass = k_weighting_coefficients(sample_rate)
        self._shelf_b, self._shelf_a = shelf
        self._hp_b, self._hp_a = highpass
        self._shelf_state = np.zeros((2, input_channels))
        self._hp_state = np.zeros((2, input_channels))
        self._history: dict[int, deque[BlockSummary]] = {slot: deque() for slot in self._columns}
        self._history_frames: dict[int, int] = {slot: 0 for slot in self._columns}

    def process(self, block: np.ndarray) -> None:
        samples = np.asarray(block, dtype=np.float64)
        if samples.ndim != 2 or samples.shape[1] != self._input_channels:
            raise ValueError(
                f"expected a (frames, {self._input_channels}) block, got shape {samples.shape}"
            )
        if samples.shape[0] == 0:
            return
        if not np.all(np.isfinite(samples)):
            samples = np.nan_to_num(samples, nan=0.0, posinf=0.0, neginf=0.0)
        weighted, self._shelf_state = lfilter(
            self._shelf_b, self._shelf_a, samples, axis=0, zi=self._shelf_state
        )
        weighted, self._hp_state = lfilter(
            self._hp_b, self._hp_a, weighted, axis=0, zi=self._hp_state
        )
        frames = samples.shape[0]
        for slot, columns in self._columns.items():
            raw = samples[:, columns]
            k_weighted = weighted[:, columns]
            summary = BlockSummary(
                frames=frames,
                peak=float(np.max(np.abs(raw))),
                mean_square_sum=float(np.sum(raw * raw)) / len(columns),
                weighted_square_sum=float(np.sum(k_weighted * k_weighted)),
            )
            history = self._history[slot]
            history.append(summary)
            self._history_frames[slot] += frames
            while history and self._history_frames[slot] - history[0].frames >= self._max_frames:
                self._history_frames[slot] -= history.popleft().frames

    def _window(self, slot: int, window_ms: int) -> list[BlockSummary]:
        target = max(1, int(self._sample_rate * window_ms / 1000))
        selected: list[BlockSummary] = []
        frames = 0
        for summary in reversed(self._history[slot]):
            selected.append(summary)
            frames += summary.frames
            if frames >= target:
                break
        return selected

    def metrics(
        self, dbfs_window_ms: int, vu_window_ms: int, lufs_window_ms: int
    ) -> dict[int, TrackMetrics]:
        results: dict[int, TrackMetrics] = {}
        for slot in self._columns:
            if not self._history[slot]:
                continue
            peak_blocks = self._window(slot, dbfs_window_ms)
            vu_blocks = self._window(slot, vu_window_ms)
            lufs_blocks = self._window(slot, lufs_window_ms)

            dbfs = amplitude_to_db(max(block.peak for block in peak_blocks), self._floor_db)

            vu_frames = sum(block.frames for block in vu_blocks)
            mean_square = sum(block.mean_square_sum for block in vu_blocks) / vu_frames
            rms_dbfs = amplitude_to_db(math.sqrt(mean_square), self._floor_db - SINE_PEAK_TO_RMS_DB)
            vu = level_db(rms_dbfs + SINE_PEAK_TO_RMS_DB - self._vu_reference_dbfs, self._floor_db)

            lufs_frames = sum(block.frames for block in lufs_blocks)
            weighted_power = sum(block.weighted_square_sum for block in lufs_blocks) / lufs_frames
            lufs = (
                level_db(LUFS_OFFSET_DB + 10.0 * math.log10(weighted_power), self._floor_db)
                if weighted_power > 0.0
                else self._floor_db
            )
            results[slot] = TrackMetrics(dbfs=dbfs, vu=vu, lufs=lufs)
        return results
