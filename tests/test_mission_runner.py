"""Tests for the Phase 2 MissionRunner.

Unit tests only: deterministic, injected clock, no threads, no sleeps, no ROS 2,
no browser.
"""

from __future__ import annotations

from amr_core.mission import MissionSpec, StepSpec
from amr_core.mission_runner import (
    MissionRunner,
    RunnerOutcome,
    RunnerState,
    StepOutcome,
)
from amr_core.mock_platform import MissionClock, ScriptedSkill


def _spec(*steps: StepSpec, time_limit_s: int = 600, reserve: int = 60) -> MissionSpec:
    return MissionSpec(
        mission_id="m",
        version=1,
        time_limit_s=time_limit_s,
        reserve_for_home_s=reserve,
        steps=steps,
    )


def _skills(go_to: list[str], return_home: list[str], go_dur: float = 1.0,
            home_dur: float = 1.0) -> dict[str, ScriptedSkill]:
    return {
        "go_to": ScriptedSkill("go_to", script=go_to, duration_s=go_dur),
        "return_home": ScriptedSkill("return_home", script=return_home, duration_s=home_dur),
    }


def _run(runner: MissionRunner, dt: float = 1.0, limit: int = 500):
    clock = MissionClock()
    runner.start(0.0)
    outcome = None
    for _ in range(limit):
        outcome = runner.step_once(clock.now_s)
        if outcome is not RunnerOutcome.WAIT:
            break
        clock.advance(dt)
    return outcome


def _records(runner: MissionRunner):
    return [(r.step_id, r.attempt, r.outcome, r.reason) for r in runner.records]


# --------------------------------------------------------------------------- #
# Happy path
# --------------------------------------------------------------------------- #

def test_all_steps_success_reaches_done() -> None:
    spec = _spec(
        StepSpec("s0", "go_to", 10, target="T1"),
        StepSpec("s1", "go_to", 10, target="T2"),
        StepSpec("s2", "return_home", 10),
    )
    runner = MissionRunner(spec=spec, skills=_skills(["SUCCESS", "SUCCESS"], ["SUCCESS"]))
    assert _run(runner) is RunnerOutcome.DONE
    assert runner.state is RunnerState.FINISHED
    assert [r.outcome for r in runner.records] == ["SUCCESS", "SUCCESS", "SUCCESS"]


def test_mission_without_return_home_can_be_done() -> None:
    spec = _spec(StepSpec("s0", "go_to", 10, target="T1"))
    runner = MissionRunner(spec=spec, skills=_skills(["SUCCESS"], ["SUCCESS"]))
    assert _run(runner) is RunnerOutcome.DONE


# --------------------------------------------------------------------------- #
# Retry semantics
# --------------------------------------------------------------------------- #

def test_retry_zero_means_one_attempt() -> None:
    spec = _spec(
        StepSpec("s0", "go_to", 10, retry=0, on_fail="skip", target="T1"),
        StepSpec("s1", "return_home", 10),
    )
    runner = MissionRunner(spec=spec, skills=_skills(["FAILURE"], ["SUCCESS"]))
    outcome = _run(runner)
    go_attempts = [r for r in runner.records if r.step_id == "s0" and r.attempt >= 1]
    assert len(go_attempts) == 1  # exactly one attempt
    assert outcome is RunnerOutcome.DONE  # on_fail=skip


def test_retry_two_means_three_attempts() -> None:
    spec = _spec(
        StepSpec("s0", "go_to", 10, retry=2, on_fail="fail", target="T1"),
        StepSpec("s1", "return_home", 10),
    )
    # Fails all 3 attempts -> on_fail=fail -> FAIL.
    runner = MissionRunner(spec=spec, skills=_skills(["FAILURE"], ["SUCCESS"]))
    outcome = _run(runner)
    assert outcome is RunnerOutcome.FAIL
    assert runner.terminal_reason.startswith("step_failed:s0")
    attempts = [r.attempt for r in runner.records if r.step_id == "s0" and r.attempt >= 1]
    assert attempts == [1, 2, 3]


