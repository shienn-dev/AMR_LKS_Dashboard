"""Tests for the server-side robot runtime (Opsi A).

These verify the architectural contracts that matter before deployment:

- mission execution is independent of any browser connection;
- two browser dashboards share the *same* runtime (not two engines);
- the runtime advances via ``step`` without any UI.

Unit tests only; no browser is started, no network is used.
"""

from __future__ import annotations

from amr_core.states import RobotState
from amr_dashboard import app as dash
from amr_dashboard.runtime import RobotRuntime, get_runtime, reset_runtime


def test_get_runtime_is_a_singleton() -> None:
    assert get_runtime() is get_runtime()


def test_reset_runtime_creates_a_fresh_instance() -> None:
    a = get_runtime()
    reset_runtime()
    b = get_runtime()
    assert a is not b


def test_runtime_boots_to_ready() -> None:
    rt = RobotRuntime()
    assert rt.engine.state is RobotState.BOOT
    rt.boot()
    assert rt.engine.state is RobotState.READY


def test_two_dashboard_states_share_the_same_engine() -> None:
    # A second browser page must see the same runtime, not a new engine.
    first = dash.DashboardState()
    second = dash.DashboardState()
    assert first.engine is second.engine
    assert first.runner is second.runner


def test_mission_advances_without_any_browser() -> None:
    # No DashboardState / page is ever created here: the runtime owns execution.
    rt = RobotRuntime()
    rt.boot()
    rt.engine.start_mission()
    assert rt.engine.state is RobotState.RUNNING

    for _ in range(200):
        rt.step(2.0)  # simulate the app-scope timer, no browser involved
        if rt.engine.state is not RobotState.RUNNING:
            break
    assert rt.engine.state is RobotState.DONE


def test_disconnect_does_not_reset_the_shared_engine() -> None:
    # Simulate a browser disconnect: a new page is created, but the shared
    # engine keeps its state (mission is not restarted or stopped).
    runtime = get_runtime()
    runtime.boot()
    runtime.engine.start_mission()
    runtime.step(2.0)
    state_before = runtime.engine.state

    # "Reconnect" -> a brand new DashboardState (fresh page).
    new_page = dash.DashboardState()
    assert new_page.engine is runtime.engine
    assert new_page.engine.state is state_before  # unchanged by the new page


def test_runtime_status_view_model() -> None:
    rt = RobotRuntime()
    rt.boot()
    rt.engine.start_mission()
    rt.step(2.0)
    status = rt.status()
    assert status is not None
    assert status.total_steps == 5
