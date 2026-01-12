from __future__ import annotations

import re


_POS = {
    "beats",
    "beat",
    "surge",
    "soars",
    "soar",
    "rally",
    "rallies",
    "bullish",
    "upgrade",
    "upgrades",
    "record",
    "strong",
    "growth",
    "profit",
    "profits",
    "buy",
    "outperform",
    "wins",
    "win",
}

_NEG = {
    "miss",
    "misses",
    "plunge",
    "plunges",
    "falls",
    "fall",
    "drop",
    "drops",
    "bearish",
    "downgrade",
    "downgrades",
    "weak",
    "slump",
    "loss",
    "losses",
    "sell",
    "lawsuit",
    "probe",
    "recall",
    "warning",
}


def estimate_tone_en(title: str) -> float | None:
    """
    Lightweight English title sentiment heuristic.
    Returns a tone-like value roughly in [-10, 10].
    """
    t = (title or "").strip()
    if not t:
        return None
    t2 = re.sub(r"[^0-9A-Za-z\\s]", " ", t).lower()
    words = [w for w in t2.split() if w]
    if not words:
        return None
    pos = sum(1 for w in words if w in _POS)
    neg = sum(1 for w in words if w in _NEG)
    if pos == 0 and neg == 0:
        return 0.0
    score = (pos - neg) * 2.0
    if score > 10.0:
        score = 10.0
    if score < -10.0:
        score = -10.0
    return float(score)

