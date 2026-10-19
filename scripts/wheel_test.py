#!/usr/bin/env python3
"""Supervised, single-shot wheel test for the STM32 chassis controller.

SAFETY MODEL
------------
This script can transmit to ``/dev/ttyACM0``, which is the one thing the rest of
this repository deliberately refuses to do. It is therefore built to be hard to
fire by accident:

* **Dry run by default.** Without ``--confirm`` it prints the exact frame it
  *would* send and exits without opening the port.
* **Interactive acknowledgement.** Even with ``--confirm`` you must type the
  word ``MOVE`` at the prompt (skip with ``--yes`` only for scripted runs).
* **One command, then stop.** A single motor frame is sent, held for
  ``--duration`` seconds, then an explicit all-zero stop frame is sent. The stop
  also runs in a ``finally`` block, so it is sent even on error or Ctrl+C.
* **Low speed by default.** ``--speed 0.15`` rps is roughly 9 rpm. The factory
  demo uses 0.6; we start far below that because this board's firmware is
  unverified.
* **DTR/RTS are lowered before ``open()``.** This reduces (but does NOT
  guarantee against) an STM32 reset on open. See ``docs/robot_integration.md``.

PRECONDITIONS (do not skip)
---------------------------
1. Wheels OFF the ground, robot stable, nothing in the wheel path.
2. Physical power switch / E-stop within reach, hand on it.
3. Owner approval to actuate.
4. ModemManager considered: ``/dev/ttyACM0`` carries ``ID_MM_CANDIDATE=1`` and
   ModemManager is active on this image, so it may open/reset the port on its
   own. See the warning printed by this script.

PROTOCOL (from the stock Hiwonder SDK, unverified on this board)
----------------------------------------------------------------
Frame: ``0xAA 0x55 <func> <len> <payload> <crc8>``, CRC-8 reflected poly 0x8C.
Motor (func 3): ``[0x01, n, (motor_id - 1 : u8, speed : float32 LE) x n]``.
Speed unit is **rps** (rev/s) per Hiwonder "3. Chassis Motion Control" §3.1.1
(``speed_covert`` converts m/s -> rps).

Usage
-----
    python scripts/wheel_test.py                       # dry run, prints frame
    python scripts/wheel_test.py --confirm             # asks you to type MOVE
    python scripts/wheel_test.py --confirm --yes --speed 0.1 --duration 0.8
    python scripts/wheel_test.py --confirm --motors 1  # single wheel

This script performs no configuration changes, installs nothing, and writes no
files. It only opens the serial port, writes frames, and closes it.
"""

from __future__ import annotations

import argparse
import struct
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from amr_core.robot.stm32_protocol import Stm32Function, build_frame  # noqa: E402

DEFAULT_PORT = "/dev/ttyACM0"
DEFAULT_SPEED_RPS = 0.15
DEFAULT_DURATION_S = 1.0
# The stock SDK opens at 1 Mbaud even though this is a CDC-ACM device where the
# line rate is nominal. Kept identical to the SDK to avoid a second variable.
DEFAULT_BAUD = 1_000_000

STOP_SPEED = 0.0


def build_motor_frame(speeds: list[tuple[int, float]]) -> bytes:
    """Encode a func-3 MOTOR frame: ``[0x01, n, (id-1, rps) x n]``."""
    payload = bytearray([0x01, len(speeds)])
    for motor_id, rps in speeds:
        if not 1 <= motor_id <= 4:
            raise ValueError(f"motor id must be 1..4, got {motor_id}")
        payload.extend(struct.pack("<Bf", motor_id - 1, float(rps)))
    return build_frame(Stm32Function.MOTOR, bytes(payload))


def hexdump(data: bytes) -> str:
    """Space-separated lowercase hex, for copy-pasting into a log."""
    return " ".join(f"{b:02x}" for b in data)


def check_modemmanager() -> None:
    """Warn if ModemManager looks like it may grab the port."""
    print(
        "  [!] Reminder: ModemManager is active on this image and /dev/ttyACM0\n"
        "      carries ID_MM_CANDIDATE=1 (no ID_MM_PORT_IGNORE rule). It may\n"
        "      open and reset the port independently of this script. If the\n"
        "      result looks erratic, that is a likely cause."
    )


