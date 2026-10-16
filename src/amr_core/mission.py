"""Mission configuration model and validator.

Missions are data, not code (architecture principle #1). A mission has a name,
a version, a time limit, a reserved time for returning home, and steps. Steps
reference *skills* from the catalog; only registered expressions are allowed.

Phase 1 validates the subset needed by the dashboard prototype:
- the sample mission selected from a fixed list,
- a randomized target order,
- a rack-color configuration,
- required fields, types, and bounds.

Nothing here executes code from configuration.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Colors allowed in a rack slot. Kept small and explicit so the validator can
# reject anything else (matches VIS: 3 colors).
ALLOWED_COLORS: tuple[str, ...] = ("red", "green", "blue")

# A sample mission is a named preset. Target names must exist in the arena.
SAMPLE_TARGETS: tuple[str, ...] = ("T1", "T2", "T3", "T4")
SAMPLE_RACKS: tuple[str, ...] = ("rack_A", "rack_B", "rack_C")

MIN_TIME_LIMIT_S = 30
MAX_TIME_LIMIT_S = 600


@dataclass
class MissionConfig:
    """Validated mission configuration shown and edited by the dashboard.

    All values are *simulated sample data* in Phase 1.
    """

    mission_id: str
    version: int
    time_limit_s: int
    reserve_for_home_s: int
    target_order: list[str] = field(default_factory=list)
    rack_colors: dict[str, str] = field(default_factory=dict)

    @property
    def display_name(self) -> str:
        return self.mission_id

    def copy(self) -> MissionConfig:
        """Return an independent copy of this configuration.

        The mutable fields (``target_order``, ``rack_colors``) are copied too, so
        later edits to either object never affect the other. This is the
        primitive used to promote an edited draft to the active mission.
        """
        return MissionConfig(
            mission_id=self.mission_id,
            version=self.version,
            time_limit_s=self.time_limit_s,
            reserve_for_home_s=self.reserve_for_home_s,
            target_order=list(self.target_order),
            rack_colors=dict(self.rack_colors),
        )


@dataclass(frozen=True)
class ValidationIssue:
    """A single validation error with a human-readable message."""

    field: str
    message: str

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"{self.field}: {self.message}"


def validate_mission(config: MissionConfig) -> list[ValidationIssue]:
    """Validate a mission configuration.

    Returns a (possibly empty) list of issues. Empty list means valid. This
    function never mutates *config* and never raises for bad user input.
    """
    issues: list[ValidationIssue] = []

    if not config.mission_id or not config.mission_id.strip():
        issues.append(ValidationIssue("mission_id", "Mission must be selected."))

    if config.version < 1:
        issues.append(ValidationIssue("version", "Version must be >= 1."))

    if not (MIN_TIME_LIMIT_S <= config.time_limit_s <= MAX_TIME_LIMIT_S):
        issues.append(
            ValidationIssue(
                "time_limit_s",
                f"Time limit must be between {MIN_TIME_LIMIT_S} and {MAX_TIME_LIMIT_S} s.",
            )
        )

    if config.reserve_for_home_s < 0:
        issues.append(ValidationIssue("reserve_for_home_s", "Reserve time must be >= 0 s."))

    if config.reserve_for_home_s >= config.time_limit_s:
        issues.append(
            ValidationIssue(
                "reserve_for_home_s",
                "Reserve time for home must be smaller than the time limit.",
            )
        )

    issues.extend(_validate_target_order(config.target_order))
    issues.extend(_validate_rack_colors(config.rack_colors))

    return issues


def _validate_target_order(order: list[str]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if not order:
        issues.append(ValidationIssue("target_order", "Target order cannot be empty."))
        return issues
    unknown = [t for t in order if t not in SAMPLE_TARGETS]
    if unknown:
        issues.append(
            ValidationIssue("target_order", f"Unknown targets: {', '.join(unknown)}.")
        )
    if len(set(order)) != len(order):
        issues.append(ValidationIssue("target_order", "Target order has duplicates."))
    return issues


def _validate_rack_colors(colors: dict[str, str]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if not colors:
        issues.append(ValidationIssue("rack_colors", "At least one rack must be configured."))
        return issues
    for rack, color in colors.items():
        if rack not in SAMPLE_RACKS:
            issues.append(ValidationIssue("rack_colors", f"Unknown rack: {rack}."))
        if color not in ALLOWED_COLORS:
            issues.append(
                ValidationIssue(
                    "rack_colors",
                    f"Rack {rack} has invalid color '{color}' "
                    f"(allowed: {', '.join(ALLOWED_COLORS)}).",
                )
            )
    return issues


def is_valid(config: MissionConfig) -> bool:
    return not validate_mission(config)


# --------------------------------------------------------------------------- #
# Phase 2 — mission spec (parsed mission with steps)
# --------------------------------------------------------------------------- #
#
# ``MissionConfig`` above stays the Phase 1 configuration object used by the
# dashboard draft. ``MissionSpec`` is the Phase 2 parsed form consumed by the
# mission runner. It is additive: nothing in Phase 1 depends on it.

# Skills known to the mock runner. Values are the skill names allowed in a
# mission file. Kept small and explicit; real skills are added to the
# architecture catalogue first, then here.
KNOWN_SKILLS: tuple[str, ...] = ("go_to", "return_home", "wait_for_start")

# Skills that require a ``target`` point.
SKILLS_REQUIRING_TARGET: tuple[str, ...] = ("go_to",)

# Allowed ``on_fail`` values.
ON_FAIL_SKIP = "skip"
ON_FAIL_FAIL = "fail"
ALLOWED_ON_FAIL: tuple[str, ...] = (ON_FAIL_SKIP, ON_FAIL_FAIL)

# Reserved skill name for returning home; the runner prioritizes this step.
RETURN_HOME_SKILL = "return_home"


@dataclass(frozen=True)
class StepSpec:
    """One parsed mission step (a single executable action).

    ``retry`` is the number of *additional* attempts after the first, so
    ``retry=0`` means one attempt, ``retry=1`` two, etc.
    """

    step_id: str
    skill: str
    timeout_s: float
    retry: int = 0
    on_fail: str = ON_FAIL_FAIL
    target: str | None = None


@dataclass(frozen=True)
class MissionSpec:
    """A parsed, validated mission ready for the runner."""

    mission_id: str
    version: int
    time_limit_s: int
    reserve_for_home_s: int
    steps: tuple[StepSpec, ...]
    start: str = "physical_button"

    @property
    def display_name(self) -> str:
        return self.mission_id


def spec_from_config(config: MissionConfig, *, default_timeout_s: float = 90.0) -> MissionSpec:
    """Build a runnable :class:`MissionSpec` from a Phase 1 :class:`MissionConfig`.

    The dashboard's sample missions carry a target order and rack colors but no
    per-step timeout/retry (that lives in the mission YAML of the real system).
    This adapter turns the target order into ``go_to`` steps followed by a
    ``return_home`` step, using a default step timeout. It is a *compatibility*
    adapter for the mock; the YAML loader is the real source of ``MissionSpec``.
    """
    steps: list[StepSpec] = []
    for i, target in enumerate(config.target_order):
        steps.append(
            StepSpec(
                step_id=f"s{i}",
                skill="go_to",
                timeout_s=default_timeout_s,
                retry=0,
                on_fail=ON_FAIL_FAIL,
                target=target,
            )
        )
    steps.append(
        StepSpec(
            step_id=f"s{len(steps)}",
            skill=RETURN_HOME_SKILL,
            timeout_s=default_timeout_s,
            retry=0,
            on_fail=ON_FAIL_FAIL,
        )
    )
    return MissionSpec(
        mission_id=config.mission_id,
        version=config.version,
        time_limit_s=config.time_limit_s,
        reserve_for_home_s=config.reserve_for_home_s,
        steps=tuple(steps),
    )