def test_retry_then_success() -> None:
    spec = _spec(
        StepSpec("s0", "go_to", 10, retry=2, on_fail="fail", target="T1"),
        StepSpec("s1", "return_home", 10),
    )
    skills = _skills(["FAILURE", "FAILURE", "SUCCESS"], ["SUCCESS"])
    runner = MissionRunner(spec=spec, skills=skills)
    assert _run(runner) is RunnerOutcome.DONE
    outcomes = [r.outcome for r in runner.records if r.step_id == "s0" and r.attempt >= 1]
    assert outcomes == ["FAILURE", "FAILURE", "SUCCESS"]


# --------------------------------------------------------------------------- #
# on_fail skip vs fail
# --------------------------------------------------------------------------- #

def test_on_fail_skip_continues_to_next_step() -> None:
    spec = _spec(
        StepSpec("s0", "go_to", 10, retry=0, on_fail="skip", target="T1"),
        StepSpec("s1", "return_home", 10),
    )
    runner = MissionRunner(spec=spec, skills=_skills(["FAILURE"], ["SUCCESS"]))
    assert _run(runner) is RunnerOutcome.DONE
    # The failed step is recorded; the skip is recorded once (attempt=0).
    assert any(r.outcome == StepOutcome.SKIPPED.value for r in runner.records)


def test_on_fail_fail_stops_run() -> None:
    spec = _spec(
        StepSpec("s0", "go_to", 10, retry=0, on_fail="fail", target="T1"),
        StepSpec("s1", "return_home", 10),
    )
    runner = MissionRunner(spec=spec, skills=_skills(["FAILURE"], ["SUCCESS"]))
    assert _run(runner) is RunnerOutcome.FAIL
    # return_home never ran.
    assert all(r.step_id != "s1" for r in runner.records)


# --------------------------------------------------------------------------- #
# Timeouts
# --------------------------------------------------------------------------- #

def test_manager_forced_timeout() -> None:
    spec = _spec(
        StepSpec("s0", "go_to", 5, retry=0, on_fail="fail", target="T1"),
        StepSpec("s1", "return_home", 10),
    )
    # Skill never returns within the step timeout.
    skills = _skills(["SUCCESS"], ["SUCCESS"], go_dur=999.0)
    runner = MissionRunner(spec=spec, skills=skills)
    assert _run(runner) is RunnerOutcome.FAIL
    rec = next(r for r in runner.records if r.step_id == "s0")
    assert rec.outcome == StepOutcome.TIMEOUT.value
    assert rec.forced_by == "manager"
    assert rec.reason == "step timeout"


def test_skill_reported_timeout_is_marked_forced_by_skill() -> None:
    spec = _spec(
        StepSpec("s0", "go_to", 30, retry=0, on_fail="fail", target="T1"),
        StepSpec("s1", "return_home", 10),
    )
    runner = MissionRunner(spec=spec, skills=_skills(["TIMEOUT"], ["SUCCESS"]))
    assert _run(runner) is RunnerOutcome.FAIL
    rec = next(r for r in runner.records if r.step_id == "s0")
    assert rec.outcome == StepOutcome.TIMEOUT.value
    assert rec.forced_by == "skill"


# --------------------------------------------------------------------------- #
# Global deadline & return_home
# --------------------------------------------------------------------------- #

def test_global_deadline_fails_run() -> None:
    spec = _spec(
        StepSpec("s0", "go_to", 5, target="T1"),
        StepSpec("s1", "return_home", 100),
        time_limit_s=30,
        reserve=10,
    )
    skills = _skills(["SUCCESS"], ["SUCCESS"], go_dur=1.0, home_dur=100.0)
    runner = MissionRunner(spec=spec, skills=skills)
    outcome = _run(runner, dt=1.0)
    assert outcome is RunnerOutcome.FAIL
    assert runner.terminal_reason == "global_deadline_exceeded"


