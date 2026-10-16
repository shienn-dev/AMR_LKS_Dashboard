"""Mission YAML loader and validator (Phase 2).

Missions are data, not code. This module parses a mission document from a YAML
string into a :class:`~amr_core.mission.MissionSpec` and validates it. It never
executes code or evaluates dynamic expressions from the file; unsupported
dynamic expressions are *rejected*, not interpreted.

Error levels (each error is a :class:`ValidationIssue` whose ``field`` carries a
path prefix):

- ``document:`` — YAML syntax / wrong document shape.
- ``mission.<field>:`` — root mission fields.
- ``steps[i].<field>:`` — per-step fields.

The loader is deterministic and has no side effects on the filesystem here (it
parses a string); a thin file wrapper is provided for callers that have a path.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import yaml

from amr_core.mission import (
    ALLOWED_ON_FAIL,
    KNOWN_SKILLS,
    MAX_TIME_LIMIT_S,
    MIN_TIME_LIMIT_S,
    SAMPLE_TARGETS,
    SKILLS_REQUIRING_TARGET,
    MissionSpec,
    StepSpec,
    ValidationIssue,
)

# Only this start source is defined today (one physical button). Any other
# value is rejected so the schema stays honest.
ALLOWED_START = "physical_button"

# A token is treated as a dynamic expression if it contains these characters.
# The architecture's G2 examples (e.g. ``rack_for(obj.color)``) are dynamic and
# are not supported yet; they must be rejected rather than evaluated.
_DYNAMIC_MARKERS = ("(", ")")


def _is_dynamic(value: str) -> bool:
    return any(marker in value for marker in _DYNAMIC_MARKERS)


def load_mission_yaml(text: str) -> tuple[MissionSpec | None, list[ValidationIssue]]:
    """Parse and validate *text* as a mission document.

    Returns ``(spec, issues)``. On any error ``spec`` is None and ``issues`` is
    non-empty. Never raises for bad input (including malformed YAML).
    """
    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as exc:  # pragma: no cover - message text varies
        return None, [ValidationIssue("document", f"YAML parse error: {exc}")]

    if raw is None:
        return None, [ValidationIssue("document", "document is empty")]

    if not isinstance(raw, dict):
        return None, [ValidationIssue("document", "expected a mapping with mission metadata")]

    issues: list[ValidationIssue] = []

    mission_id = _require_str(raw, "mission", "mission", issues)
    version = _require_int(raw, "version", "mission", issues)
    time_limit_s = _require_int(raw, "time_limit_s", "mission", issues)
    reserve_for_home_s = _require_int(raw, "reserve_for_home_s", "mission", issues)

    start = raw.get("start", ALLOWED_START)
    if not isinstance(start, str) or start != ALLOWED_START:
        issues.append(
            ValidationIssue("mission.start", f"must be '{ALLOWED_START}' (got {start!r})")
        )

    if version is not None and version < 1:
        issues.append(ValidationIssue("mission.version", f"must be >= 1 (got {version})"))

    if time_limit_s is not None and not (MIN_TIME_LIMIT_S <= time_limit_s <= MAX_TIME_LIMIT_S):
        issues.append(
            ValidationIssue(
                "mission.time_limit_s",
                f"must be between {MIN_TIME_LIMIT_S} and {MAX_TIME_LIMIT_S} s "
                f"(got {time_limit_s})",
            )
        )

    if reserve_for_home_s is not None and reserve_for_home_s < 0:
        issues.append(
            ValidationIssue(
                "mission.reserve_for_home_s", f"must be >= 0 (got {reserve_for_home_s})"
            )
        )
    if (
        reserve_for_home_s is not None
        and time_limit_s is not None
        and reserve_for_home_s >= time_limit_s
    ):
        issues.append(
            ValidationIssue(
                "mission.reserve_for_home_s",
                f"must be smaller than time_limit_s ({time_limit_s})",
            )
        )

    steps = _parse_steps(raw.get("steps"), issues)

    if issues:
        return None, issues

    assert mission_id is not None and version is not None
    assert time_limit_s is not None and reserve_for_home_s is not None
    return (
        MissionSpec(
            mission_id=mission_id,
            version=version,
            time_limit_s=time_limit_s,
            reserve_for_home_s=reserve_for_home_s,
            steps=tuple(steps),
            start=start,
        ),
        [],
    )


def load_mission_file(path: str | Path) -> tuple[MissionSpec | None, list[ValidationIssue]]:
    """Read *path* and parse it as a mission document."""
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        return None, [ValidationIssue("document", f"cannot read file: {exc}")]
    return load_mission_yaml(text)


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #

def _require_str(
    raw: dict, key: str, prefix: str, issues: list[ValidationIssue]
) -> str | None:
    value = raw.get(key)
    if value is None:
        issues.append(ValidationIssue(f"{prefix}.{key}", "required field is missing"))
        return None
    if not isinstance(value, str) or not value.strip():
        issues.append(ValidationIssue(f"{prefix}.{key}", "must be a non-empty string"))
        return None
    return value


def _require_int(
    raw: dict, key: str, prefix: str, issues: list[ValidationIssue]
) -> int | None:
    value = raw.get(key)
    if value is None:
        issues.append(ValidationIssue(f"{prefix}.{key}", "required field is missing"))
        return None
    # bool is a subclass of int; reject it explicitly.
    if isinstance(value, bool) or not isinstance(value, int):
        issues.append(ValidationIssue(f"{prefix}.{key}", "must be an integer"))
        return None
    return value


def _parse_steps(raw_steps: object, issues: list[ValidationIssue]) -> list[StepSpec]:
    if raw_steps is None:
        issues.append(ValidationIssue("mission.steps", "required field is missing"))
        return []
    if not isinstance(raw_steps, list):
        issues.append(ValidationIssue("mission.steps", "must be a list of steps"))
        return []
    if not raw_steps:
        issues.append(ValidationIssue("mission.steps", "must contain at least one step"))
        return []

    steps: list[StepSpec] = []
    counter = 0
    for index, raw_step in enumerate(raw_steps):
        path = f"steps[{index}]"
        if not isinstance(raw_step, dict):
            issues.append(ValidationIssue(path, "must be a mapping"))
            continue

        # Normalize the architecture's for_each/do spelling into flat steps.
        expanded = _expand_step(raw_step, path, issues)
        for step in expanded:
            steps.append(replace(step, step_id=f"s{counter}"))
            counter += 1
    return steps


def _expand_step(
    raw_step: dict, path: str, issues: list[ValidationIssue]
) -> list[StepSpec]:
    """Normalize one raw step (flat or for_each) into 0+ StepSpec entries."""
    fields = dict(raw_step)

    # Accept the architecture's spelling: {for_each: {targets: [...]}, do: {...}}
    targets: list[str] | None = None
    if "for_each" in fields:
        fe = fields.pop("for_each")
        if not isinstance(fe, dict) or "targets" not in fe:
            issues.append(ValidationIssue(f"{path}.for_each", "must be a mapping with 'targets'"))
            return []
        raw_targets = fe["targets"]
        if not isinstance(raw_targets, list) or not raw_targets:
            issues.append(
                ValidationIssue(f"{path}.for_each.targets", "must be a non-empty list of points")
            )
            return []
        targets = []
        seen: set[str] = set()
        for j, t in enumerate(raw_targets):
            if not isinstance(t, str):
                issues.append(
                    ValidationIssue(f"{path}.for_each.targets[{j}]", "must be a known arena point")
                )
                continue
            if _is_dynamic(t):
                issues.append(
                    ValidationIssue(
                        f"{path}.for_each.targets[{j}]",
                        "dynamic expressions are not supported yet",
                    )
                )
                continue
            if t not in SAMPLE_TARGETS:
                issues.append(
                    ValidationIssue(
                        f"{path}.for_each.targets[{j}]", f"'{t}' is not a known arena point"
                    )
                )
                continue
            if t in seen:
                issues.append(
                    ValidationIssue(f"{path}.for_each.targets[{j}]", f"duplicate target '{t}'")
                )
                continue
            seen.add(t)
            targets.append(t)
        if "do" in fields:
            do = fields.pop("do")
            if not isinstance(do, dict):
                issues.append(ValidationIssue(f"{path}.do", "must be a mapping"))
                return []
            fields.update(do)

    elif "do" in fields:
        issues.append(ValidationIssue(f"{path}.do", "'do' requires a sibling 'for_each'"))

    base = _parse_single_step(fields, path, issues, targets_from_for_each=targets is not None)
    if base is None:
        return []

    if targets is None:
        return [base]
    # One expanded step per target.
    return [replace(base, target=t) for t in targets]


def _parse_single_step(
    fields: dict, path: str, issues: list[ValidationIssue], *, targets_from_for_each: bool = False
) -> StepSpec | None:
    ok = True

    skill = fields.get("skill")
    if not isinstance(skill, str) or not skill:
        issues.append(ValidationIssue(f"{path}.skill", "required field is missing"))
        ok = False
    elif skill not in KNOWN_SKILLS:
        issues.append(ValidationIssue(f"{path}.skill", f"unknown skill '{skill}'"))
        ok = False

    timeout_s = fields.get("timeout_s")
    if timeout_s is None:
        issues.append(ValidationIssue(f"{path}.timeout_s", "required field is missing"))
        ok = False
    elif isinstance(timeout_s, bool) or not isinstance(timeout_s, (int, float)):
        issues.append(ValidationIssue(f"{path}.timeout_s", "must be a number"))
        ok = False
    elif timeout_s <= 0:
        issues.append(ValidationIssue(f"{path}.timeout_s", f"must be > 0 (got {timeout_s})"))
        ok = False

    retry = fields.get("retry", 0)
    if isinstance(retry, bool) or not isinstance(retry, int):
        issues.append(ValidationIssue(f"{path}.retry", "must be an integer"))
        ok = False
    elif retry < 0:
        issues.append(ValidationIssue(f"{path}.retry", f"must be >= 0 (got {retry})"))
        ok = False

    on_fail = fields.get("on_fail", "fail")
    if on_fail not in ALLOWED_ON_FAIL:
        issues.append(
            ValidationIssue(f"{path}.on_fail", f"must be 'skip' or 'fail' (got {on_fail!r})")
        )
        ok = False

    target = fields.get("target")
    if target is not None and not isinstance(target, str):
        issues.append(ValidationIssue(f"{path}.target", "must be a string"))
        ok = False
    if isinstance(target, str) and _is_dynamic(target):
        issues.append(
            ValidationIssue(f"{path}.target", "dynamic expressions are not supported yet")
        )
        ok = False
    if (
        isinstance(skill, str)
        and skill in SKILLS_REQUIRING_TARGET
        and target is None
        and not targets_from_for_each
    ):
        issues.append(ValidationIssue(f"{path}.target", f"required for skill '{skill}'"))
        ok = False
    if isinstance(target, str) and not _is_dynamic(target) and target not in SAMPLE_TARGETS:
        issues.append(ValidationIssue(f"{path}.target", f"'{target}' is not a known arena point"))
        ok = False

    if not ok:
        return None

    assert isinstance(skill, str)
    assert isinstance(timeout_s, (int, float))
    assert isinstance(retry, int)
    return StepSpec(
        step_id="",  # assigned by the caller
        skill=skill,
        timeout_s=float(timeout_s),
        retry=retry,
        on_fail=on_fail,
        target=target if isinstance(target, str) else None,
    )
