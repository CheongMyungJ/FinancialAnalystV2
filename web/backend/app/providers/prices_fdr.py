from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal

import FinanceDataReader as fdr
import pandas as pd
import httpx
from io import StringIO
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential_jitter

from app.util.rate_limit import SyncRateLimiter

Market = Literal["KR", "US"]

_STOOQ_LIMITER = SyncRateLimiter(min_interval_s=0.4)


@dataclass(frozen=True)
class DailyBar:
    date: date
    open: float
    high: float
    low: float
    close: float
    volume: float | None


def _fetch_stooq_csv(symbol: str, start: str | None, end: str | None) -> pd.DataFrame | None:
    sym = symbol.strip().lower()
    if not sym.endswith(".us"):
        sym = f"{sym}.us"
    url = f"https://stooq.com/q/d/l/?s={sym}&i=d"
    try:
        r = _stooq_get(url)
        r.raise_for_status()
        txt = r.text
        df = pd.read_csv(StringIO(txt))
        if "Date" not in df.columns:
            return None
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        df = df.dropna(subset=["Date"])
        if start:
            df = df[df["Date"] >= pd.to_datetime(start)]
        if end:
            df = df[df["Date"] <= pd.to_datetime(end)]
        return df.set_index("Date")
    except Exception:
        return None


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential_jitter(initial=0.8, max=6.0),
    retry=retry_if_exception_type((httpx.TimeoutException, httpx.HTTPError)),
)
def _stooq_get(url: str) -> httpx.Response:
    _STOOQ_LIMITER.wait()
    return httpx.get(url, timeout=20.0, headers={"User-Agent": "Mozilla/5.0"}, follow_redirects=True)


def fetch_prices_daily(
    *,
    market: Market,
    symbol: str,
    start: str | None = None,
    end: str | None = None,
) -> list[DailyBar]:
    """
    Fetch daily OHLCV bars.

    Notes:
    - KR uses numeric symbol like '005930'
    - US uses ticker like 'AAPL'
    """
    # FinanceDataReader accepts start/end as 'YYYY-MM-DD' strings.
    df = None
    try:
        df = fdr.DataReader(symbol, start, end)
    except Exception:
        df = None

    # Fallback: for US tickers, try Stooq (free CSV) if FDR is blocked/unavailable.
    if (df is None or getattr(df, "empty", True)) and market == "US":
        df = _fetch_stooq_csv(symbol, start, end)

    if df is None:
        return []

    df = df.reset_index()
    if "Date" not in df.columns:
        # FinanceDataReader often returns a DatetimeIndex with name None -> 'index' column after reset_index().
        if len(df.columns) > 0:
            df = df.rename(columns={df.columns[0]: "Date"})

    out: list[DailyBar] = []
    for _, row in df.iterrows():
        d = row.get("Date")
        if d is None:
            continue
        out.append(
            DailyBar(
                date=d.date() if hasattr(d, "date") else d,
                open=float(row.get("Open", row.get("open", 0.0))),
                high=float(row.get("High", row.get("high", 0.0))),
                low=float(row.get("Low", row.get("low", 0.0))),
                close=float(row.get("Close", row.get("close", 0.0))),
                volume=float(row["Volume"]) if "Volume" in row and row["Volume"] is not None else None,
            )
        )
    return out

