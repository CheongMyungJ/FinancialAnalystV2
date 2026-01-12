from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from sqlmodel import Session, delete, select

from app.db.models import FactorDefinition, FactorScore, Ranking, Stock
from app.scoring.calculators import CALCULATORS, StockContext
from app.scoring.normalize import grade_from_quantiles, percentile_scores, weighted_total
from app.settings import settings


@dataclass(frozen=True)
class ScoringResult:
    market: str
    day: date
    stock_ids: list[int]


def compute_and_store_market_scores(*, session: Session, market: str, day: date) -> ScoringResult:
    bench = settings.benchmark_symbol_kr if market == "KR" else settings.benchmark_symbol_us
    stocks = session.exec(select(Stock).where(Stock.market == market).where(Stock.symbol != bench)).all()
    stock_ids = [s.id for s in stocks if s.id is not None]
    if not stock_ids:
        return ScoringResult(market=market, day=day, stock_ids=[])

    # Compute scores for ALL factors (for explainability), but only enabled factors contribute to total.
    factors_all = session.exec(select(FactorDefinition)).all()
    factors_all = [f for f in factors_all if f.id is not None]
    factors_enabled = [f for f in factors_all if f.enabled]

    # wipe existing scores/rankings for (market, day)
    for sid in stock_ids:
        session.exec(delete(FactorScore).where(FactorScore.stock_id == sid).where(FactorScore.day == day))
    session.exec(delete(Ranking).where(Ranking.market == market).where(Ranking.day == day))
    session.commit()

    raw_by_factor: dict[int, dict[int, float | None]] = {}  # factor_id -> stock_id -> raw
    for f in factors_all:
        calc = CALCULATORS.get(f.calculator)
        if not calc:
            raw_by_factor[f.id] = {sid: None for sid in stock_ids}
            continue
        vals: dict[int, float | None] = {}
        for sid in stock_ids:
            try:
                vals[sid] = calc(session, StockContext(stock_id=sid, day=day))
            except Exception:
                vals[sid] = None
        raw_by_factor[f.id] = vals

    score_by_stock: dict[int, dict[int, float | None]] = {sid: {} for sid in stock_ids}
    weights: dict[int, float] = {f.id: float(f.weight) for f in factors_enabled}

    for f in factors_all:
        raw_vals = raw_by_factor.get(f.id, {sid: None for sid in stock_ids})
        scores = percentile_scores(raw_vals, higher_is_better=bool(f.higher_is_better))
        for sid in stock_ids:
            score_by_stock[sid][f.id] = scores.get(sid)

    totals = weighted_total(score_by_stock, weights)
    # Only rank stocks that have at least one computed factor score (avoid fake 0.0 totals).
    scored_sids = [
        sid
        for sid in stock_ids
        if any((score_by_stock.get(sid, {}).get(fid) is not None) for fid in weights.keys())
    ]
    sorted_sids = sorted(scored_sids, key=lambda sid: totals.get(sid, 0.0), reverse=True)
    grades = grade_from_quantiles(sorted_sids)

    # store FactorScore rows (all factors, so UI can show per-factor scores even if disabled)
    for f in factors_all:
        for sid in stock_ids:
            session.add(
                FactorScore(
                    stock_id=sid,
                    day=day,
                    factor_id=f.id,
                    raw_value=raw_by_factor[f.id].get(sid),
                    score=score_by_stock[sid].get(f.id),
                )
            )

    # store Ranking rows (Top rank computed for all, UI will limit)
    for idx, sid in enumerate(sorted_sids, start=1):
        session.add(
            Ranking(
                market=market,
                day=day,
                stock_id=sid,
                total_score=float(totals.get(sid, 0.0)),
                grade=grades.get(sid, "C"),
                rank=idx,
            )
        )

    session.commit()
    return ScoringResult(market=market, day=day, stock_ids=stock_ids)

