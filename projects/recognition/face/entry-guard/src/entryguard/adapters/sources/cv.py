"""Frame sources built on cv2.VideoCapture: webcam, rtsp, file."""
from __future__ import annotations

import time
from typing import Iterator

import cv2
import numpy as np


class _CvSource:
    def __init__(self, target, fps: float = 10, loop: bool = False) -> None:
        self._target, self._interval, self._loop = target, 1.0 / fps if fps else 0, loop
        self._cap = cv2.VideoCapture(target)
        if not self._cap.isOpened():
            raise RuntimeError(f"Cannot open video source: {self._safe(target)}")

    @staticmethod
    def _safe(t) -> str:
        return str(t).split("@")[-1] if isinstance(t, str) else str(t)  # hide credentials

    def frames(self) -> Iterator[np.ndarray]:
        last = 0.0
        while True:
            ok, frame = self._cap.read()
            if not ok:
                if self._loop:
                    self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    continue
                return
            now = time.monotonic()
            if now - last < self._interval:
                continue  # drop frames above the configured fps
            last = now
            yield frame

    def close(self) -> None:
        self._cap.release()


class WebcamSource(_CvSource):
    def __init__(self, index: int = 0, fps: float = 10) -> None:
        super().__init__(int(index), fps)


class RtspSource(_CvSource):
    def __init__(self, url: str, fps: float = 10) -> None:
        super().__init__(url, fps)


class FileSource(_CvSource):
    def __init__(self, path: str, fps: float = 10, loop: bool = False) -> None:
        super().__init__(str(path), fps, loop)
