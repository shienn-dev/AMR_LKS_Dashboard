"""Tests for the single server-side advancement loop.

Deterministic tests use an injected scheduler (no real timers, no sleeps). They
verify the *loop management* (start-once, idempotent, stop) — not just that
``RobotRuntime.step`` works.

A separate integration test (``test_runtime_lifecycle_integration.py``) starts a
real NiceGUI server to exercise the actual lifecycle.
"""

from __future__ import annotations

import pytest

from amr_dashboard import runtime as rt


class _FakeTimer:
    """A fake NiceGUI timer that the test drives manually."""

    def __init__(self, interval: float, callback) -> None:
        self.interval = interval
        self.callback = callback
        self.cancelled = False
        self.fire_count = 0

    def cancel(self) -> None:
        self.cancelled = True

    def fire(self) -> None:
        if not self.cancelled:
            self.callback()
            self.fire_count += 1


class _FakeScheduler:
    """Records created timers so tests can count loops."""

    def __init__(self) -> None:
        self.timers: list[_FakeTimer] = []

    def __call__(self, interval: float, callback):
        timer = _FakeTimer(interval, callback)
        self.timers.append(timer)
        return timer


@pytest.fixture
def fake_scheduler() -> _FakeScheduler:
    return _FakeScheduler()


def _loop(fake_scheduler: _FakeScheduler) -> rt.ServerRuntimeLoop:
    runtime = rt.RobotRuntime()
    return rt.ServerRuntimeLoop(runtime, scheduler=fake_scheduler)


# --------------------------------------------------------------------------- #
# Loop management
# --------------------------------------------------------------------------- #

def test_start_creates_exactly_one_timer(fake_scheduler: _FakeScheduler) -> None:
    loop = _loop(fake_scheduler)
    loop.start()
    assert len(fake_scheduler.timers) == 1
    assert loop.running


def test_start_is_idempotent(fake_scheduler: _FakeScheduler) -> None:
    loop = _loop(fake_scheduler)
    loop.start()
    loop.start()
    loop.start()
    assert len(fake_scheduler.timers) == 1  # never a second loop


def test_one_client_advances_once_per_interval(fake_scheduler: _FakeScheduler) -> None:
    loop = _loop(fake_scheduler)
    loop.start()
    timer = fake_scheduler.timers[0]
    before = loop.runtime.ticks
    timer.fire()
    assert loop.runtime.ticks == before + 1
    assert loop.advance_count == 1


def test_second_client_does_not_add_a_loop(fake_scheduler: _FakeScheduler) -> None:
    loop = _loop(fake_scheduler)
    loop.start()
    # A "second client" calling start again must not create another timer.
    loop.start()
    assert len(fake_scheduler.timers) == 1


def test_extra_clients_do_not_increase_advance_rate(fake_scheduler: _FakeScheduler) -> None:
    loop = _loop(fake_scheduler)
    loop.start()
    loop.start()  # client #2
    loop.start()  # client #3
    timer = fake_scheduler.timers[0]
    before = loop.runtime.ticks
    for _ in range(10):
        timer.fire()
    # 10 intervals -> exactly 10 advances, no matter how many "clients".
    assert loop.runtime.ticks == before + 10
    assert len(fake_scheduler.timers) == 1


def test_stop_cancels_the_loop(fake_scheduler: _FakeScheduler) -> None:
    loop = _loop(fake_scheduler)
    loop.start()
    timer = fake_scheduler.timers[0]
    loop.stop()
    assert timer.cancelled
    assert not loop.running


def test_stopped_loop_does_not_advance(fake_scheduler: _FakeScheduler) -> None:
    loop = _loop(fake_scheduler)
    loop.start()
    timer = fake_scheduler.timers[0]
    loop.stop()
    before = loop.runtime.ticks
    timer.fire()  # a late fire after cancel must not advance
    assert loop.runtime.ticks == before


def test_stop_is_safe_when_not_started(fake_scheduler: _FakeScheduler) -> None:
    loop = _loop(fake_scheduler)
    loop.stop()  # must not raise
    assert not loop.running


def test_restart_after_stop_creates_one_new_loop(fake_scheduler: _FakeScheduler) -> None:
    loop = _loop(fake_scheduler)
    loop.start()
    loop.stop()
    loop.start()
    assert len(fake_scheduler.timers) == 2  # one per start, but never concurrent
    assert fake_scheduler.timers[0].cancelled
    assert not fake_scheduler.timers[1].cancelled


# --------------------------------------------------------------------------- #
# Process-wide manager
# --------------------------------------------------------------------------- #

def test_get_server_loop_is_a_singleton() -> None:
    assert rt.get_server_loop() is rt.get_server_loop()


def test_start_server_loop_is_idempotent(fake_scheduler: _FakeScheduler, monkeypatch) -> None:
    # Inject the fake scheduler into the singleton manager.
    rt.reset_runtime()
    monkeypatch.setattr(rt, "_default_scheduler", fake_scheduler)
    loop = rt.start_server_loop()
    rt.start_server_loop()  # second client / duplicate startup
    assert len(fake_scheduler.timers) == 1
    assert loop.running
    rt.stop_server_loop()


def test_reset_runtime_stops_the_loop(fake_scheduler: _FakeScheduler, monkeypatch) -> None:
    rt.reset_runtime()
    monkeypatch.setattr(rt, "_default_scheduler", fake_scheduler)
    rt.start_server_loop()
    timer = fake_scheduler.timers[0]
    rt.reset_runtime()
    assert timer.cancelled


def test_shutdown_hook_stops_the_loop(fake_scheduler: _FakeScheduler, monkeypatch) -> None:
    from amr_dashboard import app as dash

    rt.reset_runtime()
    monkeypatch.setattr(rt, "_default_scheduler", fake_scheduler)
    rt.start_server_loop()
    handle = fake_scheduler.timers[0]

    # The app's on_shutdown hook must cancel the loop/task.
    dash._stop_runtime_loop()
    assert handle.cancelled
    assert rt.get_server_loop() is not None
    assert not rt.get_server_loop().running


def test_startup_hook_starts_exactly_one_loop(fake_scheduler: _FakeScheduler, monkeypatch) -> None:
    from amr_dashboard import app as dash

    rt.reset_runtime()
    monkeypatch.setattr(rt, "_default_scheduler", fake_scheduler)
    dash._start_runtime_loop()
    dash._start_runtime_loop()  # duplicate startup must be idempotent
    assert len(fake_scheduler.timers) == 1
