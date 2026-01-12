from __future__ import annotations

from app.providers.fundamentals_yfinance import YFOverview, fetch_overview


def fetch_overview_kr(stock_code: str) -> YFOverview:
    """
    KR fundamentals via Yahoo Finance using yfinance.

    Heuristic:
    - Try KOSPI suffix '.KS' first (KOSPI200 is KOSPI).
    - Fallback to KOSDAQ suffix '.KQ'.
    """
    code = (stock_code or "").strip()
    if not code:
        return fetch_overview(code)

    # If caller already passed a Yahoo-style ticker, just use it.
    if "." in code:
        return fetch_overview(code)

    # First try KOSPI suffix.
    try:
        ks = fetch_overview(f"{code}.KS")
        # yfinance may return an "empty" info dict without raising.
        if any(v is not None for v in (ks.pe_ratio, ks.roe_ttm, ks.market_cap, ks.name)):
            return ks
    except Exception:
        pass
    # Fallback to KOSDAQ suffix.
    return fetch_overview(f"{code}.KQ")

