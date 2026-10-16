"""Simulated AMR core package (Phase 1 prototype).

This package holds the parts of the application that are *not* UI:
- the operational state machine model,
- the mission configuration model and its validator,
- the bounded simulation engine.

Everything here is pure Python and testable without NiceGUI, ROS 2, or hardware.
It is a Phase 1 prototype: no robot connection, no ROS 2 publishing.
"""

from amr_core.mission import (
    MissionConfig,
    MissionSpec,
    StepSpec,
    ValidationIssue,
    is_valid,
    spec_from_config,
    validate_mission,
)
from amr_core.mission_loader import load_mission_yaml
from amr_core.mission_runner import (
    MissionRunner,
    MissionStatus,
    RunnerOutcome,
    StepLogRecord,
    mission_status,
)
from amr_core.simulation import HealthChangeResult, LogEvent, SimulationEngine
from amr_core.skills import Skill, SkillContext, SkillResult, SkillStatus
from amr_core.states import Action, RobotState, TransitionResult, can_edit_mission, transition

__all__ = [
    "Action",
    "HealthChangeResult",
    "LogEvent",
    "MissionConfig",
    "MissionRunner",
    "MissionSpec",
    "MissionStatus",
    "RobotState",
    "RunnerOutcome",
    "SimulationEngine",
    "Skill",
    "SkillContext",
    "SkillResult",
    "SkillStatus",
    "StepLogRecord",
    "StepSpec",
    "TransitionResult",
    "ValidationIssue",
    "can_edit_mission",
    "is_valid",
    "load_mission_yaml",
    "mission_status",
    "spec_from_config",
    "transition",
    "validate_mission",
]
