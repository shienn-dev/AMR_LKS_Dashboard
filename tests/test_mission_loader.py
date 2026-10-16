"""Tests for the Phase 2 mission YAML loader and validator.

Unit tests only; parsing strings, no filesystem, no ROS 2, no browser.
"""

from __future__ import annotations

from amr_core.mission import MissionSpec, StepSpec
from amr_core.mission_loader import load_mission_yaml

VALID = """
mission: modul_E
version: 1
time_limit_s: 600
reserve_for_home_s: 60
start: physical_button
steps:
  - for_each: {targets: [T3, T1, T4, T2]}
    do: {skill: go_to, timeout_s: 90, retry: 2, on_fail: skip}
  - {skill: return_home, timeout_s: 90}
"""


def _errors(text: str) -> list[str]:
    spec, issues = load_mission_yaml(text)
    assert spec is None
    return [i.field for i in issues]


def _messages(text: str) -> str:
    _, issues = load_mission_yaml(text)
    return " | ".join(i.message for i in issues)


def test_valid_mission_parses() -> None:
    spec, issues = load_mission_yaml(VALID)
    assert issues == []
    assert isinstance(spec, MissionSpec)
    assert spec.mission_id == "modul_E"
    assert spec.time_limit_s == 600
    assert spec.reserve_for_home_s == 60


def test_for_each_expands_to_flat_steps() -> None:
    spec, issues = load_mission_yaml(VALID)
    assert issues == []
    assert spec is not None
    # 4 expanded go_to steps + 1 return_home
    assert len(spec.steps) == 5
    assert [s.target for s in spec.steps[:4]] == ["T3", "T1", "T4", "T2"]
    assert all(s.skill == "go_to" for s in spec.steps[:4])
    assert spec.steps[4].skill == "return_home"
    assert spec.steps[4].step_id == "s4"


def test_flat_step_form_also_parses() -> None:
    text = """
mission: m
version: 1
time_limit_s: 600
reserve_for_home_s: 60
steps:
  - {skill: go_to, target: T1, timeout_s: 30}
  - {skill: return_home, timeout_s: 30}
"""
    spec, issues = load_mission_yaml(text)
    assert issues == []
    assert spec is not None
    assert len(spec.steps) == 2
    assert spec.steps[0].target == "T1"


def test_timeout_s_is_required() -> None:
    text = VALID.replace(", timeout_s: 90", "").replace(", timeout_s: 90", "")
    text = text.replace("{skill: return_home, timeout_s: 90}", "{skill: return_home}")
    assert "steps[0].timeout_s" in _errors(text)


def test_missing_mission_id() -> None:
    text = """
version: 1
time_limit_s: 600
reserve_for_home_s: 60
steps:
  - {skill: return_home, timeout_s: 30}
"""
    assert "mission.mission" in _errors(text)


def test_version_zero_rejected() -> None:
    text = VALID.replace("version: 1", "version: 0")
    assert "mission.version" in _errors(text)


def test_time_limit_out_of_range() -> None:
    text = VALID.replace("time_limit_s: 600", "time_limit_s: 700")
    assert "mission.time_limit_s" in _errors(text)
    assert "700" in _messages(text)


def test_reserve_not_smaller_than_limit() -> None:
    text = VALID.replace("reserve_for_home_s: 60", "reserve_for_home_s: 600")
    assert "mission.reserve_for_home_s" in _errors(text)


def test_reserve_negative() -> None:
    text = VALID.replace("reserve_for_home_s: 60", "reserve_for_home_s: -1")
    assert "mission.reserve_for_home_s" in _errors(text)


def test_unknown_skill_rejected() -> None:
    text = VALID.replace("skill: return_home", "skill: fly")
    # The loader reports the raw step index in the file (2nd step -> steps[1]).
    assert "steps[1].skill" in _errors(text)


def test_go_to_without_target_rejected() -> None:
    text = """
mission: m
version: 1
time_limit_s: 600
reserve_for_home_s: 60
steps:
  - {skill: go_to, timeout_s: 30}
  - {skill: return_home, timeout_s: 30}
"""
    assert "steps[0].target" in _errors(text)


def test_unknown_target_rejected() -> None:
    text = VALID.replace("targets: [T3, T1, T4, T2]", "targets: [T3, T9]")
    errors = _errors(text)
    assert any("for_each.targets" in e for e in errors)


def test_duplicate_for_each_target_rejected() -> None:
    text = VALID.replace("targets: [T3, T1, T4, T2]", "targets: [T3, T3]")
    errors = _errors(text)
    assert any("for_each.targets" in e for e in errors)
    assert "duplicate target 'T3'" in _messages(text)


def test_invalid_on_fail_rejected() -> None:
    text = VALID.replace("on_fail: skip", "on_fail: retry")
    errors = _errors(text)
    assert any("on_fail" in e for e in errors)
    assert "must be 'skip' or 'fail'" in _messages(text)


def test_negative_retry_rejected() -> None:
    text = VALID.replace("retry: 2", "retry: -1")
    assert any("retry" in e for e in _errors(text))


def test_dynamic_expression_rejected_not_evaluated() -> None:
    text = """
mission: g2
version: 1
time_limit_s: 600
reserve_for_home_s: 60
steps:
  - {skill: go_to, target: "rack_for(obj.color)", timeout_s: 30}
  - {skill: return_home, timeout_s: 30}
"""
    errors = _errors(text)
    assert any("target" in e for e in errors)
    assert "dynamic expressions are not supported yet" in _messages(text)


def test_malformed_yaml_is_document_error() -> None:
    text = "mission: [unclosed"
    spec, issues = load_mission_yaml(text)
    assert spec is None
    assert issues and issues[0].field == "document"


def test_empty_document_error() -> None:
    spec, issues = load_mission_yaml("")
    assert spec is None
    assert issues[0].field == "document"


def test_steps_missing() -> None:
    text = """
mission: m
version: 1
time_limit_s: 600
reserve_for_home_s: 60
"""
    assert "mission.steps" in _errors(text)


def test_steps_empty() -> None:
    text = """
mission: m
version: 1
time_limit_s: 600
reserve_for_home_s: 60
steps: []
"""
    assert "mission.steps" in _errors(text)


def test_retry_is_additional_attempts() -> None:
    spec, issues = load_mission_yaml(VALID)
    assert issues == []
    assert spec is not None
    assert isinstance(spec.steps[0], StepSpec)
    assert spec.steps[0].retry == 2  # 3 attempts total (documented convention)
