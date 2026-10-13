"""Regression tests for Phase 1.2 — mission draft isolation.

The dashboard edits a *draft* mission configuration in `DashboardState.draft`,
which must be a separate object from the engine's *active* mission
(`engine.mission`). Edits stay in the draft until "Validate & apply" promotes an
independent copy to the active mission.

Core tests exercise `MissionConfig.copy()` and validation. UI tests exercise the
actual `amr_dashboard.app` callback functions directly (they are plain
functions; `ui.notify` is callable outside a running server and is not asserted
here). These are unit-level tests of callback logic, not browser/end-to-end UI
tests.
"""

from __future__ import annotations

from amr_core.mission import MissionConfig, is_valid, validate_mission
from amr_core.states import RobotState
from amr_dashboard import app as dash


def _state() -> dash.DashboardState:
    """A fresh dashboard state (draft and active mission are separate objects).

    Completes the simulated boot check so the engine is in READY, matching the
    state in which mission editing happens (the UI runs the check on the first
    tick).
    """
    state = dash.DashboardState()
    state.engine.run_health_check()
    return state


def _active(state: dash.DashboardState) -> MissionConfig:
    """The active mission, asserted non-None (always set after construction)."""
    mission = state.engine.mission
    assert mission is not None
    return mission


# --------------------------------------------------------------------------- #
# Core: MissionConfig.copy() isolation
# --------------------------------------------------------------------------- #

def _config() -> MissionConfig:
    return MissionConfig(
        mission_id="modul_E",
        version=1,
        time_limit_s=600,
        reserve_for_home_s=60,
        target_order=["T3", "T1", "T4", "T2"],
        rack_colors={"rack_A": "red", "rack_B": "green", "rack_C": "blue"},
    )


def test_copy_is_a_different_object() -> None:
    original = _config()
    clone = original.copy()
    assert clone is not original


def test_copy_has_equal_field_values() -> None:
    original = _config()
    clone = original.copy()
    assert clone.mission_id == original.mission_id
    assert clone.version == original.version
    assert clone.time_limit_s == original.time_limit_s
    assert clone.reserve_for_home_s == original.reserve_for_home_s
    assert clone.target_order == original.target_order
    assert clone.rack_colors == original.rack_colors


def test_copy_mutable_fields_are_independent_lists_and_dicts() -> None:
    original = _config()
    clone = original.copy()
    assert clone.target_order is not original.target_order
    assert clone.rack_colors is not original.rack_colors


def test_editing_copy_does_not_change_original() -> None:
    original = _config()
    clone = original.copy()
    clone.target_order[0] = "T9"
    clone.rack_colors["rack_A"] = "green"
    clone.time_limit_s = 30
    assert original.target_order == ["T3", "T1", "T4", "T2"]
    assert original.rack_colors["rack_A"] == "red"
    assert original.time_limit_s == 600


# --------------------------------------------------------------------------- #
# Draft and active mission are separate objects
# --------------------------------------------------------------------------- #

def test_state_draft_is_not_active_mission_object() -> None:
    state = _state()
    active = _active(state)
    assert state.draft is not active
    assert state.draft.target_order is not active.target_order
    assert state.draft.rack_colors is not active.rack_colors


def test_state_starts_with_equal_draft_and_active() -> None:
    state = _state()
    active = _active(state)
    assert state.draft.target_order == active.target_order
    assert state.draft.rack_colors == active.rack_colors


# --------------------------------------------------------------------------- #
# Editing the draft does not change the active mission (before Apply)
# --------------------------------------------------------------------------- #

def test_editing_field_does_not_change_active_mission() -> None:
    state = _state()
    active_before = _active(state).time_limit_s
    dash._set_field(state, "time_limit_s", 123)
    assert state.draft.time_limit_s == 123
    assert _active(state).time_limit_s == active_before


def test_editing_target_does_not_change_active_mission() -> None:
    state = _state()
    active_before = list(_active(state).target_order)
    dash._set_target(state, 0, "T2")
    assert state.draft.target_order[0] == "T2"
    assert _active(state).target_order == active_before


def test_editing_rack_does_not_change_active_mission() -> None:
    state = _state()
    active_before = dict(_active(state).rack_colors)
    dash._set_rack(state, "rack_A", "green")
    assert state.draft.rack_colors["rack_A"] == "green"
    assert _active(state).rack_colors == active_before


def test_randomize_does_not_change_active_mission() -> None:
    state = _state()
    active_before = list(_active(state).target_order)
    dash._randomize(state)
    # Draft may or may not change (deterministic rng), but active is untouched.
    assert _active(state).target_order == active_before


