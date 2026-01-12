from __future__ import annotations

from dataclasses import dataclass
import random
import time

import yfinance as yf
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential_jitter

from app.util.rate_limit import SyncRateLimiter


@dataclass(frozen=True)
class YFOverview:
    symbol: str
    name: str | None
    pe_ratio: float | None
    roe_ttm: float | None  # as fraction (e.g. 0.15)
    market_cap: float | None
    enterprise_value: float | None
    ebitda: float | None
    free_cashflow: float | None
    total_debt: float | None
    revenue_growth_yoy: float | None
    earnings_growth_yoy: float | None
    source: str = "yfinance"

_YF_LIMITER = SyncRateLimiter(min_interval_s=0.6)


@retry(
    reraise=True,
    stop=stop_after_attempt(4),
    wait=wait_exponential_jitter(initial=0.8, max=8.0),
    retry=retry_if_exception_type(Exception),
)
def fetch_overview(symbol: str) -> YFOverview:
    """
    Best-effort US fundamentals via yfinance (no API key).
    Note: This scrapes/uses Yahoo Finance endpoints; availability may vary.
    """
    # Avoid burst requests that can trigger blocking.
    _YF_LIMITER.wait()
    # small jitter to decorrelate concurrent threads
    time.sleep(random.uniform(0.0, 0.25))
    t = yf.Ticker(symbol)
    info = {}
    try:
        info = t.get_info()
    except Exception:
        info = {}

    def fnum(v) -> float | None:
        try:
            if v is None:
                return None
            return float(v)
        except Exception:
            return None

    name = info.get("shortName") or info.get("longName") or None
    pe = fnum(info.get("trailingPE") or info.get("forwardPE"))
    roe = fnum(info.get("returnOnEquity"))
    mcap = fnum(info.get("marketCap"))
    ev = fnum(info.get("enterpriseValue"))
    ebitda = fnum(info.get("ebitda"))
    fcf = fnum(info.get("freeCashflow"))
    debt = fnum(info.get("totalDebt"))
    rev_g = fnum(info.get("revenueGrowth"))
    earn_g = fnum(info.get("earningsGrowth"))

    return YFOverview(
        symbol=symbol,
        name=name,
        pe_ratio=pe,
        roe_ttm=roe,
        market_cap=mcap,
        enterprise_value=ev,
        ebitda=ebitda,
        free_cashflow=fcf,
        total_debt=debt,
        revenue_growth_yoy=rev_g,
        earnings_growth_yoy=earn_g,
    )

