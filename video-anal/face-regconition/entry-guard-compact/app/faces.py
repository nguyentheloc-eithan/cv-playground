"""Step 2: the AI part. Two jobs, both done with OpenCV:

    find_faces(image)      -> where are the faces?        (YuNet model)
    face_vector(image, f)  -> turn one face into numbers  (SFace model)

A "face vector" is a list of 128 numbers. Two photos of the same person give vectors
that point in nearly the same direction. We compare them with `similarity` (0..1, higher
means more alike).
"""
from dataclasses import dataclass

import cv2
import numpy as np

from .config import path_in_project


@dataclass
class Face:
    x: float
    y: float
    w: float
    h: float
    score: float          # how sure the detector is that this is a face
    row: np.ndarray       # raw detector output, SFace needs it to align the face

    @property
    def size(self):
        return min(self.w, self.h)


class FaceEngine:
    def __init__(self, cfg):
        models = cfg["models"]
        self.detector = cv2.FaceDetectorYN.create(
            str(path_in_project(models["detector_file"])), "", (320, 320),
            models["detect_score_threshold"], 0.3, 20)
        self.recognizer = cv2.FaceRecognizerSF.create(
            str(path_in_project(models["recognizer_file"])), "")

    def find_faces(self, image):
        height, width = image.shape[:2]
        self.detector.setInputSize((width, height))
        _, rows = self.detector.detect(image)
        if rows is None:
            return []
        # float(...) turns numpy numbers into plain Python numbers, which JSON can handle
        return [Face(float(r[0]), float(r[1]), float(r[2]), float(r[3]), float(r[14]), r)
                for r in rows]

    def face_vector(self, image, face):
        aligned = self.recognizer.alignCrop(image, face.row)
        vector = self.recognizer.feature(aligned).flatten().astype(np.float32)
        return vector / np.linalg.norm(vector)  # length 1, so a dot product = similarity


def similarity(a, b):
    """How alike two face vectors are. Both must have length 1."""
    return float(np.dot(a, b))
