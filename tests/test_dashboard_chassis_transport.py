"""Chassis transport tests: the port must not be opened twice (no hardware).

Two writers on one serial port would interleave motor frames, and the robot
would do something nobody asked for. These tests cover the guard that refuses
to open a port somebody else already holds.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from amr_dashboard import chassis_transport


def test_no_holders_is_reported_for_an_unused_port() -> None:
    assert chassis_transport.other_processes_holding("/dev/definitely-not-open") == []


def test_our_own_process_is_never_a_holder(tmp_path: Path) -> None:
    """A process that holds the device itself must not block itself."""
    if not Path("/proc").is_dir():
        pytest.skip("the holder scan reads /proc, which only exists on Linux")
    target = tmp_path / "device"
    target.write_bytes(b"")
    with open(target, "rb"):
        assert os.getpid() not in chassis_transport.other_processes_holding(str(target))


def test_opening_a_busy_port_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    """The opener refuses when another process already holds the device."""
    monkeypatch.setattr(
        chassis_transport, "other_processes_holding", lambda port: [4321]
    )
    with pytest.raises(OSError, match="already open in another process"):
        chassis_transport.open_serial_port("/dev/ttyACM0")


def test_opening_a_free_port_reaches_pyserial(monkeypatch: pytest.MonkeyPatch) -> None:
    """With nobody holding the port, the opener goes on to open it."""
    monkeypatch.setattr(chassis_transport, "other_processes_holding", lambda port: [])
    opened: list[str] = []

    class FakeSerial:
        def __init__(self) -> None:
            self.port = ""
            self.baudrate = 0
            self.timeout = 0.0
            self.dtr = True
            self.rts = True

        def open(self) -> None:
            opened.append(self.port)

    import sys
    import types

    module = types.ModuleType("serial")
    module.Serial = FakeSerial  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "serial", module)

    handle = chassis_transport.open_serial_port("/dev/ttyACM0")
    assert opened == ["/dev/ttyACM0"]
    assert isinstance(handle, FakeSerial)
    assert handle.port == "/dev/ttyACM0"
    assert handle.dtr is False
    assert handle.rts is False
    assert isinstance(Path("/proc").exists(), bool)
