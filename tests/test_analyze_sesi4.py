"""Unit tests for the session-4 offline analysis script (no hardware).

The script lives in ``scripts/`` because it is a diagnostics tool, not part of
the shipped package, so it is loaded by path here.

Every dataset below is **synthetic**: it exists to check the arithmetic of the
session-4 analysis (C_eff statistics, the two competing distance models, the
decision rule). None of it is session-4 measurement data.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "analyze_sesi4.py"
_spec = importlib.util.spec_from_file_location("analyze_sesi4", _SCRIPT)
assert _spec is not None and _spec.loader is not None
analyze = importlib.util.module_from_spec(_spec)
sys.modules["analyze_sesi4"] = analyze
_spec.loader.exec_module(analyze)


# --- C_eff statistics ----------------------------------------------------- #

def test_rollout_statistics_are_exact_for_known_values() -> None:
    result = analyze.analyse_rollout([207.0, 205.0, 209.0], rotations=10)
    assert result.c_eff_cm == [20.7, 20.5, 20.9]
    assert result.mean_cm == pytest.approx(20.7)
    assert result.sd_cm == pytest.approx(0.2)
    assert result.median_cm == pytest.approx(20.7)
    assert result.cv_percent == pytest.approx(100.0 * 0.2 / 20.7)
    assert result.sigma_low_cm == pytest.approx(20.5)
    assert result.sigma_high_cm == pytest.approx(20.9)


def test_rollout_without_trials_returns_empty_result() -> None:
    result = analyze.analyse_rollout([], rotations=10)
    assert result.c_eff_cm == []
    assert result.mean_cm == 0.0


def test_rollout_rejects_non_positive_rotation_count() -> None:
    with pytest.raises(ValueError):
        analyze.analyse_rollout([200.0], rotations=0)


def test_sample_sd_and_sem_handle_single_sample() -> None:
    assert analyze.sample_sd([5.0]) == 0.0
    assert analyze.sem([5.0]) == 0.0
    assert analyze.sample_sd([]) == 0.0
    assert analyze.sem([]) == 0.0


# --- model fitting -------------------------------------------------------- #

def test_fit_ratio_recovers_the_generating_ratio() -> None:
    x = [37.3, 111.9]
    y = [0.885 * xi for xi in x]
    fit = analyze.fit_ratio(x, y)
    assert fit.params["r"] == pytest.approx(0.885)
    assert fit.rms_cm == pytest.approx(0.0, abs=1e-9)


def test_fit_offset_recovers_the_generating_offset() -> None:
    x = [37.3, 111.9]
    y = [xi - 4.89 for xi in x]
    fit = analyze.fit_offset(x, y)
    assert fit.params["k_cm"] == pytest.approx(4.89)
    assert fit.rms_cm == pytest.approx(0.0, abs=1e-9)


def test_fit_joint_recovers_both_parameters() -> None:
    x = [37.3, 111.9, 55.9]
    y = [0.95 * xi - 4.0 for xi in x]
    fit = analyze.fit_joint(x, y)
    assert fit.params["r"] == pytest.approx(0.95)
    assert fit.params["k_cm"] == pytest.approx(4.0)
    assert fit.rms_cm == pytest.approx(0.0, abs=1e-9)


def test_fit_joint_needs_at_least_two_points() -> None:
    with pytest.raises(ValueError):
        analyze.fit_joint([37.3], [33.0])


def test_offset_model_beats_ratio_model_on_offset_data() -> None:
    """A pure offset deficit must fit better under the offset model."""
    x = [37.3, 111.9]
    y = [xi - 4.89 for xi in x]
    assert analyze.fit_offset(x, y).rms_cm < analyze.fit_ratio(x, y).rms_cm


def test_ratio_model_beats_offset_model_on_ratio_data() -> None:
    x = [37.3, 111.9]
    y = [0.885 * xi for xi in x]
    assert analyze.fit_ratio(x, y).rms_cm < analyze.fit_offset(x, y).rms_cm


# --- decision rule -------------------------------------------------------- #

def test_decision_rule_thresholds() -> None:
    assert analyze.decide(99.0) == "RATIO"
    assert analyze.decide(101.0) == "RATIO"
    assert analyze.decide(103.0) == "INCONCLUSIVE"
    assert analyze.decide(105.0) == "OFFSET"
    assert analyze.decide(107.0) == "OFFSET"


def test_c_free_check_is_zero_for_ratio_and_2k_for_offset() -> None:
    difference, sigma = analyze.c_free_check(99.0, 33.0, 0.5, 0.5)
    assert difference == pytest.approx(0.0)
    assert sigma == pytest.approx((0.25 + 9 * 0.25) ** 0.5)
    offset_difference, _ = analyze.c_free_check(108.78, 33.0, 0.5, 0.5)
    assert offset_difference == pytest.approx(2 * analyze.OFFSET_PRIOR_CM)


# --- reporting must survive partial data ---------------------------------- #

def test_report_sections_handle_missing_data(capsys: pytest.CaptureFixture[str]) -> None:
    analyze.report_rollout(analyze.analyse_rollout([], 10), 10)
    analyze.report_duration([], 0.6, 20.72, 1.84)
    analyze.report_models([], 0.6, 20.72)
    analyze.report_freewheel([], 0.6, 20.72)
    output = capsys.readouterr().out
    assert output.count("data belum ada") >= 4


def test_duration_report_flags_the_offset_outcome(capsys: pytest.CaptureFixture[str]) -> None:
    trials = [
        {"duration_s": 3, "distance_cm": 33.0},
        {"duration_s": 3, "distance_cm": 32.4},
        {"duration_s": 3, "distance_cm": 33.6},
        {"duration_s": 9, "distance_cm": 106.0},
        {"duration_s": 9, "distance_cm": 107.5},
        {"duration_s": 9, "distance_cm": 105.5},
    ]
    analyze.report_duration(trials, 0.6, 20.72, 1.84)
    output = capsys.readouterr().out
    assert "HASIL: OFFSET" in output
    assert "uji ini tidak bergantung pada C_eff" in output


def test_freewheel_report_flags_the_impossible_branch(capsys: pytest.CaptureFixture[str]) -> None:
    trials = [{"trial": 1, "rotations": 20, "seconds": 40.0}]
    analyze.report_freewheel(trials, 0.6, 20.72)
    output = capsys.readouterr().out
    assert "tidak mungkin" in output
