"""Robot hardware-abstraction layer (audit phase: offline / safe only).

This package defines how the dashboard talks to robot subsystems (chassis, arm,
camera, odometry) *without* depending on a specific transport. In this phase the
only shipped adapters are:

- offline adapters that validate and record commands but transmit nothing, and
- honest availability probes that never fabricate data.

See ``amr_core.robot.interfaces`` for the value types and protocols, and
``docs/robot_integration.md`` for the verified-vs-unverified evidence map.
"""

from __future__ import annotations

__all__: list[str] = []
