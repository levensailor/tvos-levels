from __future__ import annotations

import numpy as np
import pytest

from level_bridge.metrics import MultiTrackAnalyzer, k_weighting_coefficients

SAMPLE_RATE = 48_000
BLOCK = 1024
FLOOR = -96.0
VU_REFERENCE = -18.0


def sine(amplitude: float, seconds: float, frequency: float = 1_000.0) -> np.ndarray:
    t = np.arange(int(SAMPLE_RATE * seconds)) / SAMPLE_RATE
    return amplitude * np.sin(2 * np.pi * frequency * t)


def feed(analyzer: MultiTrackAnalyzer, signal: np.ndarray) -> None:
    for start in range(0, signal.shape[0], BLOCK):
        analyzer.process(signal[start : start + BLOCK])


def test_k_weighting_matches_bs1770_reference_at_48k() -> None:
    (shelf_b, shelf_a), (hp_b, hp_a) = k_weighting_coefficients(SAMPLE_RATE)
    np.testing.assert_allclose(
        shelf_b, [1.53512485958697, -2.69169618940638, 1.19839281085285], atol=1e-6
    )
    np.testing.assert_allclose(shelf_a, [1.0, -1.69065929318241, 0.73248077421585], atol=1e-6)
    np.testing.assert_allclose(hp_b, [1.0, -2.0, 1.0])
    np.testing.assert_allclose(hp_a, [1.0, -1.99004745483398, 0.99007225036621], atol=1e-6)


def test_full_scale_sine_reads_reference_levels() -> None:
    analyzer = MultiTrackAnalyzer({1: [1]}, 1, SAMPLE_RATE, FLOOR, VU_REFERENCE)
    feed(analyzer, sine(1.0, 2.0)[:, None])
    metrics = analyzer.metrics(300, 300, 400)[1]
    assert metrics.dbfs == pytest.approx(0.0, abs=0.01)
    assert metrics.vu == pytest.approx(-VU_REFERENCE, abs=0.05)
    assert metrics.lufs == pytest.approx(-3.01, abs=0.1)


def test_reference_level_sine_reads_zero_vu() -> None:
    amplitude = 10 ** (VU_REFERENCE / 20)
    analyzer = MultiTrackAnalyzer({1: [1]}, 1, SAMPLE_RATE, FLOOR, VU_REFERENCE)
    feed(analyzer, sine(amplitude, 1.0)[:, None])
    assert analyzer.metrics(300, 300, 400)[1].vu == pytest.approx(0.0, abs=0.05)


def test_channels_are_measured_independently_and_silence_hits_floor() -> None:
    analyzer = MultiTrackAnalyzer({1: [1], 2: [2], 3: [2, 3]}, 3, SAMPLE_RATE, FLOOR, VU_REFERENCE)
    loud = sine(0.5, 1.0)
    block = np.column_stack([np.zeros_like(loud), loud, loud])
    feed(analyzer, block)
    metrics = analyzer.metrics(300, 300, 400)
    assert metrics[1].dbfs == FLOOR
    assert metrics[1].lufs == FLOOR
    assert metrics[2].dbfs == pytest.approx(-6.02, abs=0.05)
    assert metrics[3].lufs == pytest.approx(metrics[2].lufs + 3.01, abs=0.1)


def test_rejects_wrong_channel_count_and_bad_mapping() -> None:
    analyzer = MultiTrackAnalyzer({1: [1]}, 2, SAMPLE_RATE, FLOOR, VU_REFERENCE)
    with pytest.raises(ValueError):
        analyzer.process(np.zeros((BLOCK, 3)))
    with pytest.raises(ValueError):
        MultiTrackAnalyzer({1: [3]}, 2, SAMPLE_RATE, FLOOR, VU_REFERENCE)
