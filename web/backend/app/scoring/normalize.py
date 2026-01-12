from __future__ import annotations

import math
from typing import Iterable


def percentile_scores(
    values: dict[int, float | None],
    *,
    higher_is_better: bool,
) -> dict[int, float | None]:
    """
    Convert raw values to 0~100 scores using rank-percentile within the provided set.
    Missing (None) stays None.
    """
    present = [(k, v) for k, v in values.items() if v is not None and not math.isnan(float(v))]
    if not present:
        return {k: None for k in values.keys()}

    present.sort(key=lambda kv: float(kv[1]), reverse=higher_is_better)
    n = len(present)
    out: dict[int, float | None] = {k: None for k in values.keys()}

    # If all present values are equal, avoid arbitrary ranking (stable-but-random by insertion order).
    vals_only = [float(v) for _, v in present]
    if vals_only and max(vals_only) == min(vals_only):
        for stock_id, _ in present:
            out[stock_id] = 50.0
        return out

    # Rank-based percentile: best -> 100, worst -> 0
    for idx, (stock_id, _) in enumerate(present):
        if n == 1:
            out[stock_id] = 100.0
        else:
            pct = 1.0 - (idx / (n - 1))
            out[stock_id] = float(round(pct * 100.0, 6))
    return out


def weighted_total(scores: dict[int, dict[int, float | None]], weights: dict[int, float]) -> dict[int, float]:
    """
    scores[stock_id][factor_id] = score(0~100) or None
    weights[factor_id] = weight
    Returns total 0~100 (missing factor -> ignored and weights renormalized).
    """
    totals: dict[int, float] = {}
    for stock_id, fs in scores.items():
        num = 0.0
        den = 0.0
        for factor_id, w in weights.items():
            s = fs.get(factor_id)
            if s is None:
                continue
            num += float(s) * float(w)
            den += float(w)
        totals[stock_id] = (num / den) if den > 0 else 0.0
    return totals


def grade_from_quantiles(sorted_stock_ids: list[int]) -> dict[int, str]:
    """
    A/B/C/D/F by quintiles.
    Input must be sorted by total_score desc.
    """
    n = len(sorted_stock_ids)
    out: dict[int, str] = {}
    for i, sid in enumerate(sorted_stock_ids):
        if n == 0:
            out[sid] = "C"
            continue
        q = (i + 1) / n
        if q <= 0.2:
            out[sid] = "A"
        elif q <= 0.4:
            out[sid] = "B"
        elif q <= 0.6:
            out[sid] = "C"
        elif q <= 0.8:
            out[sid] = "D"
        else:
            out[sid] = "F"
    return out

