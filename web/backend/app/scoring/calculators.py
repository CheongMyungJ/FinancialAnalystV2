from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import numpy as np
import pandas as pd
from sqlmodel import Session, select

from app.db.models import Fundamental, NewsItem, PriceDaily, Stock
from app.settings import settings


@dataclass(frozen=True)
class StockContext:
    stock_id: int
    day: date


def _load_prices(session: Session, stock_id: int, end_day: date, lookback: int) -> pd.DataFrame:
    rows = session.exec(
        select(PriceDaily)
        .where(PriceDaily.stock_id == stock_id)
        .where(PriceDaily.day <= end_day)
        .order_by(PriceDaily.day.desc())
        .limit(lookback)
    ).all()
    if not rows:
        return pd.DataFrame(columns=["day", "open", "high", "low", "close", "volume"])
    rows = list(reversed(rows))
    return pd.DataFrame(
        [
            {
                "day": r.day,
                "open": r.open,
                "high": r.high,
                "low": r.low,
                "close": r.close,
                "volume": r.volume if r.volume is not None else np.nan,
            }
            for r in rows
        ]
    )


def _ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def momentum_120d(session: Session, ctx: StockContext) -> float | None:
    df = _load_prices(session, ctx.stock_id, ctx.day, lookback=140)
    if len(df) < 121:
        return None
    c0 = float(df["close"].iloc[-121])
    c1 = float(df["close"].iloc[-1])
    if c0 <= 0:
        return None
    return (c1 / c0) - 1.0


def volatility_20d(session: Session, ctx: StockContext) -> float | None:
    df = _load_prices(session, ctx.stock_id, ctx.day, lookback=40)
    if len(df) < 21:
        return None
    closes = df["close"].astype(float)
    rets = closes.pct_change().dropna()
    if len(rets) < 20:
        return None
    return float(rets.tail(20).std(ddof=1))


def gdelt_tone(session: Session, ctx: StockContext) -> float | None:
    # Average tone of cached news in last 14 days.
    cutoff = pd.Timestamp(ctx.day) - pd.Timedelta(days=14)
    rows = session.exec(
        select(NewsItem)
        .where(NewsItem.stock_id == ctx.stock_id)
        .where(NewsItem.published_at >= cutoff.to_pydatetime())
        .order_by(NewsItem.published_at.desc())
        .limit(50)
    ).all()
    tones = [r.tone for r in rows if r.tone is not None]
    if not tones:
        return None
    return float(np.mean(tones))


def news_volume_14d(session: Session, ctx: StockContext) -> float | None:
    cutoff = pd.Timestamp(ctx.day) - pd.Timedelta(days=14)
    rows = session.exec(
        select(NewsItem.id).where(NewsItem.stock_id == ctx.stock_id).where(NewsItem.published_at >= cutoff.to_pydatetime())
    ).all()
    return float(len(rows))


def news_tone_change(session: Session, ctx: StockContext) -> float | None:
    # (mean last 3d) - (mean last 14d)
    cutoff14 = pd.Timestamp(ctx.day) - pd.Timedelta(days=14)
    cutoff3 = pd.Timestamp(ctx.day) - pd.Timedelta(days=3)
    rows = session.exec(
        select(NewsItem)
        .where(NewsItem.stock_id == ctx.stock_id)
        .where(NewsItem.published_at >= cutoff14.to_pydatetime())
        .order_by(NewsItem.published_at.desc())
        .limit(80)
    ).all()
    tones14 = [r.tone for r in rows if r.tone is not None]
    if not tones14:
        return None
    tones3 = [r.tone for r in rows if r.tone is not None and r.published_at >= cutoff3.to_pydatetime()]
    if not tones3:
        return None
    return float(np.mean(tones3) - np.mean(tones14))


_NEG_KO = ("리콜", "소송", "규제", "수사", "횡령", "불법", "급락", "하락", "충격", "경고", "우려", "부진", "적자", "하향")
_NEG_EN = ("lawsuit", "recall", "probe", "regulator", "drop", "falls", "plunge", "warning", "miss", "weak", "slump")


def news_neg_risk_14d(session: Session, ctx: StockContext) -> float | None:
    cutoff = pd.Timestamp(ctx.day) - pd.Timedelta(days=14)
    rows = session.exec(
        select(NewsItem.title)
        .where(NewsItem.stock_id == ctx.stock_id)
        .where(NewsItem.published_at >= cutoff.to_pydatetime())
        .order_by(NewsItem.published_at.desc())
        .limit(80)
    ).all()
    if not rows:
        return None
    hits = 0
    for (title,) in rows:
        t = (title or "")
        if any(k in t for k in _NEG_KO):
            hits += 1
            continue
        tl = t.lower()
        if any(k in tl for k in _NEG_EN):
            hits += 1
    return float(hits)


