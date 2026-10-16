"""Server-side robot runtime (Opsi A).

The robot runtime owns the single ``SimulationEngine`` and its ``MissionRunner``
for the whole server process. It is **independent of any browser**: the
advancement loop is driven by a timer registered at app startup, not by the
per-page rendering. Disconnecting a browser therefore cannot stop a mission.

Design notes:
- This is the *deployment target* architecture (server on the robot, browser on
  the operator's laptop/phone). It has **not** been validated on a Raspberry Pi;
  the same code runs on a laptop for testing.
- Mission logic lives in ``amr_core``; this module only owns wiring and the
  advancement loop. It never assigns ``engine.state`` directly.
"""

from __future__ import annotations

import random
from collections.abc import Callable
from dataclasses import dataclass, field

from amr_core.mission import MissionConfig, spec_from_config
from amr_core.mission_runner import MissionRunner, MissionStatus, mission_status
from amr_core.mock_platform import default_skill_factory
from amr_core.samples import SAMPLE_MISSIONS, get_sample_mission
from amr_core.simulation import SimulationEngine

# Simulated seconds advanced per tick (bounded, deterministic).
TICK_DT_S = 2.0
# Wall-clock interval of the single server-side advancement loop.
TICK_INTERVAL_S = 0.5


@dataclass
class RobotRuntime:
    """The single robot runtime for the server process.

    ``step`` advances the mission by a bounded amount; it is called by the
    server-side timer. Tests call ``step`` directly (no timer, no browser).
    """

    rng: random.Random = field(default_factory=lambda: random.Random(2026))
    engine: SimulationEngine = field(default_factory=lambda: SimulationEngine(auto_check=False))
    mission: MissionConfig | None = None
    runner: MissionRunner | None = None
    ticks: int = 0

    def __post_init__(self) -> None:
        first = get_sample_mission(SAMPLE_MISSIONS[0].mission_id)
        assert first is not None
        self.mission = first.sample_config(self.rng)
        self.engine.mission = self.mission
        self.runner = MissionRunner(
            spec=spec_from_config(self.mission),
            skills=default_skill_factory(),
            log=self.engine.log,
        )
        self.engine.attach_runner(self.runner)

    # -- lifecycle -----------------------------------------------------------

    def boot(self) -> None:
        """Complete the boot health check (idempotent)."""
        self.engine.run_health_check()

    def step(self, dt_s: float = TICK_DT_S) -> None:
        """Advance one bounded tick. Called by the server-side timer or tests."""
        self.engine.run_health_check()
        self.engine.tick(dt_s)
        self.ticks += 1

    # -- read-only view ------------------------------------------------------

    def status(self) -> MissionStatus | None:
        return mission_status(self.runner)


# Module-level singleton for the server process. It exists independently of any
# client/page. Tests may construct their own RobotRuntime instances.
_runtime: RobotRuntime | None = None


def get_runtime() -> RobotRuntime:
    """Return the process-wide runtime, creating it on first use."""
    global _runtime
    if _runtime is None:
        _runtime = RobotRuntime()
    return _runtime


def reset_runtime() -> None:
    """Discard the process-wide runtime and stop its loop (used by tests)."""
    global _runtime
    stop_server_loop()
    _runtime = None


# --------------------------------------------------------------------------- #
# Single server-side advancement loop
# --------------------------------------------------------------------------- #
#
# There must be exactly ONE advancement loop per application process. This
# manager owns it: ``start`` is idempotent (a second client, a page refresh, or
# a duplicate startup hook cannot create a second loop), and ``stop`` cancels it
# for clean shutdown. The dashboard's per-page timer only reads state; it never
# advances the runtime.
#
# IMPORTANT (NiceGUI 3.18): a ``ui.timer`` created with no client never fires.
# The server-wide loop is therefore an asyncio task on the application event
# loop, created inside ``app.on_startup`` (where the loop is running).

Scheduler = Callable[[float, Callable[[], None]], object]


async def _advance_forever(interval_s: float, callback: Callable[[], None]) -> None:
    import asyncio

    while True:
        await asyncio.sleep(interval_s)
        callback()


def _default_scheduler(interval_s: float, callback: Callable[[], None]) -> object:
    """Create the production advancement task on the running event loop.

    Returns an ``asyncio.Task`` whose ``cancel`` stops the loop.
    """
    import asyncio

    return asyncio.get_event_loop().create_task(_advance_forever(interval_s, callback))


class ServerRuntimeLoop:
    """Owns the single advancement loop for the process."""

    def __init__(
        self,
        runtime: RobotRuntime,
        *,
        interval_s: float = TICK_INTERVAL_S,
        dt_s: float = TICK_DT_S,
        scheduler: Scheduler | None = None,
    ) -> None:
        self.runtime = runtime
        self.interval_s = interval_s
        self.dt_s = dt_s
        self._explicit_scheduler = scheduler
        self._handle: object | None = None
        self.advance_count = 0

    def _resolve_scheduler(self) -> Scheduler:
        # Resolved at start time so tests can monkeypatch ``_default_scheduler``.
        return (
            self._explicit_scheduler
            if self._explicit_scheduler is not None
            else _default_scheduler
        )

    @property
    def running(self) -> bool:
        return self._handle is not None

    def advance_once(self) -> None:
        """One advancement: this is the ONLY thing that moves the runtime."""
        self.runtime.step(self.dt_s)
        self.advance_count += 1

    def start(self) -> None:
        """Start the loop if it is not already running (idempotent)."""
        if self._handle is not None:
            return
        self.runtime.boot()
        self._handle = self._resolve_scheduler()(self.interval_s, self.advance_once)

    def stop(self) -> None:
        """Cancel the loop (safe to call when not running)."""
        handle = self._handle
        self._handle = None
        if handle is None:
            return
        cancel = getattr(handle, "cancel", None)
        if callable(cancel):
            cancel()


_loop: ServerRuntimeLoop | None = None


def get_server_loop() -> ServerRuntimeLoop:
    """Return the process-wide server loop manager (creating it on first use)."""
    global _loop
    if _loop is None:
        _loop = ServerRuntimeLoop(get_runtime())
    return _loop


def start_server_loop() -> ServerRuntimeLoop:
    """Start the single server loop. Idempotent across clients and startups."""
    loop = get_server_loop()
    loop.start()
    return loop


def stop_server_loop() -> None:
    """Stop the server loop (used on shutdown and by tests)."""
    global _loop
    if _loop is not None:
        _loop.stop()
        _loop = None