def confirm_or_exit(args: argparse.Namespace, frame: bytes, stop_frame: bytes) -> None:
    """Print the plan and require explicit acknowledgement."""
    print("\n--- WHAT WILL HAPPEN ---")
    print(f"  port      : {args.port}")
    print(f"  baud      : {args.baud}")
    print(f"  motors    : {args.motors}")
    print(f"  speed     : {args.speed} rps  (~{args.speed * 60:.1f} rpm)")
    print(f"  duration  : {args.duration} s")
    print(f"  frame     : {hexdump(frame)}")
    print(f"  stop frame: {hexdump(stop_frame)}")
    print("\n--- BEFORE YOU CONTINUE ---")
    print("  [ ] Wheels are OFF the ground")
    print("  [ ] Nothing can be caught in the wheels")
    print("  [ ] Power switch / E-stop is within reach, hand on it")
    print("  [ ] Owner approved this actuation")
    check_modemmanager()

    if args.yes:
        print("\n  --yes given: skipping interactive prompt.")
        return

    print("\nType MOVE to transmit, anything else to abort: ", end="", flush=True)
    answer = sys.stdin.readline().strip()
    if answer != "MOVE":
        print("Aborted. Nothing was sent.")
        raise SystemExit(1)


def run(args: argparse.Namespace) -> int:
    """Open the port, send one move frame, hold, then always send stop."""
    try:
        import serial  # imported late so --help works without pyserial
    except ImportError:
        print("ERROR: pyserial is not installed in this interpreter.", file=sys.stderr)
        print("       Use the project venv: ../.venv/bin/python scripts/wheel_test.py",
              file=sys.stderr)
        return 2

    speeds = [(m, args.speed) for m in args.motors]
    frame = build_motor_frame(speeds)
    stop_frame = build_motor_frame([(m, STOP_SPEED) for m in args.motors])

    confirm_or_exit(args, frame, stop_frame)

    print("\n--- TRANSMITTING ---")
    port = None
    try:
        # Lower DTR/RTS BEFORE open() to reduce the chance of resetting the MCU.
        port = serial.Serial()
        port.port = args.port
        port.baudrate = args.baud
        port.timeout = 0.2
        port.dtr = False
        port.rts = False
        port.open()
        print(f"  opened {args.port} @ {args.baud}")
        time.sleep(args.settle)  # let the board settle after open

        port.write(frame)
        port.flush()
        print(f"  sent move frame ({len(frame)} bytes), holding {args.duration}s")
        time.sleep(args.duration)

    except Exception as exc:  # noqa: BLE001 - report the real cause, never hide it
        print(f"  ERROR while transmitting: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 3
    finally:
        if port is not None and port.is_open:
            try:
                port.write(stop_frame)
                port.flush()
                print(f"  sent STOP frame ({len(stop_frame)} bytes)")
            except Exception as exc:  # noqa: BLE001
                print(f"  ERROR sending stop: {type(exc).__name__}: {exc}", file=sys.stderr)
            finally:
                time.sleep(0.2)
                port.close()
                print("  port closed")

    print("\nDone. Record what you observed: did the wheels turn, in which")
    print("direction, and did the board stay connected?")
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Supervised single-shot STM32 wheel test (dry run by default).",
    )
    parser.add_argument(
        "--port", default=DEFAULT_PORT, help=f"serial port (default {DEFAULT_PORT})"
    )
    parser.add_argument(
        "--baud", type=int, default=DEFAULT_BAUD, help="baud rate (default 1000000)"
    )
    parser.add_argument(
        "--speed",
        type=float,
        default=DEFAULT_SPEED_RPS,
        help=f"motor speed in rps (default {DEFAULT_SPEED_RPS}; keep small)",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=DEFAULT_DURATION_S,
        help=f"how long to hold the command, seconds (default {DEFAULT_DURATION_S})",
    )
    parser.add_argument(
        "--motors",
        type=lambda s: [int(x) for x in s.split(",")],
        default=[1, 2, 3, 4],
        help="comma-separated motor ids 1..4 (default 1,2,3,4)",
    )
    parser.add_argument(
        "--settle",
        type=float,
        default=0.3,
        help="seconds to wait after opening before sending (default 0.3)",
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="actually transmit (without this the script is a dry run)",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="skip the interactive MOVE prompt (only with --confirm)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    speeds = [(m, args.speed) for m in args.motors]
    frame = build_motor_frame(speeds)
    stop_frame = build_motor_frame([(m, STOP_SPEED) for m in args.motors])

    if not args.confirm:
        print("=== DRY RUN (no port is opened, nothing is sent) ===")
        print(f"  port      : {args.port}")
        print(f"  motors    : {args.motors}")
        print(f"  speed     : {args.speed} rps (~{args.speed * 60:.1f} rpm)")
        print(f"  frame     : {hexdump(frame)}")
        print(f"  stop frame: {hexdump(stop_frame)}")
        print("\nRe-run with --confirm to transmit. Wheels must be OFF the ground.")
        return 0

    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
