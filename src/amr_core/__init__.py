"""Simulated AMR core package (Phase 1 prototype).

This package holds the parts of the application that are *not* UI:
- the operational state machine model,
- the mission configuration model and its validator,
- the bounded simulation engine.

Everything here is pure Python and testable without NiceGUI, ROS 2, or hardware.
It is a Phase 1 prototype: no robot connection, no ROS 2 publishing.
"""

from amr_core.mission import MissionConfig, ValidationIssue, is_valid, validate_mission
from amr_core.simulation import HealthChangeResult, LogEvent, SimulationEngine
from amr_core.states import Action, RobotState, TransitionResult, can_edit_mission, transition

__all__ = [
    "Action",
    "HealthChangeResult",
    "LogEvent",
    "MissionConfig",
    "RobotState",
    "SimulationEngine",
    "TransitionResult",
    "ValidationIssue",
    "can_edit_mission",
    "is_valid",
    "transition",
    "validate_mission",
]
