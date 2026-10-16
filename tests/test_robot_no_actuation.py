"""Guard tests: the offline robot adapters must not touch hardware.

These assert the *absence* of a hardware path, so a future change that silently
starts driving motors/servos (or opens a serial port) fails loudly here.
"""

from __future__ import annotations

import ast
from pathlib import Path

from amr_core.robot.chassis import OfflineChassisAdapter, SerialChassisAdapter
from amr_core.robot.interfaces import ChassisCommand

ROBOT_PKG = Path(__file__).resolve().parent.parent / "src" / "amr_core" / "robot"


def test_robot_core_modules_do_not_import_serial() -> None:
    for path in ROBOT_PKG.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert all(alias.name != "serial" for alias in node.names), path
            if isinstance(node, ast.ImportFrom):
                assert node.module != "serial", path


def test_offline_and_serial_adapters_never_transmit() -> None:
    for adapter in (OfflineChassisAdapter(), SerialChassisAdapter()):
        outcome = adapter.submit(ChassisCommand(0.2, 0.0, 0.0))
        assert outcome.transmitted is False
