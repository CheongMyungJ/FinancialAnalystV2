from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
import traceback
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError, as_completed

from sqlmodel import Session, select

from app.db.models import Fundamental, JobLog, NewsItem, PriceDaily, Stock
from app.providers.fundamentals_alpha_vantage import fetch_company_overview
from app.providers.fundamentals_yfinance import fetch_overview as fetch_yf_overview
from app.providers.fundamentals_yfinance_kr import fetch_overview_kr as fetch_yf_overview_kr
from app.providers.news_gdelt import fetch_news_gdelt
from app.providers.news_google_rss import fetch_news_google_rss
from app.providers.prices_fdr import fetch_prices_daily
from app.providers.universe_fdr import Market, list_universe
from app.scoring.engine import compute_and_store_market_scores
from app.settings import settings


_FUND_KEYS_NEEDED = [
    "market_cap",
    "pe_ratio",
    "roe_ttm",
    "enterprise_value",
    "ebitda",
    "free_cashflow",
    "total_debt",
    "revenue_growth_yoy",
    "earnings_growth_yoy",
]


@dataclass(frozen=True)
class RecomputeParams:
    market: Market
    day: date


_prices_executor = ThreadPoolExecutor(max_workers=6)
_fund_executor = ThreadPoolExecutor(max_workers=3)


def _upsert_stock(session: Session, market: Market, symbol: str, name: str | None) -> Stock:
    row = session.exec(select(Stock).where(Stock.market == market).where(Stock.symbol == symbol)).first()
    now = datetime.utcnow()
    if row:
        row.name = name or row.name
        row.updated_at = now
        session.add(row)
        session.commit()
        session.refresh(row)
        return row
    row = Stock(market=market, symbol=symbol, name=name, created_at=now, updated_at=now)
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def _store_prices_from_bars(session: Session, stock_id: int, bars) -> None:
    if not bars:
        return
    days = [b.date for b in bars]
    min_day, max_day = min(days), max(days)
    existing = session.exec(
        select(PriceDaily)
        .where(PriceDaily.stock_id == stock_id)
        .where(PriceDaily.day >= min_day)
        .where(PriceDaily.day <= max_day)
    ).all()
    for e in existing:
        session.delete(e)
    for b in bars[-260:]:
        session.add(
            PriceDaily(
                stock_id=stock_id,
                day=b.date,
                open=b.open,
                high=b.high,
                low=b.low,
                close=b.close,
                volume=b.volume,
            )
        )
    session.commit()


async def _store_news(session: Session, stock_id: int, market: Market, query: str, day: date) -> None:
    if not settings.enable_news:
        return
    # Prefer GDELT. If empty (or tone is missing), fallback to Google News RSS.
    try:
        items = await fetch_news_gdelt(query=query, max_records=25)
    except Exception:
        items = []
    if items and all((it.tone is None) for it in items):
        items = []

    if (not items) and market == "KR":
        try:
            items = await fetch_news_google_rss(query=query, max_records=25)
        except Exception:
            items = []
    if (not items) and market == "US":
        # Force English RSS so we can estimate tone reliably.
        try:
            items = await fetch_news_google_rss(query=query, max_records=25, hl="en-US", gl="US", ceid="US:en")
        except Exception:
            items = []
    cutoff = datetime(day.year, day.month, day.day) - timedelta(days=30)
    existing = session.exec(
        select(NewsItem).where(NewsItem.stock_id == stock_id).where(NewsItem.published_at >= cutoff)
    ).all()
    for e in existing:
        session.delete(e)
    for it in items:
        session.add(
            NewsItem(
                stock_id=stock_id,
                published_at=it.published_at,
                title=it.title,
                source=it.source,
                url=it.url,
                tone=it.tone,
            )
        )
    session.commit()


async def _store_us_fundamentals(session: Session, stock_id: int, symbol: str, day: date) -> None:
    if not settings.enable_fundamentals:
        return
    # Prefer Alpha Vantage if key is present; otherwise fall back to yfinance (no key).
    if settings.alpha_vantage_api_key:
        ov = await fetch_company_overview(api_key=settings.alpha_vantage_api_key, symbol=symbol)
        pts: list[tuple[str, float | None]] = [
            ("market_cap", ov.market_cap),
            ("pe_ratio", ov.pe_ratio),
            ("roe_ttm", ov.roe_ttm),
            ("profit_margin", ov.profit_margin),
        ]
        src = ov.source
    else:
        try:
            fut = _fund_executor.submit(fetch_yf_overview, symbol)
            yfo = fut.result(timeout=12)
            pts = [
                ("market_cap", yfo.market_cap),
                ("pe_ratio", yfo.pe_ratio),
                ("roe_ttm", yfo.roe_ttm),
                ("enterprise_value", yfo.enterprise_value),
                ("ebitda", yfo.ebitda),
                ("free_cashflow", yfo.free_cashflow),
                ("total_debt", yfo.total_debt),
                ("revenue_growth_yoy", yfo.revenue_growth_yoy),
                ("earnings_growth_yoy", yfo.earnings_growth_yoy),
            ]
            src = yfo.source
        except Exception:
            return

    for k, v in pts:
        if v is None:
            continue
        session.add(Fundamental(stock_id=stock_id, asof_date=day, key=k, value=float(v), source=src))
    session.commit()


