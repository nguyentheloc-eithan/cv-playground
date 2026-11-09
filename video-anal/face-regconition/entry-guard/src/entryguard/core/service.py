"""Use cases: enroll a person from images, check images, watch a video stream."""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from typing import Callable, Iterable

import numpy as np

from ..config import Settings
from .policy import best_match, decide
from .ports import Detector, Embedder, FrameSource, Liveness, Store
from .tracker import IouTracker
from .types import Decision, Detection, Embedding, Match, Person


class EnrollmentError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass
class CheckResult:
    decision: Decision
    match: Match
    person: Person | None
    detection: Detection | None
    liveness: float = 1.0


class FaceService:
    def __init__(self, settings: Settings, detector: Detector, embedder: Embedder,
                 liveness: Liveness, store: Store) -> None:
        self.s, self.detector, self.embedder = settings, detector, embedder
        self.liveness, self.store = liveness, store

    # ---- enrollment -------------------------------------------------------
    def enroll(self, name: str, attributes: dict[str, str],
               images: Iterable[np.ndarray]) -> Person:
        cfg = self.s.enrollment
        for f in self.s.person_schema:
            if f.required and not attributes.get(f.key):
                raise EnrollmentError("MISSING_FIELD", f"Field '{f.key}' is required")
        unknown = set(attributes) - {f.key for f in self.s.person_schema}
        if unknown:
            raise EnrollmentError("UNKNOWN_FIELD", f"Not in person_schema: {sorted(unknown)}")
        images = list(images)
        if not cfg.min_photos <= len(images) <= cfg.max_photos:
            raise EnrollmentError(
                "PHOTO_COUNT", f"Need {cfg.min_photos}-{cfg.max_photos} photos, got {len(images)}")
        vecs: list[np.ndarray] = []
        for i, img in enumerate(images):
            dets = self.detector.detect(img)
            if len(dets) != 1:
                raise EnrollmentError("FACE_COUNT", f"Photo {i + 1}: expected 1 face, found {len(dets)}")
            d = dets[0]
            if d.size < cfg.min_face_px or d.score < cfg.min_detect_score:
                raise EnrollmentError("LOW_QUALITY", f"Photo {i + 1}: face too small or unclear")
            vecs.append(self.embedder.embed(img, d))
        person = Person(id=str(uuid.uuid4()), name=name, attributes=attributes)
        self.store.add_person(person)
        self.store.add_embeddings(
            [Embedding(person.id, self.embedder.space_id, v) for v in vecs])
        return person

    # ---- recognition ------------------------------------------------------
    def _classify(self, image: np.ndarray, det: Detection) -> CheckResult:
        live = self.liveness.score(image, det)
        if live < 0.5:
            return CheckResult(Decision.SPOOF, Match(None, 0.0), None, det, live)
        ids, mat = self.store.embeddings(self.embedder.space_id)
        m = best_match(self.embedder.embed(image, det), ids, mat)
        decision = decide(m, self.s.policy)
        person = self.store.get_person(m.person_id) if m.person_id else None
        if decision is Decision.UNKNOWN:
            person = None
        return CheckResult(decision, m, person, det, live)

    def check_image(self, image: np.ndarray) -> list[CheckResult]:
        dets = [d for d in self.detector.detect(image) if d.size >= self.s.policy.min_face_px]
        if not dets:
            return [CheckResult(Decision.NO_FACE, Match(None, 0.0), None, None)]
        return [self._classify(image, d) for d in dets]

    def watch(self, camera_id: str, source: FrameSource,
              on_event: Callable[[str, CheckResult], None]) -> None:
        """Run on a frame stream; emit one event per track after N votes."""
        p = self.s.policy
        tracker = IouTracker(p.track_iou, p.track_max_missed)
        last_emit: dict[str, float] = {}
        for frame in source.frames():
            dets = [d for d in self.detector.detect(frame) if d.size >= p.min_face_px]
            for track, det in tracker.update(dets):
                if track.decided:
                    continue
                r = self._classify(frame, det)
                track.votes.append(r)
                if len(track.votes) < p.frames_to_decide:
                    continue
                track.decided = True
                final = self._vote(track.votes)
                key = final.person.id if final.person else final.decision.value
                now = time.time()
                if now - last_emit.get(key, 0) < p.event_cooldown_s:
                    continue
                last_emit[key] = now
                self.store.log_event(now, camera_id, final.decision.value,
                                     final.person.id if final.person else None, final.match.score)
                on_event(camera_id, final)

    @staticmethod
    def _vote(votes: list[CheckResult]) -> CheckResult:
        counts: dict[Decision, int] = {}
        for v in votes:
            counts[v.decision] = counts.get(v.decision, 0) + 1
        if counts.get(Decision.SPOOF):
            return next(v for v in votes if v.decision is Decision.SPOOF)
        top = max(counts, key=counts.get)
        pool = [v for v in votes if v.decision is top]
        return max(pool, key=lambda v: v.match.score)
