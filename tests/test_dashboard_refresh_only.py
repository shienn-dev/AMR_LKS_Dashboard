"""Tests that the dashboard refresh never advances the runtime.

The per-page timer must only read state; only the single server-side loop may
advance the mission (``amr_dashboard.runtime``). Uses AST inspection so comment
text cannot produce false positives/negatives.
"""

from __future__ import annotations

import ast
import inspect

from amr_dashboard import app as dash


def _advancement_calls(func) -> list[str]:
    """Return dotted names of any advancement calls (``*.step``/``*.tick``)."""
    tree = ast.parse(inspect.getsource(func))
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = _call_name(node.func)
            if name.endswith(".step") or name.endswith(".tick") or name in {"step", "tick"}:
                found.append(name)
    return found


def _call_name(func: ast.expr) -> str:
    if isinstance(func, ast.Attribute):
        base = _call_name(func.value)
        return f"{base}.{func.attr}" if base else func.attr
    if isinstance(func, ast.Name):
        return func.id
    return ""


def test_on_tick_never_advances_the_runtime() -> None:
    assert _advancement_calls(dash._on_tick) == []


def test_main_page_never_advances_the_runtime() -> None:
    assert _advancement_calls(dash.main_page) == []


def test_app_module_has_no_direct_engine_tick_or_runtime_step_calls() -> None:
    # The startup hook delegates to the runtime module's loop; app.py itself
    # must not call engine.tick() nor runtime.step().
    tree = ast.parse(inspect.getsource(dash))
    dotted = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            dotted.append(_call_name(node.func))
    assert not any(n.endswith(".engine.tick") or n == "engine.tick" for n in dotted)
    assert not any(n.endswith(".runtime.step") or n == "runtime.step" for n in dotted)


def test_loop_advances_once_per_interval_via_injected_scheduler() -> None:
    from amr_dashboard import runtime as rt

    intervals: list[float] = []

    class _Timer:
        def cancel(self) -> None:
            pass

    def scheduler(interval: float, callback):
        intervals.append(interval)
        callback()  # simulate one interval firing
        return _Timer()

    runtime = rt.RobotRuntime()
    loop = rt.ServerRuntimeLoop(runtime, scheduler=scheduler)
    loop.start()
    assert runtime.ticks == 1  # exactly one advance for one interval
    assert intervals == [rt.TICK_INTERVAL_S]
