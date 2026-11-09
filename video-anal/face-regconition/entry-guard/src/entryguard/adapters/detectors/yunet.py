from __future__ import annotations

import cv2
import numpy as np

from ...core.types import Detection


class YuNetDetector:
    name = "yunet"

    def __init__(self, path: str, score_threshold: float = 0.8,
                 nms_threshold: float = 0.3, top_k: int = 20) -> None:
        self._args = (str(path), "", (320, 320), score_threshold, nms_threshold, top_k)
        self._det = cv2.FaceDetectorYN.create(*self._args)

    def detect(self, image: np.ndarray) -> list[Detection]:
        h, w = image.shape[:2]
        self._det.setInputSize((w, h))
        _, faces = self._det.detect(image)
        out: list[Detection] = []
        for f in faces if faces is not None else []:
            lm = tuple((float(f[4 + 2 * i]), float(f[5 + 2 * i])) for i in range(5))
            out.append(Detection(bbox=tuple(float(v) for v in f[:4]), score=float(f[14]),
                                 landmarks=lm))
        return out
