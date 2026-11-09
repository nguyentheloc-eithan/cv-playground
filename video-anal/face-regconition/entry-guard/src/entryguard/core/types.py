from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

import numpy as np


@dataclass(frozen=True)
class Detection:
    bbox: tuple[float, float, float, float]  # x, y, w, h in pixels
    score: float
    landmarks: tuple[tuple[float, float], ...] = ()  # 5 points: eyes, nose, mouth corners

    @property
    def size(self) -> float:
        return min(self.bbox[2], self.bbox[3])


class Decision(str, Enum):
    AUTHORIZED = "authorized"
    UNKNOWN = "unknown"
    UNCERTAIN = "uncertain"
    SPOOF = "spoof"
    NO_FACE = "no_face"


@dataclass
class Match:
    person_id: str | None
    score: float


@dataclass
class Person:
    id: str
    name: str
    attributes: dict[str, str] = field(default_factory=dict)
    status: str = "active"


@dataclass
class Embedding:
    person_id: str
    space_id: str
    vec: np.ndarray
