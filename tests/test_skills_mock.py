"""Tests for the Phase 2 skill contract and mock platform.

Unit tests; injected clock, no sleep, no ROS 2, no browser.
"""

from __future__ import annotations

from amr_core.mock_platform import MissionClock, ScriptedSkill, default_skill_factory
from amr_core.skills import SkillContext, SkillResult, SkillStatus


def _ctx() -> SkillContext:
    return SkillContext(log=lambda _msg: None)


def test_scripted_skill_success() -> None:
    skill = ScriptedSkill("go_to", script=["SUCCESS"], duration_s=5.0)
    skill.start({}, _ctx())
    assert skill.poll(0.0) is None
    result = skill.poll(5.0)
    assert isinstance(result, SkillResult)
    assert result.status is SkillStatus.SUCCESS


def test_scripted_skill_reports_timeout() -> None:
    skill = ScriptedSkill("go_to", script=["TIMEOUT"], duration_s=2.0)
    skill.start({}, _ctx())
    skill.poll(0.0)
    result = skill.poll(2.0)
    assert result is not None and result.status is SkillStatus.TIMEOUT


def test_attempts_follow_the_script() -> None:
    skill = ScriptedSkill("go_to", script=["FAILURE", "SUCCESS"], duration_s=1.0)
    skill.start({}, _ctx())
    skill.poll(0.0)
    first = skill.poll(1.0)
    assert first is not None and first.status is SkillStatus.FAILURE
    # A new attempt.
    skill.start({}, _ctx())
    skill.poll(10.0)
    second = skill.poll(11.0)
    assert second is not None and second.status is SkillStatus.SUCCESS


def test_cancel_is_idempotent_and_stops_results() -> None:
    skill = ScriptedSkill("go_to", script=["SUCCESS"], duration_s=1.0)
    skill.start({}, _ctx())
    skill.poll(0.0)
    skill.cancel("test")
    skill.cancel("test-again")  # must not raise
    assert skill.cancelled
    assert skill.poll(100.0) is None  # no result after cancel


def test_skill_emits_at_most_one_result() -> None:
    skill = ScriptedSkill("go_to", script=["SUCCESS"], duration_s=1.0)
    skill.start({}, _ctx())
    skill.poll(0.0)
    first = skill.poll(1.0)
    assert first is not None
    assert skill.poll(2.0) is None  # already emitted


def test_mission_clock_advances_only_forward() -> None:
    clock = MissionClock()
    assert clock.advance(5.0) == 5.0
    assert clock.advance(-1.0) == 5.0  # ignores non-positive
    assert clock.now_s == 5.0


def test_default_skill_factory_names() -> None:
    skills = default_skill_factory()
    assert set(skills) == {"go_to", "return_home", "wait_for_start"}
