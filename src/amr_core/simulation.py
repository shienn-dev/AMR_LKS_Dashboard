"""Bounded mission simulation engine.

Design rules (from the task brief and architecture doc):
- Explicit, testable state model. No arbitrary UI-only state changes.
- Deterministic where practical: given the same config and the same sequence of
  ``tick`` calls, the output is identical.
- No infinite background tasks. The engine owns no timer; the UI advances it.
- No hidden side effects: every mutation happens inside a documented method.

The engine wraps the operational state machine (``amr_core.states``) and adds
mission progress bookkeeping. It never touches ROS 2 or hardware.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from amr_core.interfaces import HEALTH_COMPONENTS
from amr_core.mission import MissionConfig, is_valid
from amr_core.states import Action, RobotState, TransitionResult, can_edit_mission, transition

# Retention: the maximum number of events kept in ``SimulationEngine.events``
# per engine instance. When the buffer exceeds this, the oldest events are
# dropped; the newest LOG_RETENTION events are always kept. Sequence numbers
# continue to increase regardless of trimming.
LOG_RETENTION = 1000


@dataclass(frozen=True)
class LogEvent:
    """A single event log entry, timestamped when it is *emitted*.

    - ``time`` is captured at emit time (not render time), so repeated UI
      renders show stable timestamps and cannot rewrite history.
    - ``seq`` is a per-instance monotonic sequence number. It never repeats and
      is never reset (not even by ``reset``), so the UI can use it as a stable
      cursor even after old events are trimmed from the buffer.
    """

    seq: int
    time: str
    message: str

    def render(self) -> str:
        return f"{self.time}  {self.message}"


@dataclass
class HealthStatus:
    """Readiness checklist state for one component."""

    key: str
    label: str
    critical: bool
    ok: bool

    @property
    def level(self) -> str:
        if self.ok:
            return "ok"
        return "fault" if self.critical else "warn"


@dataclass(frozen=True)
class HealthChangeResult:
    """Outcome of a simulated health change.

    ``transition`` is the state transition (if any) that the health change
    caused; ``allowed`` mirrors it for convenience.
    """

    component: str
    ok: bool
    transition: TransitionResult

    @property
    def changed_state(self) -> bool:
        return self.transition.changed

    @property
    def reason(self) -> str:
        return self.transition.reason


@dataclass
class StepRecord:
    """One completed mission step, for the run history and event log."""

    index: int
    name: str
    outcome: str


@dataclass
class SimulationEngine:
    """A bounded, pull-based mission simulation.

    Usage: ``engine.tick(dt_seconds)`` advances a running mission. The UI calls
    it from a bounded timer; tests call it directly with fixed steps.

    State transitions are owned by this class. UI code must not assign
    ``engine.state`` directly; it calls ``apply_health`` (or the mission
    methods) and reads the resulting state.
    """

    mission: MissionConfig | None = None
    state: RobotState = RobotState.BOOT
    elapsed_s: float = 0.0
    step_index: int = 0
    steps: list[str] = field(default_factory=list)
    history: list[StepRecord] = field(default_factory=list)
    health: dict[str, HealthStatus] = field(default_factory=dict)
    events: list[LogEvent] = field(default_factory=list)
    last_reason: str = ""
    # Monotonic sequence source for events. Never reset, so sequence numbers are
    # unique for the lifetime of the engine instance (requirement 3 and 7).
    _next_seq: int = 0
    # Boot lifecycle (F7). When True (default), the constructor completes the
    # health check, so the engine leaves BOOT immediately. When False, the
    # engine stays in BOOT after construction until ``run_health_check()`` is
    # called explicitly — a deterministic, sleep-free way for the UI to observe
    # BOOT before the check finishes.
    auto_check: bool = True
    _boot_completed: bool = False
    # Phase 2: an optional mission runner. When attached, ``tick`` delegates
    # mission advancement to it; when absent, the legacy synthetic cadence is
    # used (kept for backward compatibility with Phase 1 callers/tests).
    runner: object | None = None

    # -- setup ---------------------------------------------------------------

    def __post_init__(self) -> None:
        self._reset_health()
        self.log("Simulation started. No robot connected (simulated data only).")
        if self.auto_check:
            self.run_health_check()
        else:
            # Stay in BOOT: health initialized but not yet evaluated. The caller
            # must call run_health_check() to move to READY or FAULT.
            self.log("Boot: checking components (simulated)...")

    def _reset_health(self) -> None:
        self.health = {
            c.key: HealthStatus(key=c.key, label=c.label, critical=c.critical, ok=True)
            for c in HEALTH_COMPONENTS
        }

    # -- logging -------------------------------------------------------------

    def log(self, message: str) -> None:
        """Append an event, timestamped and sequenced at emit time.

        The buffer keeps at most ``LOG_RETENTION`` events; when it overflows the
        oldest are dropped. Sequence numbers keep increasing, so a UI cursor
        stays valid across trimming (requirement 2, 3, 7).
        """
        event = LogEvent(
            seq=self._next_seq,
            time=time.strftime("%H:%M:%S"),
            message=message,
        )
        self._next_seq += 1
        self.events.append(event)
        if len(self.events) > LOG_RETENTION:
            # Keep only the newest LOG_RETENTION events.
            del self.events[: len(self.events) - LOG_RETENTION]

    @property
    def latest_seq(self) -> int:
        """Sequence number of the most recently emitted event.

        Returns -1 when no event has been emitted yet, so a fresh reader can
        start its cursor at ``0`` and receive everything that is retained.
        """
        return self._next_seq - 1

    def events_since(self, seq: int) -> list[LogEvent]:
        """Return retained events with a sequence number strictly greater than *seq*.

        ``seq`` is a stable cursor (from ``LogEvent.seq``), not a list index, so
        it is unaffected by trimming old events. Returns oldest-first.
        """
        return [e for e in self.events if e.seq > seq]

    # -- health --------------------------------------------------------------

    def _critical_failures(self) -> list[HealthStatus]:
        return [h for h in self.health.values() if h.critical and not h.ok]

    def apply_health(self, key: str, ok: bool) -> HealthChangeResult:
        """Apply a simulated health change and the resulting state transition.

        This is the single public entry point for health-driven state changes,
        so transition ownership stays in the core layer (UI never assigns
        ``state`` directly).

        Behaviour:
        - The component's status is updated and logged (emit-time timestamp).
        - A critical failure is routed through the explicit transition table:
          BOOT/READY -> FAULT (pre-run, OPS-02); RUNNING -> FAILED (during a
          run, OPS-11).
        - Recovering a component does not move the robot out of FAULT/FAILED;
          that still requires an explicit RESET (see ``reset``).
        """
        if key not in self.health:
            raise KeyError(f"unknown component: {key}")

        item = self.health[key]
        if item.ok == ok:
            return HealthChangeResult(key, ok, TransitionResult(True, self.state, self.state))

        item.ok = ok
        self.log(f"Simulated health check: {item.label} -> {'OK' if ok else 'FAIL'}")

        result = TransitionResult(True, self.state, self.state)
        # While in BOOT the health check has not completed yet, so a change here
        # only updates the health map; the BOOT -> READY/FAULT decision belongs
        # to run_health_check(). All other states transition as documented.
        if self.state is not RobotState.BOOT and not ok and item.critical:
            # During a run (RUNNING -> FAILED, OPS-11), cancel the active skill
            # BEFORE the transition, exactly like ``tick`` does, so no skill is
            # left running after the mission is FAILED. The transition is
            # RUNNING -> FAILED only when the engine is RUNNING; for pre-run
            # states (READY -> FAULT, OPS-02) there is no mission running, so no
            # abort is needed. Only abort when a runner is attached and the run
            # actually started, to preserve behaviour without a runner.
            if self.state is RobotState.RUNNING and self.runner is not None:
                failures = self._critical_failures()
                names = ", ".join(h.label for h in failures)
                self.runner.abort(f"health:{names}")  # type: ignore[attr-defined]
            result = self._apply(Action.HEALTH_FAILED)
            if result.changed:
                self.last_reason = f"Critical component failed: {item.label}"
                self.log(
                    f"Critical component '{item.label}' failed. "
                    f"State -> {result.new_state.value}. Mission stopped."
                )
        return HealthChangeResult(key, ok, result)

    def run_health_check(self) -> TransitionResult:
        """Complete the boot health check and leave BOOT (idempotent).

        This is the public, explicit mechanism that separates engine
        construction from finishing boot. It is deterministic: no sleep, no
        timer, no randomness.

        - First call: evaluates the readiness checklist and moves BOOT -> READY
          (all critical components OK) or BOOT -> FAULT (any critical failure).
        - Later calls: no-op, returning the current state unchanged, so it is
          safe to call from a loop/tick without repeating the transition.
        """
        if self._boot_completed:
            return TransitionResult(True, self.state, self.state)
        self._boot_completed = True
        return self._run_health_check()

    def _run_health_check(self) -> TransitionResult:
        """Boot-time health check. Critical failure -> FAULT (architecture OPS-02)."""
        failures = self._critical_failures()
        if failures:
            names = ", ".join(h.label for h in failures)
            result = self._apply(Action.HEALTH_FAILED)
            self.log(f"Critical health check failed: {names}. State -> {self.state.value}.")
            self.last_reason = f"Critical component failed: {names}"
            return result
        result = self._apply(Action.HEALTH_PASSED)
        self.log("Health check passed. State -> READY.")
        return result

    # -- transitions ---------------------------------------------------------

    def _apply(self, action: Action) -> TransitionResult:
        result = transition(self.state, action)
        if result.allowed and result.changed:
            self.state = result.new_state
        elif not result.allowed:
            self.last_reason = result.reason
            self.log(f"Rejected action {action.value}: {result.reason}.")
        return result

    def can_edit_mission(self) -> bool:
        return can_edit_mission(self.state)

    def can_start(self) -> TransitionResult:
        """Whether a simulated START is currently allowed, without applying it.

        Combines the explicit transition table with the readiness requirement
        (a valid mission is configured). Used by the UI to enable/disable the
        START control and to explain a rejection.
        """
        if self.mission is None or not is_valid(self.mission):
            return TransitionResult(
                False,
                self.state,
                self.state,
                "Cannot START: mission configuration is missing or invalid.",
            )
        return transition(self.state, Action.START)

    def start_mission(self) -> TransitionResult:
        """Simulated START. Validates mission, then READY -> RUNNING."""
        check = self.can_start()
        if not check.allowed:
            self.last_reason = check.reason
            self.log(check.reason)
            return check

        mission = self.mission
        assert mission is not None  # guaranteed by can_start()
        result = self._apply(Action.START)
        if result.allowed:
            self.elapsed_s = 0.0
            self.step_index = 0
            self.history.clear()
            self.steps = list(mission.target_order) + ["return_home"]
            self._start_runner(mission)
            self.log(
                f"Simulated START accepted (software only, robot NOT actually "
                f"started). Mission '{mission.display_name}' RUNNING."
            )
        return result

    def complete_mission(self) -> TransitionResult:
        result = self._apply(Action.MISSION_COMPLETED)
        if result.allowed:
            self.log(f"Mission DONE in {self.elapsed_s:.0f} s.")
        return result

    def fail_mission(self, why: str = "simulated failure") -> TransitionResult:
        result = self._apply(Action.MISSION_FAILED)
        if result.allowed:
            self.last_reason = why
            self.log(f"Mission FAILED: {why}.")
        return result

    def reset(self) -> TransitionResult:
        """Explicit simulated RESET. Only valid from DONE/FAILED/STOPPED/FAULT.

        Recovery condition (applies to EVERY source state): a RESET cannot move
        the robot to READY while any critical component is still unhealthy.
        The rejection is returned and logged so the caller/UI can show why.
        """
        failures = self._critical_failures()
        if failures:
            names = ", ".join(h.label for h in failures)
            reason = f"RESET refused: {names} still failing. Fix and retry."
            self.last_reason = reason
            self.log(reason)
            return TransitionResult(False, self.state, self.state, reason)

        result = self._apply(Action.RESET)
        if result.allowed:
            # Cancel any active skill BEFORE the transition settles, so no skill
            # keeps running in READY (Phase 2 contract).
            self._abort_runner("reset")
            self.elapsed_s = 0.0
            self.step_index = 0
            self.history.clear()
            self.last_reason = ""
            self.log("Simulated RESET. State -> READY. Pose set to home (simulated).")
        return result

    # -- mission runner (Phase 2) -------------------------------------------

    def attach_runner(self, runner: object) -> None:
        """Attach a mission runner. ``tick`` then delegates advancement to it."""
        self.runner = runner

    def _start_runner(self, mission: MissionConfig) -> None:
        runner = self.runner
        if runner is None:
            return
        from amr_core.mission import spec_from_config

        spec = spec_from_config(mission)
        runner.configure(spec)  # type: ignore[attr-defined]
        runner.start(0.0)  # type: ignore[attr-defined]

    def _abort_runner(self, reason: str) -> None:
        runner = self.runner
        if runner is not None and getattr(runner, "state", None) is not None:
            runner.abort(reason)  # type: ignore[attr-defined]
            runner.reset()  # type: ignore[attr-defined]

    def _step_runner(self, dt_s: float) -> None:
        """Delegate advancement to the runner, mapping its outcome to state."""
        runner = self.runner
        self.elapsed_s += dt_s
        outcome = runner.step_once(self.elapsed_s)  # type: ignore[attr-defined]
        name = outcome.value if hasattr(outcome, "value") else str(outcome)
        if name == "DONE":
            self.complete_mission()
        elif name == "FAIL":
            self.fail_mission(runner.terminal_reason or "mission failed")  # type: ignore[attr-defined]

    # -- progress ------------------------------------------------------------

    @property
    def total_steps(self) -> int:
        return len(self.steps)

    @property
    def remaining_s(self) -> float:
        if self.mission is None:
            return 0.0
        return max(0.0, self.mission.time_limit_s - self.elapsed_s)

    @property
    def progress_fraction(self) -> float:
        if not self.steps:
            return 0.0
        return min(1.0, self.step_index / len(self.steps))

    @property
    def current_step(self) -> str:
        if self.state is not RobotState.RUNNING or self.step_index >= len(self.steps):
            return "-"
        return self.steps[self.step_index]

    def tick(self, dt_s: float) -> None:
        """Advance the simulation by *dt_s* seconds. Bounded per call.

        Only RUNNING advances. A critical component failure detected during the
        run stops the mission (state -> FAILED) before any further progress, per
        OPS-11. When a mission runner is attached, advancement is delegated to
        it; otherwise the legacy synthetic cadence is used.
        """
        if self.state is not RobotState.RUNNING or self.mission is None:
            return
        if dt_s <= 0:
            return

        # Run-time health re-check: never keep progressing with a failed
        # critical component. Cancel the active skill BEFORE the transition.
        failures = self._critical_failures()
        if failures:
            names = ", ".join(h.label for h in failures)
            if self.runner is not None:
                self.runner.abort(f"health:{names}")  # type: ignore[attr-defined]
            self._apply(Action.HEALTH_FAILED)
            self.last_reason = f"Critical component failed during run: {names}"
            self.log(f"Run stopped: critical component failed ({names}). Mission FAILED.")
            return

        if self.runner is not None:
            self._step_runner(dt_s)
            return

        self.elapsed_s += dt_s

        # Advance one step roughly every few seconds of simulated time.
        step_duration = max(2.0, self.mission.time_limit_s / max(1, self.total_steps * 8))
        while (
            self.step_index < self.total_steps
            and self.elapsed_s >= (self.step_index + 1) * step_duration
        ):
            name = self.steps[self.step_index]
            self.history.append(StepRecord(self.step_index, name, "SUCCESS"))
            self.log(f"Step {self.step_index + 1}/{self.total_steps}: {name} SUCCESS.")
            self.step_index += 1

        if self.step_index >= self.total_steps:
            self.complete_mission()
        elif self.remaining_s <= 0:
            self.fail_mission("time limit exceeded")
