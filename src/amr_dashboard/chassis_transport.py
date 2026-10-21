"""Opening the STM32 chassis port (the only place that touches pyserial).

``amr_core.robot`` is deliberately free of device imports -- there is a guard
test for it (``tests/test_robot_no_actuation.py``) and the reason is sound:
the safety-critical robot package must be importable, testable and auditable
without a serial stack. The device therefore lives here, in the layer that
owns the process lifecycle.

The details that matter and are easy to get wrong:

* **DTR and RTS are lowered before ``open()``.** That was shown not to reset
  the STM32 on this board (sesi 2 §9.1). Opening with the default line states
  can reboot the controller.
* **The baud rate is 1 Mbaud**, the value the stock Hiwonder SDK uses even
  though the device is USB CDC-ACM. Keeping it identical to the SDK avoids
  introducing a second variable.
* **The import is late.** Importing this module never imports pyserial, so the
  dashboard still starts on a machine without it.
"""

from __future__ import annotations

from amr_core.robot.serial_chassis import SerialPort

DEFAULT_BAUD = 1_000_000


def open_serial_port(port: str, baud: int = DEFAULT_BAUD) -> SerialPort:
    """Open the board's serial port, ready to accept motor frames."""
    import serial  # late import: this module must import cleanly without pyserial

    handle = serial.Serial()
    handle.port = port
    handle.baudrate = baud
    handle.timeout = 0.2
    handle.dtr = False
    handle.rts = False
    handle.open()
    return handle