async def recompute_market(*, session: Session, market: Market, day: date) -> None:
    # Prevent duplicate concurrent recomputes per market.
    running = session.exec(
        select(JobLog)
        .where(JobLog.job_name == f"recompute:{market}")
        .where(JobLog.status == "running")
        .where(JobLog.finished_at == None)  # noqa: E711
        .order_by(JobLog.started_at.desc())
        .limit(1)
    ).first()
    if running:
        # If a "running" job is stale (e.g., background task died), mark it failed and proceed.
        now = datetime.utcnow()
        # Keep this relatively short in dev; tasks can get stuck due to external providers.
        if running.started_at and (now - running.started_at) > timedelta(minutes=5):
            running.status = "failed"
            running.finished_at = now
            running.message = "stale running job auto-failed"
            session.add(running)
            session.commit()
        else:
            return

    job = JobLog(job_name=f"recompute:{market}", status="running", started_at=datetime.utcnow())
    session.add(job)
    session.commit()
    session.refresh(job)

    try:
        limit = settings.universe_limit_kr if market == "KR" else settings.universe_limit_us
        try:
            universe = list_universe(market=market, limit=limit)
        except Exception:
            universe = []

        # Benchmark price series for RS factor (exclude from ranking later in scoring engine).
        bench_sym = settings.benchmark_symbol_kr if market == "KR" else settings.benchmark_symbol_us
        bench_name = "Benchmark" if market == "US" else "벤치마크"
        bench_stock = _upsert_stock(session, market=market, symbol=bench_sym, name=bench_name)
        # Prices: fetch in parallel to avoid very slow sequential network calls.
        start = (day - timedelta(days=400)).isoformat()
        end = day.isoformat()
        price_futures = {}
        fund_futures = {}
        kr_fund_futures = {}

        # Fetch benchmark prices once.
        if bench_stock.id is not None:
            try:
                fut = _prices_executor.submit(fetch_prices_daily, market=market, symbol=bench_sym, start=start, end=end)
                price_futures[fut] = bench_stock.id
            except Exception:
                pass

        # We'll collect stock ids for a batch "already has fundamentals?" check to reduce API calls.
        stock_ids_in_market: list[int] = []
        stock_symbol_by_id: dict[int, str] = {}

        for u in universe:
            stock = _upsert_stock(session, market=u.market, symbol=u.symbol, name=u.name)
            if stock.id is None:
                continue
            stock_ids_in_market.append(stock.id)
            stock_symbol_by_id[stock.id] = u.symbol
            try:
                fut = _prices_executor.submit(fetch_prices_daily, market=u.market, symbol=u.symbol, start=start, end=end)
                price_futures[fut] = stock.id
            except Exception:
                pass

            # News query heuristic
            q = (u.name or u.symbol) + (" stock" if market == "US" else " 주식")
            try:
                await _store_news(session, stock.id, market, query=q, day=day)
            except Exception:
                # News should not break the whole recompute job.
                pass

            # Fundamentals are scheduled after the loop (so we can skip already-fetched ones in a batch).
            if market == "US" and settings.enable_fundamentals and settings.alpha_vantage_api_key:
                # AlphaVantage path (rate-limited) stays sequential.
                await _store_us_fundamentals(session, stock.id, symbol=u.symbol, day=day)

        # collect price results (overall timeout)
        try:
            for fut in as_completed(price_futures.keys(), timeout=60):
                stock_id = price_futures.get(fut)
                if not stock_id:
                    continue
                try:
                    bars = fut.result()
                except Exception:
                    continue
                _store_prices_from_bars(session, stock_id, bars)
        except FuturesTimeoutError:
            # Some futures can hang; continue with whatever we got.
            pass

        # Fundamentals: schedule yfinance for only missing rows (reduces API calls on reruns).
        missing_fund_ids: set[int] = set()
        if settings.enable_fundamentals and stock_ids_in_market:
            existing = session.exec(
                select(Fundamental.stock_id, Fundamental.key)
                .where(Fundamental.asof_date == day)
                .where(Fundamental.stock_id.in_(stock_ids_in_market))
                .where(Fundamental.key.in_(_FUND_KEYS_NEEDED))
            ).all()
            has: dict[int, set[str]] = {}
            for sid, k in existing:
                if sid is None or k is None:
                    continue
                has.setdefault(int(sid), set()).add(str(k))
            for sid in stock_ids_in_market:
                keys = has.get(sid, set())
                if not all((k in keys) for k in _FUND_KEYS_NEEDED):
                    missing_fund_ids.add(sid)

        if settings.enable_fundamentals and missing_fund_ids:
            if market == "US" and (not settings.alpha_vantage_api_key):
                for sid in missing_fund_ids:
                    sym = stock_symbol_by_id.get(sid)
                    if not sym:
                        continue
                    try:
                        ffut = _fund_executor.submit(fetch_yf_overview, sym)
                        fund_futures[ffut] = sid
                    except Exception:
                        pass
            elif market == "KR":
                for sid in missing_fund_ids:
                    sym = stock_symbol_by_id.get(sid)
                    if not sym:
                        continue
                    try:
                        ffut = _fund_executor.submit(fetch_yf_overview_kr, sym)
                        kr_fund_futures[ffut] = sid
                    except Exception:
                        pass

        # collect fundamentals results (yfinance fallback)
        if fund_futures:
            # With yfinance throttling (~0.6s/call), bigger universes need more time.
            fund_timeout = max(180, int(len(fund_futures) * 1.2))
            try:
                for fut in as_completed(fund_futures.keys(), timeout=fund_timeout):
                    stock_id = fund_futures.get(fut)
                    if not stock_id:
                        continue
                    try:
                        yfo = fut.result()
                    except Exception:
                        continue
                    pts = [
                        ("market_cap", yfo.market_cap),
                        ("pe_ratio", yfo.pe_ratio),
                        ("roe_ttm", yfo.roe_ttm),
                        ("enterprise_value", yfo.enterprise_value),
                        ("ebitda", yfo.ebitda),
                        ("free_cashflow", yfo.free_cashflow),
                        ("total_debt", yfo.total_debt),
                        ("revenue_growth_yoy", yfo.revenue_growth_yoy),
                        ("earnings_growth_yoy", yfo.earnings_growth_yoy),
                    ]
                    existing = session.exec(
                        select(Fundamental)
                        .where(Fundamental.stock_id == stock_id)
                        .where(Fundamental.asof_date == day)
                        .where(Fundamental.key.in_([k for k, _ in pts]))
                    ).all()
                    for e in existing:
                        session.delete(e)
                    for k, v in pts:
                        if v is None:
                            continue
                        session.add(
                            Fundamental(stock_id=stock_id, asof_date=day, key=k, value=float(v), source=yfo.source)
                        )
                    session.commit()
            except FuturesTimeoutError:
                pass

        # collect KR fundamentals results (yfinance)
        if kr_fund_futures:
            kr_timeout = max(240, int(len(kr_fund_futures) * 1.2))
            try:
                for fut in as_completed(kr_fund_futures.keys(), timeout=kr_timeout):
                    stock_id = kr_fund_futures.get(fut)
                    if not stock_id:
                        continue
                    try:
                        yfo = fut.result()
                    except Exception:
                        continue
                    pts = [
                        ("market_cap", yfo.market_cap),
                        ("pe_ratio", yfo.pe_ratio),
                        ("roe_ttm", yfo.roe_ttm),
                        ("enterprise_value", yfo.enterprise_value),
                        ("ebitda", yfo.ebitda),
                        ("free_cashflow", yfo.free_cashflow),
                        ("total_debt", yfo.total_debt),
                        ("revenue_growth_yoy", yfo.revenue_growth_yoy),
                        ("earnings_growth_yoy", yfo.earnings_growth_yoy),
                    ]
                    existing = session.exec(
                        select(Fundamental)
                        .where(Fundamental.stock_id == stock_id)
                        .where(Fundamental.asof_date == day)
                        .where(Fundamental.key.in_([k for k, _ in pts]))
                    ).all()
                    for e in existing:
                        session.delete(e)
                    for k, v in pts:
                        if v is None:
                            continue
                        session.add(
                            Fundamental(stock_id=stock_id, asof_date=day, key=k, value=float(v), source=yfo.source)
                        )
                    session.commit()
            except FuturesTimeoutError:
                pass

        compute_and_store_market_scores(session=session, market=market, day=day)

        job.status = "success"
        job.finished_at = datetime.utcnow()
        job.message = f"ok: {market} {day.isoformat()}"
        session.add(job)
        session.commit()
    except Exception as e:
        job.status = "failed"
        job.finished_at = datetime.utcnow()
        job.message = (repr(e) + "\n" + traceback.format_exc())[:4000]
        session.add(job)
        session.commit()
        raise

