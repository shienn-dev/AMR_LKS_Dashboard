"""Skill contract for the mock mission runner (Phase 2).

A skill performs exactly one action and always returns one of four statuses plus
a reason, mirroring the architecture: ``SUCCESS | FAILURE | TIMEOUT | ABORTED``.

Two timeouts are deliberately distinguished:

- **Skill-reported TIMEOUT** — the skill's own control loop reached its internal
  deadline and returned ``TIMEOUT`` by itself.
- **Manager-forced TIMEOUT** — the mission manager reached ``step.timeout_s``
  first, calls :meth:`Skill.cancel`, and records the outcome itself. The skill
  is *not* expected to have returned.

Nothing here touches ROS 2 or hardware. The interface is pull-based so the
manager stays deterministic (an injected clock advances time; there are no
threads and no sleeps).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol


class SkillStatus(str, Enum):
    """The four terminal statuses a skill can report."""

    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    TIMEOUT = "TIMEOUT"   # the skill's own deadline
    ABORTED = "ABORTED"   # stopped from outside (manager/health/reset)


@dataclass(frozen=True)
class SkillResult:
    """A skill outcome plus a human-readable reason and optional outputs."""

    status: SkillStatus
    reason: str = ""
    output: dict = field(default_factory=dict)


@dataclass
class SkillContext:
    """Read-only services a skill may use. Deliberately does NOT expose the
    mission manager (skills never call other skills or the manager).
    """

    log: Callable[[str], None]
    outputs: dict = field(default_factory=dict)
    # ``arena_points`` would live here once arena.yaml exists; unused in Phase 2.


class Skill(Protocol):
    """Protocol every skill implements.

    ``poll`` returns ``None`` while still running, or a terminal
    :class:`SkillResult` once. After a terminal result or ``cancel`` a skill
    must not emit a second result.
    """

    name: str

    def start(self, params: dict, ctx: SkillContext) -> None: ...

    def poll(self, now_s: float) -> SkillResult | None: ...

    def cancel(self, reason: str) -> None: ...
