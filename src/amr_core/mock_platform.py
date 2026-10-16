"""Mock platform: deterministic clock and scripted skills (Phase 2).

No ROS 2, no hardware, no threads, no sleeps. Time is advanced explicitly by the
caller (the engine's ``tick(dt_s)``), so a run is a pure function of the mission
and the skill scripts.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from amr_core.skills import Skill, SkillContext, SkillResult, SkillStatus


@dataclass
class MissionClock:
    """A monotonic mission clock advanced explicitly (no sleeping)."""

    now_s: float = 0.0

    def advance(self, dt_s: float) -> float:
        if dt_s > 0:
            self.now_s += dt_s
        return self.now_s


@dataclass
class ScriptedSkill:
    """A skill whose behavior is a deterministic script.

    Each entry in ``script`` is a list of outcomes for successive attempts:
    ``"SUCCESS"``, ``"FAILURE"``, or ``"TIMEOUT"``. ``duration_s`` is how long
    each attempt takes (mission-clock seconds) before it returns its outcome.
    Attempts beyond the script length repeat the last entry.
    """

    name: str
    script: list[str] = field(default_factory=lambda: ["SUCCESS"])
    duration_s: float = 5.0

    _started_at: float | None = field(default=None, init=False)
    _attempt_index: int = field(default=0, init=False)
    _params: dict = field(default_factory=dict, init=False)
    _cancelled: bool = field(default=False, init=False)
    _emitted: bool = field(default=False, init=False)

    # -- Skill protocol ------------------------------------------------------

    def start(self, params: dict, ctx: SkillContext) -> None:
        self._params = dict(params)
        self._cancelled = False
        self._emitted = False
        self._started_at = None  # set on first poll

    def poll(self, now_s: float) -> SkillResult | None:
        if self._cancelled or self._emitted:
            return None
        if self._started_at is None:
            self._started_at = now_s
        if now_s - self._started_at < self.duration_s:
            return None
        self._emitted = True
        status = self._outcome_for_attempt(self._attempt_index)
        self._attempt_index += 1
        return SkillResult(status=status, reason=f"{self.name}:{status.value}")

    def cancel(self, reason: str) -> None:
        # Idempotent: a second cancel is a no-op.
        if self._cancelled:
            return
        self._cancelled = True
        self._emitted = True

    # -- test helpers --------------------------------------------------------

    @property
    def cancelled(self) -> bool:
        return self._cancelled

    def _outcome_for_attempt(self, index: int) -> SkillStatus:
        choice = self.script[index] if index < len(self.script) else self.script[-1]
        return SkillStatus(choice)


def default_skill_factory() -> dict[str, Skill]:
    """A fresh set of mock skills (one instance per skill name)."""
    return {
        "go_to": ScriptedSkill("go_to", script=["SUCCESS"], duration_s=5.0),
        "return_home": ScriptedSkill("return_home", script=["SUCCESS"], duration_s=5.0),
        "wait_for_start": ScriptedSkill("wait_for_start", script=["SUCCESS"], duration_s=0.1),
    }
