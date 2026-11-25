"""Face recognition on top of the repository's FaceEngine (YuNet detector + SFace recognizer)."""
import threading

import cv2
import numpy as np

from app.faces import FaceEngine

from . import settings

_engine = None
_lock = threading.Lock()          # the OpenCV models are not thread-safe


def engine():
    global _engine
    if _engine is None:
        m = settings.get().recognition.models
        _engine = FaceEngine({"models": m.model_dump()})
    return _engine


def decode(data: bytes):
    return cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)


def largest_face_vector(img, min_px):
    """(vector, face, crop_jpeg) of the biggest face, or None."""
    with _lock:
        eng = engine()
        faces = [f for f in eng.find_faces(img) if f.size >= min_px]
        if not faces:
            return None
        f = max(faces, key=lambda x: x.w * x.h)
        return eng.face_vector(img, f), f, eng.crop_jpeg(img, (f.x, f.y, f.w, f.h))


def single_face_vector(img):
    """For registration: exactly one face or None."""
    with _lock:
        eng = engine()
        fs = eng.find_faces(img) if img is not None else []
        return eng.face_vector(img, fs[0]) if len(fs) == 1 else None


def histogram(data: bytes):
    img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_GRAYSCALE)
    if img is None:
        return None
    h = cv2.calcHist([cv2.resize(img, (64, 48))], [0], None, [32], [0, 256])
    return cv2.normalize(h, h).flatten()


def correlation(a, b):
    return float(cv2.compareHist(np.asarray(a, np.float32), np.asarray(b, np.float32), cv2.HISTCMP_CORREL))
