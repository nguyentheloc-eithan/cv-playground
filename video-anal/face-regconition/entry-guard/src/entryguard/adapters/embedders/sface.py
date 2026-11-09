from __future__ import annotations

import cv2
import numpy as np

from ...core.types import Detection


class SFaceEmbedder:
    name = "sface"
    space_id = "sface_128"

    def __init__(self, path: str) -> None:
        self._rec = cv2.FaceRecognizerSF.create(str(path), "")

    def embed(self, image: np.ndarray, det: Detection) -> np.ndarray:
        row = np.array([*det.bbox, *[c for p in det.landmarks for c in p], det.score],
                       dtype=np.float32)
        aligned = self._rec.alignCrop(image, row)
        vec = self._rec.feature(aligned).flatten().astype(np.float32)
        return vec / (np.linalg.norm(vec) or 1.0)
