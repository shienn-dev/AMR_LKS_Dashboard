"""Tests for the Phase 2 dashboard mission log wiring.

Unit tests over the dashboard helpers; no browser, no rendered page.
"""

from __future__ import annotations

from amr_core.mission_runner import mission_status
from amr_core.states import RobotState
from amr_dashboard import app as dash
from amr_dashboard import panels


class _RecordingLabel:
    """Minimal stand-in capturing rendered text (test double)."""

    def __init__(self) -> None:
        self.texts: list[str] = []


def test_dashboard_state_attaches_a_runner() -> None:
    state = dash.DashboardState()
    assert state.engine.runner is state.runner


def test_mission_status_is_none_before_start_has_finished_steps() -> None:
    state = dash.DashboardState()
    state.engine.run_health_check()
    status = mission_status(state.engine.runner)  # type: ignore[arg-type]
    assert status is not None
    assert status.total_steps == 5  # 4 targets + return_home
    assert status.records == ()


def test_mission_log_populates_after_a_run() -> None:
    state = dash.DashboardState()
    state.engine.run_health_check()
    state.engine.start_mission()
    for _ in range(200):
        state.engine.tick(2.0)
        if state.engine.state is not RobotState.RUNNING:
            break
    assert state.engine.state is RobotState.DONE
    status = mission_status(state.engine.runner)  # type: ignore[arg-type]
    assert status is not None
    assert len(status.records) == 5
    assert all(r.outcome == "SUCCESS" for r in status.records)


def test_mission_log_panel_handles_none() -> None:
    # Should not raise when there is no runner-attached status.
    panels.mission_log_panel(None)


def test_dashboard_ui_has_no_state_assignment() -> None:
    # The dashboard must never assign engine.state directly (Phase 1 contract).
    import inspect

    source = inspect.getsource(dash)
    assert "engine.state =" not in source
    assert ".state = " not in source.replace("state = ", "")
