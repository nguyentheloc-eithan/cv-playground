"""Step 2: the AI part and image helpers, all done with OpenCV.

    find_faces(image)        -> where are the faces?             (YuNet model)
    face_vector(image, f)    -> turn one face into numbers        (SFace model)
    sharpness(image, f)      -> is the face photo blurry?
    to_jpeg(image)           -> picture to JPEG bytes

A "face vector" is a list of 128 numbers. Two photos of the same person give vectors
that point in nearly the same direction. `similarity` compares two of them
(0..1, higher means more alike).
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
    row: np.ndarray       # raw detector output (box, 5 landmarks, score); SFace needs it

    @property
    def size(self):
        return min(self.w, self.h)

    @property
    def yaw(self):
        """How far the head is turned: 0 = facing the camera, about 0.5+ = side view.

        Uses the nose position between the two eyes (landmarks 0, 1 = eyes, 2 = nose).
        """
        right_eye_x, left_eye_x, nose_x = float(self.row[4]), float(self.row[6]), float(self.row[8])
        eye_distance = abs(left_eye_x - right_eye_x) or 1.0
        return float(abs(nose_x - (right_eye_x + left_eye_x) / 2) / eye_distance)


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

    def sharpness(self, image, face):
        """Blur score of the face area. Higher = sharper. Below about 60 looks blurry."""
        x, y = max(int(face.x), 0), max(int(face.y), 0)
        crop = image[y:y + int(face.h), x:x + int(face.w)]
        if crop.size == 0:
            return 0.0
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        return float(cv2.Laplacian(gray, cv2.CV_64F).var())

    def crop_jpeg(self, image, bbox, margin=0.35, quality=85):
        """JPEG of the face area (with some margin around it), used as an event snapshot."""
        x, y, w, h = bbox
        height, width = image.shape[:2]
        x0, y0 = max(int(x - w * margin), 0), max(int(y - h * margin), 0)
        x1, y1 = min(int(x + w * (1 + margin)), width), min(int(y + h * (1 + margin)), height)
        return self.to_jpeg(image[y0:y1, x0:x1], quality)

    def to_jpeg(self, image, quality=92):
        ok, buffer = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, quality])
        return buffer.tobytes()


def similarity(a, b):
    """How alike two face vectors are. Both must have length 1."""
    return float(np.dot(a, b))
