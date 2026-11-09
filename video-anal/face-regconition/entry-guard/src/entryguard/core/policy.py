from __future__ import annotations

import numpy as np

from ..config import Policy
from .types import Decision, Match


def best_match(query: np.ndarray, person_ids: list[str], matrix: np.ndarray) -> Match:
    """Cosine similarity (vectors are L2-normalised, so a dot product)."""
    if len(person_ids) == 0:
        return Match(None, 0.0)
    sims = matrix @ query
    # best score per person
    best: dict[str, float] = {}
    for pid, s in zip(person_ids, sims):
        if s > best.get(pid, -2.0):
            best[pid] = float(s)
    pid = max(best, key=best.get)
    return Match(pid, best[pid])


def decide(match: Match, policy: Policy) -> Decision:
    if match.person_id is None or match.score < policy.reject_threshold:
        return Decision.UNKNOWN
    if match.score >= policy.accept_threshold:
        return Decision.AUTHORIZED
    return Decision.UNCERTAIN
