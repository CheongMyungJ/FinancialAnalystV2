from __future__ import annotations

from dataclasses import dataclass

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential_jitter

from app.util.rate_limit import AsyncRateLimiter, RateLimitError


@dataclass(frozen=True)
class CompanyOverview:
    symbol: str
    name: str | None
    market_cap: float | None
    pe_ratio: float | None
    roe_ttm: float | None
    profit_margin: float | None
    source: str = "alphavantage"

_AV_LIMITER = AsyncRateLimiter(min_interval_s=12.5)  # free tier: ~5 req/min


@retry(
    reraise=True,
    stop=stop_after_attempt(5),
    wait=wait_exponential_jitter(initial=1.0, max=15.0),
    retry=retry_if_exception_type((httpx.TimeoutException, httpx.HTTPError, RateLimitError)),
)
async def _fetch_overview_json(*, api_key: str, symbol: str) -> dict:
    await _AV_LIMITER.wait()
    params = {
        "function": "OVERVIEW",
        "symbol": symbol,
        "apikey": api_key,
    }
    async with httpx.AsyncClient(timeout=15.0, headers={"User-Agent": "Mozilla/5.0"}) as client:
        r = await client.get("https://www.alphavantage.co/query", params=params)
        r.raise_for_status()
        data = r.json()
    # AlphaVantage often returns 200 with a rate-limit note instead of 429.
    if isinstance(data, dict) and any(k in data for k in ("Note", "Information")):
        raise RateLimitError(data.get("Note") or data.get("Information") or "alphavantage rate limited")
    return data if isinstance(data, dict) else {}


async def fetch_company_overview(*, api_key: str, symbol: str) -> CompanyOverview:
    """
    Alpha Vantage Company Overview (US).
    https://www.alphavantage.co/documentation/
    """
    data = await _fetch_overview_json(api_key=api_key, symbol=symbol)

    def fnum(k: str) -> float | None:
        v = data.get(k)
        if v in (None, "", "None"):
            return None
        try:
            return float(v)
        except Exception:
            return None

    return CompanyOverview(
        symbol=symbol,
        name=data.get("Name"),
        market_cap=fnum("MarketCapitalization"),
        pe_ratio=fnum("PERatio"),
        roe_ttm=fnum("ReturnOnEquityTTM"),
        profit_margin=fnum("ProfitMargin"),
    )

