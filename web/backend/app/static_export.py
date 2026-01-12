from __future__ import annotations

import asyncio
import json
from datetime import date
from pathlib import Path
import traceback

from sqlmodel import Session, select

from app.db.init_db import init_db, seed_default_factors, seed_default_weight_presets
from app.db.models import FactorDefinition, FactorScore, JobLog, NewsItem, PriceDaily, Ranking, Stock
from app.db.session import engine
from app.jobs.recompute import recompute_market
from app.providers.universe_fdr import Market


def _export_rankings(session: Session, market: Market, out_dir: Path) -> None:
    latest = session.exec(select(Ranking).where(Ranking.market == market).order_by(Ranking.day.desc()).limit(1)).first()
    day = latest.day if latest else None

    rows = session.exec(
        select(Ranking, Stock)
        .where(Ranking.market == market)
        .where(Ranking.day == day)  # day can be None; then rows will be empty
        .where(Ranking.stock_id == Stock.id)
        .order_by(Ranking.rank.asc())
    ).all()

    # Keep the same keys as the API response so the frontend can reuse it.
    explain_keys = [
        "gdelt_tone",
        "pe_ratio",
        "roe_ttm",
        "ev_to_ebitda",
        "fcf_yield",
        "debt_to_ebitda",
        "revenue_growth_yoy",
        "earnings_growth_yoy",
        "atr_14p",
        "rs_6m_vs_benchmark",
    ]
    factors = session.exec(select(FactorDefinition).where(FactorDefinition.key.in_(explain_keys))).all()
    factors = [f for f in factors if f.id is not None]
    factor_id_to_key = {f.id: f.key for f in factors}

    stock_ids = [stock.id for (_, stock) in rows if stock.id is not None]
    fs_map: dict[int, dict[str, float | None]] = {sid: {} for sid in stock_ids}
    if stock_ids and factor_id_to_key:
        fs_rows = session.exec(
            select(FactorScore)
            .where(FactorScore.day == day)
            .where(FactorScore.stock_id.in_(stock_ids))
            .where(FactorScore.factor_id.in_(list(factor_id_to_key.keys())))
        ).all()
        for r in fs_rows:
            k = factor_id_to_key.get(r.factor_id)
            if not k:
                continue
            fs_map.setdefault(r.stock_id, {})[k] = r.score

    last_success = session.exec(
        select(JobLog)
        .where(JobLog.job_name == f"recompute:{market}")
        .where(JobLog.status == "success")
        .order_by(JobLog.finished_at.desc())
        .limit(1)
    ).first()

    payload = {
        "market": market,
        "day": (day.isoformat() if day else None),
        "prev_day": None,
        "computed_at": (last_success.finished_at.isoformat() if last_success and last_success.finished_at else None),
        "factors": explain_keys,
        "items": [
            {
                "rank": ranking.rank,
                "delta_rank": None,
                "grade": ranking.grade,
                "total_score": ranking.total_score,
                "symbol": stock.symbol,
                "name": stock.name,
                "factor_scores": fs_map.get(stock.id or -1, {}),
            }
            for (ranking, stock) in rows
        ],
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"rankings_{market}.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _export_stock_details(session: Session, market: Market, out_dir: Path) -> None:
    """
    Export per-stock detail payloads for the latest ranking day in this market.
    This matches (a subset of) the backend API response shape so the frontend can reuse the UI in static mode.
    """
    latest = session.exec(select(Ranking).where(Ranking.market == market).order_by(Ranking.day.desc()).limit(1)).first()
    day = latest.day if latest else None
    if day is None:
        return

    rows = session.exec(
        select(Ranking, Stock)
        .where(Ranking.market == market)
        .where(Ranking.day == day)
        .where(Ranking.stock_id == Stock.id)
        .order_by(Ranking.rank.asc())
    ).all()
    if not rows:
        return

    last_success = session.exec(
        select(JobLog)
        .where(JobLog.job_name == f"recompute:{market}")
        .where(JobLog.status == "success")
        .order_by(JobLog.finished_at.desc())
        .limit(1)
    ).first()
    computed_at = last_success.finished_at.isoformat() if last_success and last_success.finished_at else None

    factors = session.exec(select(FactorDefinition).order_by(FactorDefinition.key.asc())).all()
    factors = [f for f in factors if f.id is not None]

    stocks_dir = out_dir / "stocks"
    stocks_dir.mkdir(parents=True, exist_ok=True)

    for ranking, stock in rows:
        if stock.id is None:
            continue

        # prices (close series)
        p_rows = session.exec(
            select(PriceDaily)
            .where(PriceDaily.stock_id == stock.id)
            .order_by(PriceDaily.day.desc())
            .limit(900)
        ).all()
        p_rows = list(reversed(p_rows))
        price_bars = [{"date": r.day.isoformat(), "close": float(r.close)} for r in p_rows]

        # news (optional)
        n_rows = session.exec(
            select(NewsItem).where(NewsItem.stock_id == stock.id).order_by(NewsItem.published_at.desc()).limit(20)
        ).all()
        news_items = [
            {
                "published_at": r.published_at.isoformat(),
                "title": r.title,
                "source": r.source,
                "url": r.url,
                "tone": r.tone,
            }
            for r in n_rows
        ]

        # factor breakdown
        scores = session.exec(select(FactorScore).where(FactorScore.stock_id == stock.id).where(FactorScore.day == day)).all()
        by_factor_id = {s.factor_id: s for s in scores}
        breakdown = []
        for f in factors:
            s = by_factor_id.get(f.id) if f.id is not None else None
            breakdown.append(
                {
                    "key": f.key,
                    "name": f.name,
                    "factor_type": f.factor_type,
                    "weight": f.weight,
                    "higher_is_better": f.higher_is_better,
                    "raw_value": (s.raw_value if s else None),
                    "score": (s.score if s else None),
                    "enabled": f.enabled,
                    "note": None,
                }
            )

        payload = {
            "market": market,
            "symbol": stock.symbol,
            "name": stock.name,
            "day": day.isoformat(),
            "computed_at": computed_at,
            "ranking": {
                "rank": ranking.rank,
                "grade": ranking.grade,
                "total_score": ranking.total_score,
            },
            "prices": {"bars": price_bars},
            "news": {"items": news_items},
            "breakdown": breakdown,
        }

        (stocks_dir / f"{market}_{stock.symbol}.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )


async def _run() -> None:
    init_db()
    with Session(engine) as session:
        seed_default_factors(session)
        seed_default_weight_presets(session)

        today = date.today()
        for m in ("KR", "US"):
            try:
                await recompute_market(session=session, market=m, day=today)
            except Exception:
                # Network/provider failures should not break the whole export job.
                print(f"[static_export] recompute failed: market={m} day={today.isoformat()}")
                print(traceback.format_exc()[:4000])

        # Export into frontend public dir so GitHub Pages can serve it directly.
        out_dir = Path(__file__).resolve().parents[2] / "frontend" / "public" / "data"
        _export_rankings(session, "KR", out_dir)
        _export_rankings(session, "US", out_dir)
        _export_stock_details(session, "KR", out_dir)
        _export_stock_details(session, "US", out_dir)


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()

