"""Guard tests: the robot adapters must not touch hardware by accident.

These assert the *absence* of a hardware path, so a future change that silently
starts driving motors/servos (or opens a serial port) fails loudly here.
"""

from __future__ import annotations

import ast
from pathlib import Path

from amr_core.robot.chassis import OfflineChassisAdapter
from amr_core.robot.interfaces import ChassisCommand
from amr_core.robot.serial_chassis import SerialChassisAdapter

ROBOT_PKG = Path(__file__).resolve().parent.parent / "src" / "amr_core" / "robot"


def test_robot_core_modules_do_not_import_serial() -> None:
    for path in ROBOT_PKG.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert all(alias.name != "serial" for alias in node.names), path
            if isinstance(node, ast.ImportFrom):
                assert node.module != "serial", path


def test_offline_adapter_never_transmits() -> None:
    outcome = OfflineChassisAdapter().submit(ChassisCommand(0.2, 0.0, 0.0))
    assert outcome.transmitted is False


def test_live_adapter_never_transmits_before_the_port_is_open() -> None:
    """The live adapter must stay quiet until somebody opens the port.

    This is the guard that matters now that a real transport exists: creating
    the adapter, validating a command or asking it to stop must not put a byte
    on the wire.
    """
    adapter = SerialChassisAdapter(port="/dev/does-not-exist")
    outcome = adapter.submit(ChassisCommand(0.2, 0.0, 0.0))
    assert outcome.transmitted is False
    assert adapter.stop().transmitted is False
