"""Simulated vision detections.

Phase 1 has no camera. This module produces deterministic *sample* detections
for color and shape so the vision panel has meaningful content. The panel must
always label this data as simulated, never as a live feed (task requirement).
"""

from __future__ import annotations

from dataclasses import dataclass

DETECTION_COLORS: tuple[str, ...] = ("red", "green", "blue")
DETECTION_SHAPES: tuple[str, ...] = ("cube", "cylinder", "triangle")


@dataclass(frozen=True)
class Detection:
    """A single simulated object detection."""

    label: str
    color: str
    shape: str
    confidence: float

    @property
    def display(self) -> str:
        return f"{self.color} {self.shape} ({self.confidence:.0%})"


def sample_detections() -> list[Detection]:
    """Return a fixed, deterministic set of sample detections.

    Three colors x three shapes would be 9 objects; the sample shows a
    representative subset (matches the F criterion's 3x3 identity space).
    """
    samples = [
        ("red", "cube", 0.94),
        ("green", "cylinder", 0.88),
        ("blue", "triangle", 0.91),
        ("red", "cylinder", 0.79),
        ("green", "cube", 0.83),
    ]
    return [
        Detection(label=f"obj_{i + 1}", color=c, shape=s, confidence=conf)
        for i, (c, s, conf) in enumerate(samples)
    ]
