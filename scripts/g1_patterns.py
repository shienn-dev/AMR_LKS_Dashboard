#!/usr/bin/env python3
"""Print the exact commands for the sign-identification gate (G1).

This script **does not actuate**. It only prints the ``wheel_test.py`` command
line for each direction, generated from the same kinematics module the
dashboard uses, so the pattern that is tested on the robot is guaranteed to be
the pattern the code produces.

Usage::

    python scripts/g1_patterns.py
    python scripts/g1_patterns.py --duration 2 --speed 0.3

The operator runs each printed line by hand, with the robot in the state the
line asks for, and writes down what the robot actually did. The record sheet
is in ``docs/g1_identifikasi_tanda.md``.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from amr_core.robot import kinematics as k  # noqa: E402

#: name, (vx, vy, wz) in the body frame, what the robot should do, and whether
#: the pattern is expected to move the chassis or only turn the wheels.
DIRECTIONS: tuple[tuple[str, tuple[float, float, float], str], ...] = (
    ("maju", (0.19, 0.0, 0.0), "robot maju (dijamin, sudah terverifikasi di lantai)"),
    ("mundur", (-0.19, 0.0, 0.0), "robot mundur"),
    ("samping-kiri", (0.0, 0.19, 0.0), "robot meluncur ke KIRI, tidak berputar"),
    ("samping-kanan", (0.0, -0.19, 0.0), "robot meluncur ke KANA, tidak berputar"),
    ("putar-kiri", (0.0, 0.0, 1.0), "robot berputar di tempat ke KIRI (CCW dari atas)"),
    ("putar-kanan", (0.0, 0.0, -1.0), "robot berputar di tempat ke KANAN (CW dari atas)"),
    ("diagonal-maju-kiri", (0.19, 0.19, 0.0), "robot bergerak diagonal ke depan-kiri"),
    ("diagonal-maju-kanan", (0.19, -0.19, 0.0), "robot bergerak diagonal ke depan-kanan"),
)

WHEEL_NAMES = ("depan-kiri", "belakang-kiri", "depan-kanan", "belakang-kanan")


def main() -> None:
    parser = argparse.ArgumentParser(description="Print the G1 test commands (no actuation).")
    parser.add_argument("--duration", type=float, default=3.0, help="seconds per run")
    parser.add_argument(
        "--speed",
        type=float,
        default=0.19,
        help="body speed for translation tests in m/s (rotation uses 1 rad/s)",
    )
    parser.add_argument("--port", default="/dev/ttyACM0")
    args = parser.parse_args()

    print("=" * 78)
    print("G1 - IDENTIFIKASI TANDA. Skrip ini tidak mengirim apa pun.")
    print("Jalankan setiap perintah manual, dengan --confirm (tanpa --yes).")
    print("=" * 78)

    for name, (vx, vy, wz), expected in DIRECTIONS:
        pairs = k.command_for_body_velocity(vx, vy, wz)
        speeds = ",".join(f"{motor_id}:{rate:+.4f}" for motor_id, rate in pairs)
        pattern = "  ".join(
            f"{motor_id}:{'+' if rate >= 0 else '-'}" for motor_id, rate in pairs
        )
        print()
        print(f"--- {name} ---")
        print(f"  pola motor   : {pattern}")
        rates_text = ", ".join(f"{motor_id}:{rate:+.3f}" for motor_id, rate in pairs)
        turning = ", ".join(
            name
            for name, (_motor_id, rate) in zip(WHEEL_NAMES, pairs, strict=True)
            if abs(rate) > 0.01
        )
        print(f"  rate (rps)   : {rates_text}")
        print(f"  diharapkan    : {expected}")
        print(f"  roda yang berputar: {turning}")
        print("  perintah:")
        print(
            f"    ../.venv/bin/python scripts/wheel_test.py --confirm --port {args.port} "
            f"--rate 50 --duration {args.duration:g} --speeds \"{speeds}\""
        )

    print()
    print("=" * 78)
    print("Catatan:")
    print("  - Roda TERANGKAT dulu untuk tahap 1 (amati arah putar tiap roda).")
    print("  - Pindah ke lantai untuk tahap 2 (amati translasi nyata).")
    print("  - Kalau hasil tidak sesuai 'diharapkan', tulis apa yang terjadi;")
    print("    tandanya yang dikoreksi di src/amr_core/robot/kinematics.py,")
    print("    bukan perintah yang diulang-ulang.")


if __name__ == "__main__":
    main()