def rsi_14(session: Session, ctx: StockContext) -> float | None:
    df = _load_prices(session, ctx.stock_id, ctx.day, lookback=120)
    if len(df) < 30:
        return None
    close = df["close"].astype(float)
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)
    # Wilder smoothing (alpha=1/14)
    avg_gain = gain.ewm(alpha=1 / 14, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / 14, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    rsi = 100.0 - (100.0 / (1.0 + rs))
    v = float(rsi.iloc[-1]) if len(rsi) else np.nan
    if not np.isfinite(v):
        return None
    return v


def macd_hist(session: Session, ctx: StockContext) -> float | None:
    df = _load_prices(session, ctx.stock_id, ctx.day, lookback=260)
    if len(df) < 60:
        return None
    close = df["close"].astype(float)
    macd = _ema(close, 12) - _ema(close, 26)
    signal = _ema(macd, 9)
    hist = macd - signal
    v = float(hist.iloc[-1]) if len(hist) else np.nan
    return v if np.isfinite(v) else None


def dist_to_52w_high(session: Session, ctx: StockContext) -> float | None:
    df = _load_prices(session, ctx.stock_id, ctx.day, lookback=300)
    if len(df) < 200:
        return None
    close = df["close"].astype(float)
    c = float(close.iloc[-1])
    mx = float(close.tail(252).max())
    if mx <= 0:
        return None
    return (c / mx) - 1.0


def atr_14p(session: Session, ctx: StockContext) -> float | None:
    df = _load_prices(session, ctx.stock_id, ctx.day, lookback=80)
    if len(df) < 20:
        return None
    high = df["high"].astype(float)
    low = df["low"].astype(float)
    close = df["close"].astype(float)
    prev_close = close.shift(1)
    tr = pd.concat([(high - low).abs(), (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1 / 14, adjust=False).mean()
    v = float(atr.iloc[-1])
    c = float(close.iloc[-1])
    if not np.isfinite(v) or c <= 0:
        return None
    return v / c


_BENCH_CACHE: dict[tuple[str, date], pd.DataFrame] = {}


def _benchmark_stock_id(session: Session, market: str) -> int | None:
    sym = settings.benchmark_symbol_kr if market == "KR" else settings.benchmark_symbol_us
    row = session.exec(select(Stock).where(Stock.market == market).where(Stock.symbol == sym)).first()
    return row.id if row and row.id is not None else None


def rs_6m_vs_benchmark(session: Session, ctx: StockContext) -> float | None:
    stock = session.get(Stock, ctx.stock_id)
    if not stock:
        return None
    bench_id = _benchmark_stock_id(session, stock.market)
    if not bench_id:
        return None

    key = (stock.market, ctx.day)
    bench_df = _BENCH_CACHE.get(key)
    if bench_df is None:
        bench_df = _load_prices(session, bench_id, ctx.day, lookback=260)
        _BENCH_CACHE[key] = bench_df

    df = _load_prices(session, ctx.stock_id, ctx.day, lookback=260)
    if len(df) < 130 or len(bench_df) < 130:
        return None
    s0 = float(df["close"].iloc[-126])
    s1 = float(df["close"].iloc[-1])
    b0 = float(bench_df["close"].iloc[-126])
    b1 = float(bench_df["close"].iloc[-1])
    if s0 <= 0 or b0 <= 0:
        return None
    stock_ret = (s1 / s0) - 1.0
    bench_ret = (b1 / b0) - 1.0
    return float(stock_ret - bench_ret)

def _latest_fundamental(session: Session, stock_id: int, key: str, end_day: date) -> float | None:
    row = session.exec(
        select(Fundamental)
        .where(Fundamental.stock_id == stock_id)
        .where(Fundamental.key == key)
        .where(Fundamental.asof_date <= end_day)
        .order_by(Fundamental.asof_date.desc())
        .limit(1)
    ).first()
    return float(row.value) if row else None


def roe_ttm(session: Session, ctx: StockContext) -> float | None:
    return _latest_fundamental(session, ctx.stock_id, "roe_ttm", ctx.day)


def pe_ratio(session: Session, ctx: StockContext) -> float | None:
    return _latest_fundamental(session, ctx.stock_id, "pe_ratio", ctx.day)


def ev_to_ebitda(session: Session, ctx: StockContext) -> float | None:
    ev = _latest_fundamental(session, ctx.stock_id, "enterprise_value", ctx.day)
    ebitda = _latest_fundamental(session, ctx.stock_id, "ebitda", ctx.day)
    if ev is None or ebitda is None or ebitda <= 0:
        return None
    return float(ev / ebitda)


def fcf_yield(session: Session, ctx: StockContext) -> float | None:
    fcf = _latest_fundamental(session, ctx.stock_id, "free_cashflow", ctx.day)
    mcap = _latest_fundamental(session, ctx.stock_id, "market_cap", ctx.day)
    if fcf is None or mcap is None or mcap <= 0:
        return None
    return float(fcf / mcap)


def debt_to_ebitda(session: Session, ctx: StockContext) -> float | None:
    debt = _latest_fundamental(session, ctx.stock_id, "total_debt", ctx.day)
    ebitda = _latest_fundamental(session, ctx.stock_id, "ebitda", ctx.day)
    if debt is None or ebitda is None or ebitda <= 0:
        return None
    return float(debt / ebitda)


def revenue_growth_yoy(session: Session, ctx: StockContext) -> float | None:
    return _latest_fundamental(session, ctx.stock_id, "revenue_growth_yoy", ctx.day)


def earnings_growth_yoy(session: Session, ctx: StockContext) -> float | None:
    return _latest_fundamental(session, ctx.stock_id, "earnings_growth_yoy", ctx.day)


CALCULATORS: dict[str, callable] = {
    "momentum_120d": momentum_120d,
    "volatility_20d": volatility_20d,
    "gdelt_tone": gdelt_tone,
    "news_volume_14d": news_volume_14d,
    "news_tone_change": news_tone_change,
    "news_neg_risk_14d": news_neg_risk_14d,
    "rsi_14": rsi_14,
    "macd_hist": macd_hist,
    "dist_to_52w_high": dist_to_52w_high,
    "rs_6m_vs_benchmark": rs_6m_vs_benchmark,
    "atr_14p": atr_14p,
    "roe_ttm": roe_ttm,
    "pe_ratio": pe_ratio,
    "ev_to_ebitda": ev_to_ebitda,
    "fcf_yield": fcf_yield,
    "debt_to_ebitda": debt_to_ebitda,
    "revenue_growth_yoy": revenue_growth_yoy,
    "earnings_growth_yoy": earnings_growth_yoy,
}

