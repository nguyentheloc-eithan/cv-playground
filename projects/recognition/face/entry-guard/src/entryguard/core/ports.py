"""Interfaces the core depends on. Adapters implement these; the core imports no model library."""
from __future__ import annotations

from typing import Iterator, Protocol

import numpy as np

from .types import Detection, Embedding, Person


class Detector(Protocol):
    name: str

    def detect(self, image: np.ndarray) -> list[Detection]: ...


class Embedder(Protocol):
    name: str
    space_id: str  # vectors are comparable only inside one space

    def embed(self, image: np.ndarray, det: Detection) -> np.ndarray:
        """Return an L2-normalised vector."""
        ...


class Liveness(Protocol):
    name: str

    def score(self, image: np.ndarray, det: Detection) -> float:
        """1.0 = real person, 0.0 = spoof."""
        ...


class FrameSource(Protocol):
    def frames(self) -> Iterator[np.ndarray]: ...
    def close(self) -> None: ...


class Store(Protocol):
    def add_person(self, person: Person) -> None: ...
    def get_person(self, person_id: str) -> Person | None: ...
    def list_persons(self) -> list[Person]: ...
    def set_status(self, person_id: str, status: str) -> None: ...
    def delete_person(self, person_id: str) -> None: ...
    def add_embeddings(self, items: list[Embedding]) -> None: ...
    def embeddings(self, space_id: str) -> tuple[list[str], np.ndarray]:
        """Person ids (one per row) and a matrix of vectors for active persons."""
        ...
    def log_event(self, ts: float, camera_id: str, decision: str,
                  person_id: str | None, score: float) -> None: ...
    def list_events(self, limit: int = 50) -> list[dict]: ...
