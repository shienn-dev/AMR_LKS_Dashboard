"""Odometry source tests. No odometry hardware is present or faked as real."""

from __future__ import annotations

import math

from amr_core.robot.interfaces import ConnectionState, OdometrySample
from amr_core.robot.odometry import NoOdometrySource, validate_sample


def test_no_source_is_unavailable_and_returns_no_sample() -> None:
    source = NoOdometrySource("no source")
    assert source.state() is ConnectionState.UNAVAILABLE
    assert source.sample() is None
    assert source.detail() == "no source"


def test_validate_sample_accepts_finite() -> None:
    ok, reason = validate_sample(OdometrySample(1.0, 2.0, 3.0, 0.1, 0.2, 10.0, "test"))
    assert ok is True
    assert reason == ""


def test_validate_sample_rejects_non_finite() -> None:
    ok, reason = validate_sample(OdometrySample(math.nan, 0.0, 0.0, 0.0, 0.0, 0.0, "test"))
    assert ok is False
    assert "finite" in reason
