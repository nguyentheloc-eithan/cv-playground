"""Tiny IoU tracker: keeps one id per face across frames, so we decide once per track."""
from __future__ import annotations

from dataclasses import dataclass, field

from .types import Detection


def iou(a, b) -> float:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    ix = max(0.0, min(ax + aw, bx + bw) - max(ax, bx))
    iy = max(0.0, min(ay + ah, by + bh) - max(ay, by))
    inter = ix * iy
    union = aw * ah + bw * bh - inter
    return inter / union if union > 0 else 0.0


@dataclass
class Track:
    id: int
    bbox: tuple[float, float, float, float]
    missed: int = 0
    votes: list = field(default_factory=list)  # (person_id | None, score)
    decided: bool = False


class IouTracker:
    def __init__(self, min_iou: float, max_missed: int) -> None:
        self.min_iou, self.max_missed = min_iou, max_missed
        self._next = 1
        self.tracks: list[Track] = []

    def update(self, dets: list[Detection]) -> list[tuple[Track, Detection]]:
        pairs: list[tuple[Track, Detection]] = []
        free = list(self.tracks)
        for d in dets:
            best, best_i = None, self.min_iou
            for t in free:
                v = iou(t.bbox, d.bbox)
                if v >= best_i:
                    best, best_i = t, v
            if best is None:
                best = Track(self._next, d.bbox)
                self._next += 1
                self.tracks.append(best)
            else:
                free.remove(best)
            best.bbox, best.missed = d.bbox, 0
            pairs.append((best, d))
        for t in free:
            t.missed += 1
        self.tracks = [t for t in self.tracks if t.missed <= self.max_missed]
        return pairs