def test_unfinished_return_home_gets_timeout_incomplete_before_fail() -> None:
    spec = _spec(
        StepSpec("s0", "go_to", 5, target="T1"),
        StepSpec("s1", "return_home", 100),
        time_limit_s=30,
        reserve=10,
    )
    skills = _skills(["SUCCESS"], ["SUCCESS"], go_dur=1.0, home_dur=100.0)
    runner = MissionRunner(spec=spec, skills=skills)
    _run(runner, dt=1.0)
    home_recs = [r for r in runner.records if r.step_id == "s1"]
    assert len(home_recs) == 1
    rec = home_recs[0]
    assert rec.outcome == StepOutcome.TIMEOUT.value
    assert rec.incomplete is True
    assert rec.forced_by == "manager"


def test_return_home_failure_fails_run() -> None:
    spec = _spec(
        StepSpec("s0", "go_to", 10, target="T1"),
        StepSpec("s1", "return_home", 10),
    )
    runner = MissionRunner(spec=spec, skills=_skills(["SUCCESS"], ["FAILURE"]))
    assert _run(runner) is RunnerOutcome.FAIL
    assert runner.terminal_reason.startswith("step_failed:s1")


# --------------------------------------------------------------------------- #
# Time reserve
# --------------------------------------------------------------------------- #

def test_reserve_skips_remaining_and_returns_home() -> None:
    spec = _spec(
        StepSpec("s0", "go_to", 30, target="T1"),
        StepSpec("s1", "go_to", 20, on_fail="skip", target="T2"),
        StepSpec("s2", "return_home", 5),
        time_limit_s=30,
        reserve=10,
    )
    # s0 takes 22s -> at t=22 remaining=8 < reserve=10 -> reserve triggers.
    skills = _skills(["SUCCESS"], ["SUCCESS"], go_dur=22.0, home_dur=1.0)
    runner = MissionRunner(spec=spec, skills=skills)
    outcome = _run(runner, dt=1.0)
    assert outcome is RunnerOutcome.DONE
    s1 = next(r for r in runner.records if r.step_id == "s1")
    assert s1.outcome == StepOutcome.SKIPPED.value
    assert s1.reason == "reserve_reached"
    assert s1.incomplete is True
    # return_home ran and succeeded.
    assert any(r.step_id == "s2" and r.outcome == "SUCCESS" for r in runner.records)


def test_active_step_not_killed_at_reserve_boundary() -> None:
    # The reserve check happens between steps; a running step finishes first.
    spec = _spec(
        StepSpec("s0", "go_to", 30, target="T1"),
        StepSpec("s1", "return_home", 5),
        time_limit_s=30,
        reserve=10,
    )
    skills = _skills(["SUCCESS"], ["SUCCESS"], go_dur=22.0, home_dur=1.0)
    runner = MissionRunner(spec=spec, skills=skills)
    _run(runner, dt=1.0)
    s0 = next(r for r in runner.records if r.step_id == "s0")
    assert s0.outcome == StepOutcome.SUCCESS.value  # not skipped mid-run


def test_retry_not_started_when_it_would_eat_reserve() -> None:
    # time_limit=30, reserve=10; s0 timeout=25. A retry would need 25 more ->
    # remaining - timeout < reserve, so no retry; on_fail=fail -> FAIL.
    spec = _spec(
        StepSpec("s0", "go_to", 25, retry=3, on_fail="fail", target="T1"),
        StepSpec("s1", "return_home", 5),
        time_limit_s=30,
        reserve=10,
    )
    skills = _skills(["FAILURE"], ["SUCCESS"], go_dur=1.0)
    runner = MissionRunner(spec=spec, skills=skills)
    outcome = _run(runner, dt=1.0)
    # Only one attempt happened because a retry wouldn't fit.
    attempts = [r.attempt for r in runner.records if r.step_id == "s0" and r.attempt >= 1]
    assert attempts == [1]
    assert outcome is RunnerOutcome.FAIL