def test_change_mission_does_not_change_active_mission() -> None:
    state = _state()
    active_before = _active(state).mission_id
    dash._change_mission(state, "G2")
    assert state.draft.mission_id == "G2"
    assert _active(state).mission_id == active_before


# --------------------------------------------------------------------------- #
# Invalid draft does not change the active mission
# --------------------------------------------------------------------------- #

def test_invalid_draft_apply_does_not_change_active_mission() -> None:
    state = _state()
    active_before = list(_active(state).target_order)
    # Make the draft invalid (duplicate target).
    state.draft.target_order = ["T1", "T1"]
    assert not is_valid(state.draft)

    dash._validate_apply(state)

    assert _active(state).target_order == active_before
    assert is_valid(_active(state))  # active mission is still valid


def test_invalid_draft_is_kept_for_fixing() -> None:
    state = _state()
    state.draft.target_order = ["T1", "T1"]
    dash._validate_apply(state)
    # Draft is unchanged (still invalid, still available for the operator).
    assert state.draft.target_order == ["T1", "T1"]
    issues = validate_mission(state.draft)
    assert issues  # clear reason available to show in the UI


def test_invalid_draft_with_bad_color_not_applied() -> None:
    state = _state()
    active_before = dict(_active(state).rack_colors)
    state.draft.rack_colors = {"rack_A": "purple"}
    dash._validate_apply(state)
    assert _active(state).rack_colors == active_before


# --------------------------------------------------------------------------- #
# Valid draft is applied only after Apply
# --------------------------------------------------------------------------- #

def test_valid_draft_not_applied_before_apply() -> None:
    state = _state()
    state.draft.time_limit_s = 500
    assert _active(state).time_limit_s != 500  # not yet applied


def test_valid_draft_applied_after_apply() -> None:
    state = _state()
    state.draft.time_limit_s = 500
    dash._validate_apply(state)
    assert _active(state).time_limit_s == 500


def test_apply_promotes_an_independent_copy() -> None:
    state = _state()
    state.draft.time_limit_s = 500
    dash._validate_apply(state)
    active = _active(state)
    assert active is not state.draft
    assert active.target_order is not state.draft.target_order
    assert active.rack_colors is not state.draft.rack_colors


def test_editing_draft_after_apply_does_not_change_active_retroactively() -> None:
    state = _state()
    state.draft.time_limit_s = 500
    dash._validate_apply(state)
    applied_targets = list(_active(state).target_order)
    assert _active(state).time_limit_s == 500

    # Later edits to the draft must not leak into the applied active mission.
    dash._set_field(state, "time_limit_s", 300)
    dash._set_target(state, 0, "T2" if state.draft.target_order[0] != "T2" else "T1")
    dash._set_rack(state, "rack_A", "green")
    assert _active(state).time_limit_s == 500
    assert _active(state).target_order == applied_targets
    assert is_valid(_active(state))


# --------------------------------------------------------------------------- #
# START still rejects an invalid active mission; lock intact during RUNNING
# --------------------------------------------------------------------------- #

def test_start_rejects_when_active_mission_invalid() -> None:
    state = _state()
    # Force an invalid *active* mission directly (simulating a bad applied state).
    _active(state).target_order = ["T1", "T1"]
    check = state.engine.can_start()
    assert not check.allowed


def test_start_allowed_with_valid_active_mission() -> None:
    state = _state()
    assert state.engine.can_start().allowed


def test_start_runs_only_with_active_mission_not_draft() -> None:
    state = _state()
    # Make the draft invalid but leave the active mission valid.
    state.draft.target_order = ["T1", "T1"]
    assert state.engine.can_start().allowed  # active mission is what matters
    result = state.engine.start_mission()
    assert result.allowed
    assert state.engine.state is RobotState.RUNNING


def test_mission_editing_locked_while_running() -> None:
    state = _state()
    state.engine.start_mission()
    assert state.engine.state is RobotState.RUNNING
    assert not state.engine.can_edit_mission()

    # Locked editors must leave the draft untouched (engine lock check).
    before = state.draft.time_limit_s
    dash._set_field(state, "time_limit_s", 123)
    assert state.draft.time_limit_s == before


def test_validate_apply_locked_while_running() -> None:
    state = _state()
    active_before = _active(state).time_limit_s
    state.engine.start_mission()
    state.draft.time_limit_s = 500
    dash._validate_apply(state)  # must be refused by the RUNNING lock
    assert _active(state).time_limit_s == active_before
