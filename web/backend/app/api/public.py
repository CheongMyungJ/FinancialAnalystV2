import asyncio
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from app.providers.fundamentals_alpha_vantage import fetch_company_overview
from app.providers.news_gdelt import fetch_news_gdelt
from app.providers.news_google_rss import fetch_news_google_rss
from app.providers.prices_fdr import Market, fetch_prices_daily
from app.settings import settings
from app.db.models import FactorDefinition, FactorScore, Fundamental, JobLog, NewsItem, PriceDaily, Ranking, Stock
from app.db.session import get_session

router = APIRouter(prefix="/api/public", tags=["public"])


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


@router.get("/prices/{market}/{symbol}")
def get_prices(
    market: Market,
    symbol: str,
    start: str | None = None,
    end: str | None = None,
    limit: int = Query(200, ge=1, le=5000),
) -> dict:
    bars = fetch_prices_daily(market=market, symbol=symbol, start=start, end=end)
    if limit:
        bars = bars[-limit:]
    return {
        "market": market,
        "symbol": symbol,
        "bars": [
            {
                "date": b.date.isoformat(),
                "open": b.open,
                "high": b.high,
                "low": b.low,
                "close": b.close,
                "volume": b.volume,
            }
            for b in bars
        ],
    }


@router.get("/news")
async def get_news(
    q: str = Query(..., min_length=1, description="GDELT query string"),
    max_records: int = Query(20, ge=1, le=250),
) -> dict:
    items = await fetch_news_gdelt(query=q, max_records=max_records)
    return {
        "query": q,
        "items": [
            {
                "published_at": i.published_at.isoformat(),
                "title": i.title,
                "source": i.source,
                "url": i.url,
                "tone": i.tone,
            }
            for i in items
        ],
    }


@router.get("/fundamentals/us/{symbol}")
async def get_us_fundamentals(symbol: str) -> dict:
    if not settings.alpha_vantage_api_key:
        raise HTTPException(status_code=501, detail="ALPHAVANTAGE_API_KEY is not configured")
    ov = await fetch_company_overview(api_key=settings.alpha_vantage_api_key, symbol=symbol)
    return {
        "symbol": ov.symbol,
        "name": ov.name,
        "market_cap": ov.market_cap,
        "pe_ratio": ov.pe_ratio,
        "roe_ttm": ov.roe_ttm,
        "profit_margin": ov.profit_margin,
        "source": ov.source,
    }


