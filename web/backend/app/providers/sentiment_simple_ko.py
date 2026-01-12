from __future__ import annotations

import re


_POS = {
    "상승",
    "급등",
    "강세",
    "호재",
    "기대",
    "성장",
    "최고",
    "개선",
    "흑자",
    "상향",
    "돌파",
    "확대",
    "선방",
    "반등",
    "매수",
}

_NEG = {
    "하락",
    "급락",
    "약세",
    "악재",
    "우려",
    "부진",
    "최저",
    "감소",
    "적자",
    "하향",
    "경고",
    "리콜",
    "소송",
    "충격",
    "불확실",
    "매도",
}


def estimate_tone_ko(title: str) -> float | None:
    """
    Very lightweight heuristic sentiment for Korean news titles.
    Returns a tone-like value roughly in [-10, 10] (similar spirit to GDELT tone).

    This is intentionally simple (no model, no external deps) and should be treated as "estimated".
    """
    t = (title or "").strip()
    if not t:
        return None

    # normalize: remove punctuation, keep Hangul/ASCII/digits/spaces
    t2 = re.sub(r"[^0-9A-Za-z가-힣\s]", " ", t)
    words = [w for w in t2.split() if w]
    if not words:
        return None

    pos = 0
    neg = 0
    for w in words:
        if w in _POS:
            pos += 1
        if w in _NEG:
            neg += 1

    if pos == 0 and neg == 0:
        return 0.0

    # scale: each net keyword ~ 2.0 points, clamp to [-10, 10]
    score = (pos - neg) * 2.0
    if score > 10.0:
        score = 10.0
    if score < -10.0:
        score = -10.0
    return float(score)

