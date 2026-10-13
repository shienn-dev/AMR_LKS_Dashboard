"""Tests for mission configuration validation (requirement: valid & invalid)."""

from __future__ import annotations

from amr_core.mission import (
    MissionConfig,
    is_valid,
    validate_mission,
)


def _valid_config() -> MissionConfig:
    return MissionConfig(
        mission_id="modul_E",
        version=1,
        time_limit_s=600,
        reserve_for_home_s=60,
        target_order=["T3", "T1", "T4", "T2"],
        rack_colors={"rack_A": "red", "rack_B": "green", "rack_C": "blue"},
    )


def test_valid_mission_has_no_issues() -> None:
    assert validate_mission(_valid_config()) == []
    assert is_valid(_valid_config())


def test_missing_mission_id_is_rejected() -> None:
    config = _valid_config()
    config.mission_id = "  "
    issues = validate_mission(config)
    assert any(i.field == "mission_id" for i in issues)
    assert not is_valid(config)


def test_time_limit_out_of_bounds_is_rejected() -> None:
    config = _valid_config()
    config.time_limit_s = 10
    issues = validate_mission(config)
    assert any(i.field == "time_limit_s" for i in issues)


def test_reserve_not_smaller_than_limit_is_rejected() -> None:
    config = _valid_config()
    config.reserve_for_home_s = 600
    issues = validate_mission(config)
    assert any(i.field == "reserve_for_home_s" for i in issues)


def test_empty_target_order_is_rejected() -> None:
    config = _valid_config()
    config.target_order = []
    issues = validate_mission(config)
    assert any(i.field == "target_order" for i in issues)


def test_unknown_target_is_rejected() -> None:
    config = _valid_config()
    config.target_order = ["T1", "T9"]
    issues = validate_mission(config)
    assert any("Unknown targets" in i.message for i in issues)


def test_duplicate_targets_are_rejected() -> None:
    config = _valid_config()
    config.target_order = ["T1", "T1"]
    issues = validate_mission(config)
    assert any("duplicates" in i.message for i in issues)


def test_invalid_rack_color_is_rejected() -> None:
    config = _valid_config()
    config.rack_colors = {"rack_A": "purple"}
    issues = validate_mission(config)
    assert any("invalid color" in i.message for i in issues)


def test_unknown_rack_is_rejected() -> None:
    config = _valid_config()
    config.rack_colors = {"rack_Z": "red"}
    issues = validate_mission(config)
    assert any("Unknown rack" in i.message for i in issues)


def test_empty_rack_colors_is_rejected() -> None:
    config = _valid_config()
    config.rack_colors = {}
    issues = validate_mission(config)
    assert any(i.field == "rack_colors" for i in issues)


def test_validation_does_not_mutate_config() -> None:
    config = _valid_config()
    before = (list(config.target_order), dict(config.rack_colors))
    validate_mission(config)
    assert (config.target_order, config.rack_colors) == before