@router.get("/rankings/{market}")
def get_rankings(
    market: Market,
    day: date | None = None,
    limit: int | None = Query(None, ge=1, le=5000),
    include_delta: bool = False,
    session: Session = Depends(get_session),
):
    # If day omitted, use latest day available for this market.
    if day is None:
        latest = session.exec(select(Ranking).where(Ranking.market == market).order_by(Ranking.day.desc()).limit(1)).first()
        day = latest.day if latest else date.today()

    q = (
        select(Ranking, Stock)
        .where(Ranking.market == market)
        .where(Ranking.day == day)
        .where(Ranking.stock_id == Stock.id)
        .order_by(Ranking.rank.asc())
    )
    if limit:
        q = q.limit(limit)
    rows = session.exec(q).all()

    # Previous day rank delta (for rebalance / movement signal)
    prev_day = session.exec(
        select(Ranking.day)
        .where(Ranking.market == market)
        .where(Ranking.day < day)
        .order_by(Ranking.day.desc())
        .limit(1)
    ).first()
    prev_rank_by_sid: dict[int, int] = {}
    if include_delta and prev_day:
        prev_rows = session.exec(
            select(Ranking.stock_id, Ranking.rank)
            .where(Ranking.market == market)
            .where(Ranking.day == prev_day)
        ).all()
        for sid, rnk in prev_rows:
            if sid is None or rnk is None:
                continue
            prev_rank_by_sid[int(sid)] = int(rnk)

    # Include selected factor scores for explainability on ranking list.
    # This list is also used by frontend for badges/filters on the home page.
    explain_keys = [
        # existing columns
        "gdelt_tone",
        "pe_ratio",
        "roe_ttm",
        # long-term fundamentals
        "ev_to_ebitda",
        "fcf_yield",
        "debt_to_ebitda",
        "revenue_growth_yoy",
        "earnings_growth_yoy",
        # risk / relative strength
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
    return {
        "market": market,
        "day": day.isoformat(),
        "prev_day": (prev_day.isoformat() if include_delta and prev_day else None),
        "computed_at": (last_success.finished_at.isoformat() if last_success and last_success.finished_at else None),
        "factors": explain_keys,
        "items": [
            {
                "rank": ranking.rank,
                "delta_rank": (
                    (prev_rank_by_sid.get(ranking.stock_id) - ranking.rank)
                    if include_delta and ranking.stock_id in prev_rank_by_sid
                    else None
                ),
                "grade": ranking.grade,
                "total_score": ranking.total_score,
                "symbol": stock.symbol,
                "name": stock.name,
                "factor_scores": fs_map.get(stock.id or -1, {}),
            }
            for (ranking, stock) in rows
        ],
    }


@router.get("/stocks/{market}/{symbol}")
def get_stock_detail(
    market: Market,
    symbol: str,
    day: date | None = None,
    session: Session = Depends(get_session),
) -> dict:
    stock = session.exec(select(Stock).where(Stock.market == market).where(Stock.symbol == symbol)).first()
    if not stock or stock.id is None:
        raise HTTPException(status_code=404, detail="Stock not found")

    if day is None:
        latest = session.exec(
            select(Ranking)
            .where(Ranking.market == market)
            .where(Ranking.stock_id == stock.id)
            .order_by(Ranking.day.desc())
            .limit(1)
        ).first()
        day = latest.day if latest else date.today()

    ranking = session.exec(
        select(Ranking).where(Ranking.market == market).where(Ranking.day == day).where(Ranking.stock_id == stock.id)
    ).first()

    last_success = session.exec(
        select(JobLog)
        .where(JobLog.job_name == f"recompute:{market}")
        .where(JobLog.status == "success")
        .order_by(JobLog.finished_at.desc())
        .limit(1)
    ).first()

    factors = session.exec(select(FactorDefinition).order_by(FactorDefinition.key.asc())).all()
    scores = session.exec(
        select(FactorScore).where(FactorScore.stock_id == stock.id).where(FactorScore.day == day)
    ).all()
    by_factor_id = {s.factor_id: s for s in scores}

    breakdown = []
    for f in factors:
        if f.id is None:
            continue
        s = by_factor_id.get(f.id)
        note: str | None = None
        if f.calculator in ("roe_ttm", "pe_ratio"):
            if not settings.enable_fundamentals:
                note = "재무 데이터가 꺼져있음(ENABLE_FUNDAMENTALS=1 필요)"
            elif market == "US" and not settings.alpha_vantage_api_key:
                note = "US 재무는 AlphaVantage 키가 없으면 yfinance로 대체 수집(결측 가능)"
            elif market == "KR" and not settings.dart_api_key:
                note = "KR 재무는 현재 yfinance로 대체 수집(결측 가능). DART 연동은 추후 확장."
        if f.calculator == "gdelt_tone" and market == "KR" and (s is None or s.score is None):
            note = note or "KR 뉴스는 GDELT 실패 시 RSS로 대체. RSS는 제목 키워드 기반 추정 톤을 사용합니다(결측 가능)."
        breakdown.append(
            {
                "key": f.key,
                "name": f.name,
                "factor_type": f.factor_type,
                "weight": f.weight,
                "higher_is_better": f.higher_is_better,
                "raw_value": s.raw_value if s else None,
                "score": s.score if s else None,
                "enabled": f.enabled,
                "note": note,
            }
        )

    return {
        "market": market,
        "symbol": stock.symbol,
        "name": stock.name,
        "day": day.isoformat(),
        "computed_at": (last_success.finished_at.isoformat() if last_success and last_success.finished_at else None),
        "ranking": {
            "rank": ranking.rank if ranking else None,
            "grade": ranking.grade if ranking else None,
            "total_score": ranking.total_score if ranking else None,
        },
        "breakdown": breakdown,
    }


@router.get("/stocks/{market}/{symbol}/prices")
def get_cached_prices(
    market: Market,
    symbol: str,
    limit: int = Query(260, ge=1, le=2000),
    session: Session = Depends(get_session),
) -> dict:
    stock = session.exec(select(Stock).where(Stock.market == market).where(Stock.symbol == symbol)).first()
    if not stock or stock.id is None:
        raise HTTPException(status_code=404, detail="Stock not found")
    rows_desc = session.exec(
        select(PriceDaily).where(PriceDaily.stock_id == stock.id).order_by(PriceDaily.day.desc()).limit(limit)
    ).all()
    rows = list(reversed(rows_desc))
    return {
        "market": market,
        "symbol": symbol,
        "bars": [
            {
                "date": r.day.isoformat(),
                "open": r.open,
                "high": r.high,
                "low": r.low,
                "close": r.close,
                "volume": r.volume,
            }
            for r in rows
        ],
    }


@router.get("/stocks/{market}/{symbol}/news")
async def get_cached_news(
    market: Market,
    symbol: str,
    limit: int = Query(20, ge=1, le=200),
    session: Session = Depends(get_session),
) -> dict:
    stock = session.exec(select(Stock).where(Stock.market == market).where(Stock.symbol == symbol)).first()
    if not stock or stock.id is None:
        raise HTTPException(status_code=404, detail="Stock not found")
    rows = session.exec(
        select(NewsItem).where(NewsItem.stock_id == stock.id).order_by(NewsItem.published_at.desc()).limit(limit)
    ).all()

    # On-demand cache fill:
    # If KR cache is empty (often due to GDELT rate limit during batch), fetch once for this stock and store.
    if settings.enable_news and not rows:
        q_base = (stock.name or stock.symbol).strip()
        q = (q_base + " stock") if market == "US" else q_base
        try:
            items = await asyncio.wait_for(fetch_news_gdelt(query=q, max_records=min(10, limit)), timeout=6.0)
        except Exception:
            items = []
        if items and all((it.tone is None) for it in items):
            items = []

        # KR fallback: Google News RSS tends to work better with Korean queries.
        if not items and market == "KR":
            try:
                items = await asyncio.wait_for(fetch_news_google_rss(query=q_base, max_records=min(10, limit)), timeout=6.0)
            except Exception:
                items = []
        # US fallback: use English RSS so we can estimate tone.
        if not items and market == "US":
            try:
                items = await asyncio.wait_for(
                    fetch_news_google_rss(query=q, max_records=min(10, limit), hl="en-US", gl="US", ceid="US:en"),
                    timeout=6.0,
                )
            except Exception:
                items = []

        if items:
            cutoff = datetime.utcnow() - timedelta(days=30)
            existing = session.exec(
                select(NewsItem).where(NewsItem.stock_id == stock.id).where(NewsItem.published_at >= cutoff)
            ).all()
            for e in existing:
                session.delete(e)
            for it in items:
                session.add(
                    NewsItem(
                        stock_id=stock.id,
                        published_at=it.published_at,
                        title=it.title,
                        source=it.source,
                        url=it.url,
                        tone=it.tone,
                    )
                )
            session.commit()
            rows = session.exec(
                select(NewsItem)
                .where(NewsItem.stock_id == stock.id)
                .order_by(NewsItem.published_at.desc())
                .limit(limit)
            ).all()
    return {
        "market": market,
        "symbol": symbol,
        "items": [
            {
                "published_at": r.published_at.isoformat(),
                "title": r.title,
                "source": r.source,
                "url": r.url,
                "tone": r.tone,
            }
            for r in rows
        ],
    }