# --------------------------------------------------------------------------- #
# Abort / reset / health
# --------------------------------------------------------------------------- #

def test_abort_cancels_active_skill() -> None:
    spec = _spec(
        StepSpec("s0", "go_to", 100, target="T1"),
        StepSpec("s1", "return_home", 10),
    )
    skills = _skills(["SUCCESS"], ["SUCCESS"], go_dur=999.0)
    runner = MissionRunner(spec=spec, skills=skills)
    runner.start(0.0)
    runner.step_once(0.0)  # starts s0
    runner.abort("health:LiDAR")
    assert skills["go_to"].cancelled
    assert runner.terminal_outcome is RunnerOutcome.FAIL
    assert runner.terminal_reason.startswith("aborted:")


def test_reset_discards_run_state() -> None:
    spec = _spec(StepSpec("s0", "go_to", 10, target="T1"), StepSpec("s1", "return_home", 10))
    runner = MissionRunner(spec=spec, skills=_skills(["SUCCESS"], ["SUCCESS"]))
    _run(runner)
    runner.reset()
    assert runner.state is RunnerState.IDLE
    assert runner.records == []
    assert runner.terminal_outcome is None


# --------------------------------------------------------------------------- #
# Structured-log invariants
# --------------------------------------------------------------------------- #

def test_at_most_one_terminal_record_per_attempt() -> None:
    spec = _spec(
        StepSpec("s0", "go_to", 10, retry=2, on_fail="fail", target="T1"),
        StepSpec("s1", "return_home", 10),
    )
    runner = MissionRunner(spec=spec, skills=_skills(["FAILURE"], ["SUCCESS"]))
    _run(runner)
    terminal = {"SUCCESS", "FAILURE", "TIMEOUT", "ABORTED"}
    seen: set[tuple[str, int]] = set()
    for r in runner.records:
        if r.outcome in terminal and r.attempt >= 1:
            key = (r.step_id, r.attempt)
            assert key not in seen, f"duplicate terminal record {key}"
            seen.add(key)


def test_reserve_skipped_steps_have_one_record_each() -> None:
    spec = _spec(
        StepSpec("s0", "go_to", 30, target="T1"),
        StepSpec("s1", "go_to", 20, on_fail="skip", target="T2"),
        StepSpec("s2", "go_to", 20, on_fail="skip", target="T3"),
        StepSpec("s3", "return_home", 5),
        time_limit_s=30,
        reserve=10,
    )
    skills = _skills(["SUCCESS"], ["SUCCESS"], go_dur=22.0, home_dur=1.0)
    runner = MissionRunner(spec=spec, skills=skills)
    _run(runner, dt=1.0)
    for sid in ("s1", "s2"):
        recs = [r for r in runner.records if r.step_id == sid]
        assert len(recs) == 1
        assert recs[0].outcome == StepOutcome.SKIPPED.value


def test_structured_record_has_required_fields() -> None:
    spec = _spec(StepSpec("s0", "go_to", 10, target="T1"), StepSpec("s1", "return_home", 10))
    runner = MissionRunner(spec=spec, skills=_skills(["SUCCESS"], ["SUCCESS"]))
    _run(runner)
    rec = runner.records[0]
    for field in (
        "step_id", "skill", "attempt", "outcome", "reason", "mission_t0_s",
        "started_s", "finished_s", "duration_s", "incomplete",
    ):
        assert hasattr(rec, field)


# --------------------------------------------------------------------------- #
# Determinism
# --------------------------------------------------------------------------- #

def test_run_is_deterministic() -> None:
    def once():
        spec = _spec(
            StepSpec("s0", "go_to", 10, retry=1, on_fail="skip", target="T1"),
            StepSpec("s1", "return_home", 10),
        )
        runner = MissionRunner(spec=spec, skills=_skills(["FAILURE", "SUCCESS"], ["SUCCESS"]))
        outcome = _run(runner)
        return outcome, _records(runner)

    assert once() == once()
