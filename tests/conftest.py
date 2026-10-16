"""Shared pytest fixtures.

The dashboard uses a process-wide :class:`RobotRuntime` singleton (Opsi A: the
server owns the runtime, independent of any browser). Tests must not leak state
between each other, so this fixture resets the singleton around every test that
touches the dashboard runtime.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from amr_dashboard import robot_runtime as robot_runtime_module
from amr_dashboard import runtime as runtime_module


@pytest.fixture(autouse=True)
def _reset_dashboard_runtime() -> Iterator[None]:
    """Give every test a fresh, isolated robot runtime and adapter set."""
    runtime_module.reset_runtime()
    robot_runtime_module.reset_adapters()
    yield
    runtime_module.reset_runtime()
    robot_runtime_module.reset_adapters()
