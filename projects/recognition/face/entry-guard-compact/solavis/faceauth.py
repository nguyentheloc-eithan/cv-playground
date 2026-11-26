"""Live face check for the President (reuses the repository's face engine).

Two pictures are needed: one looking straight and one with the head clearly turned. A printed photo or a phone screen
cannot do that. Both must match the enrolled face."""
import numpy as np

from . import recog, settings
from .recog import _lock, engine
from .db import face_vectors
from sqlalchemy import select

NOT_RECOGNISED = "Face not recognised"
MIN_FACE_PX = 80


def _measure(images, need):
    if len(images) < need:
        return "Look straight at the camera, then turn your head slightly to the left or right", None
    seen = []
    with _lock:
        eng = engine()
        for img in images[:need]:
            if img is None:
                return "That picture could not be read", None
            faces = eng.find_faces(img)
            if len(faces) != 1:
                return "Exactly one face must be in view", None
            f = faces[0]
            if f.size < MIN_FACE_PX:
                return "Move closer to the camera", None
            seen.append((f.yaw, eng.face_vector(img, f), eng.crop_jpeg(img, (f.x, f.y, f.w, f.h))))
    return None, seen


def _pose_problem(cfg, seen):
    if seen[0][0] > 0.30:
        return "Look straight at the camera"
    if len(seen) == 2 and (seen[1][0] < cfg.head_turn_min_yaw or seen[1][0] - seen[0][0] < 0.12):
        return "Turn your head slightly to the left or right"
    return None


def load_vectors(c, user_id):
    return [np.frombuffer(r[0], np.float32) for r in c.execute(select(face_vectors.c.vec).where(face_vectors.c.user_id == user_id))]


def verify(images, enrolled):
    """Returns (ok, message, scores, snapshot_jpeg_or_None). A pose problem is a "try again", not a failed identity."""
    cfg = settings.get().security.face
    if not enrolled:
        return False, "No face is enrolled for this account", [], None
    need = 2 if cfg.require_head_turn else 1
    msg, seen = _measure(images, need)
    msg = msg or _pose_problem(cfg, seen)
    if msg:
        return False, msg, [], (seen[0][2] if seen else None)
    best = [float(max(np.dot(vec, e) for e in enrolled)) for _, vec, _ in seen]
    scores = [round(b, 2) for b in best]
    snap = seen[0][2]
    if best[0] < cfg.threshold or (len(best) == 2 and best[1] < settings.get().recognition.thresholds.accept):
        return False, NOT_RECOGNISED, scores, snap
    return True, "", scores, snap


def enrollment_vectors(images):
    """Needs 2-3 pictures, one face each. Returns (message, vectors, snapshot)."""
    cfg = settings.get().security.face
    if len(images) < 2:
        return "Take at least two pictures: one straight, one with the head turned", None, None
    msg, seen = _measure(images, min(len(images), cfg.max_frames))
    if msg:
        return msg, None, None
    if seen[0][0] > 0.30:
        return "The first picture must look straight at the camera", None, None
    return None, [v for _, v, _ in seen], seen[0][2]
