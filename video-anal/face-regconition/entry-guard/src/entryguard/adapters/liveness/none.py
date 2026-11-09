from __future__ import annotations

import numpy as np

from ...core.types import Detection


class NoLiveness:
    """Placeholder: treats every face as real. Replace with an anti-spoof model later."""
    name = "none"

    def score(self, image: np.ndarray, det: Detection) -> float:
        return 1.0
