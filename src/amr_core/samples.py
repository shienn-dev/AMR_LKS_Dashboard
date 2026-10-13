"""Sample missions for the Phase 1 prototype.

Everything here is *simulated sample data*. There is no robot connection and no
mission file is read from disk yet; these presets stand in for the YAML missions
described in the architecture document.

Determinism: random selections use a passed-in ``random.Random`` so tests can
seed them and get reproducible output.
"""

from __future__ import annotations

import random

from amr_core.mission import (
    ALLOWED_COLORS,
    SAMPLE_RACKS,
    SAMPLE_TARGETS,
    MissionConfig,
)


class SampleMission:
    """A named mission preset shown in the mission-selection dropdown."""

    def __init__(self, mission_id: str, version: int, time_limit_s: int, reserve_for_home_s: int):
        self.mission_id = mission_id
        self.version = version
        self.time_limit_s = time_limit_s
        self.reserve_for_home_s = reserve_for_home_s

    def blank_config(self) -> MissionConfig:
        """Return an empty configuration for this mission (needs operator input)."""
        return MissionConfig(
            mission_id=self.mission_id,
            version=self.version,
            time_limit_s=self.time_limit_s,
            reserve_for_home_s=self.reserve_for_home_s,
        )

    def sample_config(self, rng: random.Random) -> MissionConfig:
        """Return a randomized *sample* configuration.

        Target order and rack colors are randomized to imitate the judge draw.
        """
        order = list(SAMPLE_TARGETS)
        rng.shuffle(order)
        rack_colors = {rack: rng.choice(ALLOWED_COLORS) for rack in SAMPLE_RACKS}
        return MissionConfig(
            mission_id=self.mission_id,
            version=self.version,
            time_limit_s=self.time_limit_s,
            reserve_for_home_s=self.reserve_for_home_s,
            target_order=order,
            rack_colors=rack_colors,
        )


# The catalog of selectable sample missions.
SAMPLE_MISSIONS: tuple[SampleMission, ...] = (
    SampleMission("modul_E", version=1, time_limit_s=600, reserve_for_home_s=60),
    SampleMission("G2", version=1, time_limit_s=600, reserve_for_home_s=60),
)


def get_sample_mission(mission_id: str) -> SampleMission | None:
    for mission in SAMPLE_MISSIONS:
        if mission.mission_id == mission_id:
            return mission
    return None
