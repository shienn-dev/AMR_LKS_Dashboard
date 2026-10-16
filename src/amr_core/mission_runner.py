"""Mission runner: sequenced execution of a parsed mission (Phase 2).

The runner owns *sequencing* (which step runs, retry, skip, timeout, reserve
return-home) but NOT the application state. Application state stays in
:class:`~amr_core.simulation.SimulationEngine`; the engine calls
``runner.step_once(now_s)`` from its ``tick`` and maps the returned outcome to a
state transition.

Design guarantees (from the finalized Phase 2 design):

- Global deadline always wins.
- The reserve boundary is evaluated only at *step boundaries* (never mid-skill).
- A retry is only started if it fits inside the remaining budget without eating
  the reserve.
- Every attempt produces **at most one terminal record**.
- Every step skipped because of the reserve gets an explicit ``SKIPPED`` record
  (no silent loss).
- ``return_home`` that is unfinished at the deadline gets a terminal ``TIMEOUT``
  record with ``incomplete=True`` before the run becomes FAILED.
- Once the run enters RETURNING, it can only be DONE if ``return_home`` succeeds.

Everything is deterministic with an injected clock; no threads, no sleeps, no
ROS 2, no hardware.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from enum import Enum

from amr_core.mission import (
    ON_FAIL_SKIP,
    RETURN_HOME_SKILL,
    MissionSpec,
    StepSpec,
)
from amr_core.skills import Skill, SkillContext, SkillStatus


class RunnerState(str, Enum):
    """Internal runner phase (distinct from the application state)."""

    IDLE = "IDLE"
    RUNNING = "RUNNING"
    RETURNING = "RETURNING"
    FINISHED = "FINISHED"


class RunnerOutcome(str, Enum):
    """What the engine should do after a ``step_once`` call."""

    WAIT = "WAIT"
    DONE = "DONE"
    FAIL = "FAIL"


class StepOutcome(str, Enum):
    """Terminal outcome recorded for a step attempt."""

    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    TIMEOUT = "TIMEOUT"
    ABORTED = "ABORTED"
    SKIPPED = "SKIPPED"


@dataclass(frozen=True)
class StepLogRecord:
    """One structured mission-log entry (per attempt, or per skipped step).

    Distinct from the engine's human-readable event log: these are typed,
    mission-clock timestamped, and not capped at ``LOG_RETENTION``.
    """

    step_id: str
    skill: str
    attempt: int
    outcome: str
    reason: str
    forced_by: str | None = None
    mission_t0_s: float = 0.0
    started_s: float | None = None
    finished_s: float | None = None
    duration_s: float | None = None
    incomplete: bool = False


@dataclass
class _StepState:
    """Mutable per-step runtime bookkeeping."""

    spec: StepSpec
    attempt: int = 0
    started_s: float | None = None
    deadline_s: float | None = None
    terminated: bool = False


@dataclass
class MissionRunner:
    """Deterministic mission sequencer over a :class:`MissionSpec`."""

    spec: MissionSpec
    skills: Mapping[str, Skill]
    t0_s: float = 0.0
    log: Callable[[str], None] = lambda _msg: None

    state: RunnerState = RunnerState.IDLE
    records: list[StepLogRecord] = field(default_factory=list)
    terminal_reason: str = ""
    terminal_outcome: RunnerOutcome | None = None

    # runtime
    _index: int = 0
    _steps: list[_StepState] = field(default_factory=list, init=False)
    _return_index: int | None = field(default=None, init=False)
    _active: _StepState | None = field(default=None, init=False)

    def __post_init__(self) -> None:
        self._build_steps()

    def _build_steps(self) -> None:
        self._steps = [_StepState(spec=s) for s in self.spec.steps]
        self._return_index = None
        for i, s in enumerate(self._steps):
            if s.spec.skill == RETURN_HOME_SKILL:
                self._return_index = i
                break

    def configure(self, spec: MissionSpec) -> None:
        """Re-target the runner at a new spec and clear any run state."""
        self.spec = spec
        self.state = RunnerState.IDLE
        self.records = []
        self.terminal_reason = ""
        self.terminal_outcome = None
        self._index = 0
        self._active = None
        self._build_steps()

    # -- public API ----------------------------------------------------------

    def start(self, now_s: float) -> None:
        """Begin the run at mission-clock *now_s*."""
        self.t0_s = now_s
        self.state = RunnerState.RUNNING
        self._index = 0
        self._active = None

    def abort(self, reason: str) -> None:
        """Cancel the active skill and stop the run (external abort)."""
        if self._active is not None and not self._active.terminated:
            self._cancel_active(reason)
        self.terminal_reason = f"aborted:{reason}"
        self.terminal_outcome = RunnerOutcome.FAIL
        self.state = RunnerState.FINISHED

    def reset(self) -> None:
        """Discard all run state (used by the engine on START/RESET)."""
        self.state = RunnerState.IDLE
        self.records = []
        self.terminal_reason = ""
        self.terminal_outcome = None
        self._index = 0
        self._active = None
        self._steps = [_StepState(spec=s) for s in self.spec.steps]

    @property
    def return_home_completed(self) -> bool:
        """True if the mission had no return_home, or its return_home succeeded."""
        if self._return_index is None:
            return True
        s = self._steps[self._return_index]
        return s.terminated and any(
            r.step_id == s.spec.step_id and r.outcome == StepOutcome.SUCCESS.value
            for r in self.records
        )

    # -- main loop -----------------------------------------------------------

    def step_once(self, now_s: float) -> RunnerOutcome:
        """Advance the run by one manager step. Returns WAIT/DONE/FAIL."""
        if self.state is RunnerState.FINISHED:
            return self.terminal_outcome or RunnerOutcome.WAIT
        if self.state is RunnerState.IDLE:
            self.start(now_s)

        remaining = self.spec.time_limit_s - (now_s - self.t0_s)

        # (1) GLOBAL DEADLINE — always wins.
        if remaining <= 0:
            return self._fail(now_s, "global_deadline_exceeded")

        # (2) RESERVE at step boundary (not mid-skill). Only when no step is
        # actively running, so the active step is always allowed to finish.
        if (
            self.state is not RunnerState.RETURNING
            and self._active is None
            and remaining < self.spec.reserve_for_home_s
        ):
            return self._enter_return_home(now_s)

        # Advance past finished/skipped steps.
        if not self._ensure_active(now_s, remaining):
            if self._all_done():
                return self._finish(now_s, RunnerOutcome.DONE)
            return RunnerOutcome.WAIT

        step = self._active
        assert step is not None
        skill = self.skills[step.spec.skill]

        if step.started_s is None:
            step.started_s = now_s
            step.attempt += 1
            step.deadline_s = now_s + step.spec.timeout_s
            skill.start(self._params(step.spec), self._context())

        # (3) STEP TIMEOUT (manager-forced) — checked before reading a result.
        assert step.deadline_s is not None
        if now_s >= step.deadline_s:
            self._cancel_active("step timeout")
            self._record(
                step, StepOutcome.TIMEOUT, reason="step timeout",
                forced_by="manager", finished=now_s, started=step.started_s,
            )
            return self._after_attempt(now_s, remaining, step, StepOutcome.TIMEOUT)

        result = skill.poll(now_s)
        if result is None:
            return RunnerOutcome.WAIT

        outcome = _status_to_outcome(result.status)
        forced_by = "skill" if result.status is SkillStatus.TIMEOUT else None
        self._record(
            step, outcome, reason=result.reason, forced_by=forced_by,
            finished=now_s, started=step.started_s,
        )
        return self._after_attempt(now_s, remaining, step, outcome)

    # -- internals -----------------------------------------------------------

    def _ensure_active(self, now_s: float, remaining: float) -> bool:
        """Ensure ``self._active`` is a runnable step; return False if none."""
        while self._index < len(self._steps):
            step = self._steps[self._index]
            if not step.terminated:
                self._active = step
                return True
            self._index += 1
        self._active = None
        return False

    def _after_attempt(
        self, now_s: float, remaining: float, step: _StepState, outcome: StepOutcome
    ) -> RunnerOutcome:
        if outcome is StepOutcome.SUCCESS:
            step.terminated = True
            self._index += 1
            self._active = None
            if step.spec.skill == RETURN_HOME_SKILL:
                self.state = RunnerState.RETURNING
            if self._all_done():
                return self._finish(now_s, RunnerOutcome.DONE)
            return RunnerOutcome.WAIT

        if outcome is StepOutcome.ABORTED:
            step.terminated = True
            self._active = None
            return self._fail(now_s, f"aborted:{step.spec.skill}")

        # FAILURE or TIMEOUT: retry if it fits and attempts remain.
        if step.attempt < (1 + step.spec.retry) and self._retry_fits(remaining, step.spec):
            step.started_s = None  # next attempt restarts the skill
            step.deadline_s = None
            return RunnerOutcome.WAIT

        if step.spec.on_fail == ON_FAIL_SKIP:
            self._record_skip(step, reason="on_fail_skip")
            step.terminated = True
            self._index += 1
            self._active = None
            if step.spec.skill == RETURN_HOME_SKILL:
                # A skipped return_home cannot make the run DONE.
                return self._fail(now_s, "return_home_skipped")
            if self._all_done():
                return self._finish(now_s, RunnerOutcome.DONE)
            return RunnerOutcome.WAIT

        step.terminated = True
        self._active = None
        return self._fail(now_s, f"step_failed:{step.spec.step_id}:{step.spec.skill}")

    def _retry_fits(self, remaining: float, spec: StepSpec) -> bool:
        """A retry is allowed only if it does not eat the reserve budget."""
        return (remaining - spec.timeout_s) >= self.spec.reserve_for_home_s

    def _enter_return_home(self, now_s: float) -> RunnerOutcome:
        """Skip remaining not-started steps and activate return_home.

        Only steps with **no terminal record yet** get a ``SKIPPED`` record. A
        step that already produced a terminal record (e.g. a failed attempt) is
        simply closed without a duplicate record.
        """
        if self._return_index is None:
            self._fail(now_s, "global_deadline_exceeded")
            return self.terminal_outcome or RunnerOutcome.FAIL
        steps_with_records = {r.step_id for r in self.records}
        for i, step in enumerate(self._steps):
            if i == self._return_index or step.terminated:
                continue
            if step.spec.step_id not in steps_with_records:
                self._record_skip(step, reason="reserve_reached", reserve_blocked=True)
            step.terminated = True
        self.state = RunnerState.RETURNING
        self._index = self._return_index
        self._active = None
        self._ensure_active(now_s, 0.0)
        self.log("Reserve reached: skipping remaining tasks, returning home.")
        return RunnerOutcome.WAIT

    def _finish(self, now_s: float, outcome: RunnerOutcome) -> RunnerOutcome:
        # A run that entered RETURNING may only be DONE after return_home success.
        if outcome is RunnerOutcome.DONE and self.state is RunnerState.RETURNING:
            if not self.return_home_completed:
                return self._fail(now_s, "return_home_not_completed")
        elif outcome is RunnerOutcome.DONE and self._return_index is not None:
            # All steps succeeded (including return_home) -> confirm it ran.
            if not self.return_home_completed:
                return self._fail(now_s, "return_home_not_completed")
        self.state = RunnerState.FINISHED
        self.terminal_outcome = outcome
        return outcome

    def _fail(self, now_s: float, reason: str) -> RunnerOutcome:
        # If return_home is the active step and unfinished, close it with a
        # TIMEOUT record (incomplete=True) BEFORE the run becomes FAILED.
        if (
            self._active is not None
            and self._active.spec.skill == RETURN_HOME_SKILL
            and not self._active.terminated
        ):
            self._cancel_active(reason)
            self._record(
                self._active, StepOutcome.TIMEOUT, reason=reason, forced_by="manager",
                finished=now_s, started=self._active.started_s, incomplete=True,
            )
            self._active.terminated = True
        self.terminal_reason = reason
        self.terminal_outcome = RunnerOutcome.FAIL
        self.state = RunnerState.FINISHED
        return RunnerOutcome.FAIL

    def _cancel_active(self, reason: str) -> None:
        if self._active is None:
            return
        skill = self.skills[self._active.spec.skill]
        skill.cancel(reason)

    def _all_done(self) -> bool:
        return all(s.terminated for s in self._steps)

    def _params(self, spec: StepSpec) -> dict:
        params: dict = {}
        if spec.target is not None:
            params["target"] = spec.target
        return params

    def _context(self) -> SkillContext:
        return SkillContext(log=self.log, outputs={})

    # -- records -------------------------------------------------------------

    def _record(
        self,
        step: _StepState,
        outcome: StepOutcome,
        *,
        reason: str,
        forced_by: str | None = None,
        started: float | None,
        finished: float | None,
        incomplete: bool = False,
    ) -> None:
        duration = None
        if started is not None and finished is not None:
            duration = finished - started
        self.records.append(
            StepLogRecord(
                step_id=step.spec.step_id,
                skill=step.spec.skill,
                attempt=step.attempt,
                outcome=outcome.value,
                reason=reason,
                forced_by=forced_by,
                mission_t0_s=self.t0_s,
                started_s=started,
                finished_s=finished,
                duration_s=duration,
                incomplete=incomplete,
            )
        )
        # Also emit a one-line human-readable summary to the engine log.
        self.log(
            f"[{step.spec.step_id}] {step.spec.skill} attempt {step.attempt} "
            f"-> {outcome.value} ({reason})"
        )

    def _record_skip(
        self, step: _StepState, *, reason: str, reserve_blocked: bool = False
    ) -> None:
        self.records.append(
            StepLogRecord(
                step_id=step.spec.step_id,
                skill=step.spec.skill,
                attempt=0,
                outcome=StepOutcome.SKIPPED.value,
                reason=reason,
                forced_by=None,
                mission_t0_s=self.t0_s,
                started_s=None,
                finished_s=None,
                duration_s=None,
                incomplete=reserve_blocked,
            )
        )
        self.log(f"[{step.spec.step_id}] {step.spec.skill} -> SKIPPED ({reason})")


def _status_to_outcome(status: SkillStatus) -> StepOutcome:
    return {
        SkillStatus.SUCCESS: StepOutcome.SUCCESS,
        SkillStatus.FAILURE: StepOutcome.FAILURE,
        SkillStatus.TIMEOUT: StepOutcome.TIMEOUT,
        SkillStatus.ABORTED: StepOutcome.ABORTED,
    }[status]


@dataclass(frozen=True)
class MissionStatus:
    """Read-only view model the dashboard consumes (no mission logic in UI)."""

    active_step_id: str
    active_skill: str
    total_steps: int
    completed_steps: int
    terminal_reason: str
    records: tuple[StepLogRecord, ...]

    @property
    def progress_fraction(self) -> float:
        if self.total_steps == 0:
            return 0.0
        return min(1.0, self.completed_steps / self.total_steps)


def mission_status(runner: MissionRunner | None) -> MissionStatus | None:
    """Build a :class:`MissionStatus` from a runner, or None if no runner."""
    if runner is None:
        return None
    active = runner._active  # read-only peek for display
    completed = sum(1 for s in runner._steps if s.terminated)
    return MissionStatus(
        active_step_id=active.spec.step_id if active is not None else "-",
        active_skill=active.spec.skill if active is not None else "-",
        total_steps=len(runner._steps),
        completed_steps=completed,
        terminal_reason=runner.terminal_reason,
        records=tuple(runner.records),
    )
