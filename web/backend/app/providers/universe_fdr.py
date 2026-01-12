from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import pandas as pd
import FinanceDataReader as fdr

Market = Literal["KR", "US"]


@dataclass(frozen=True)
class UniverseStock:
    market: Market
    symbol: str
    name: str | None


def _safe_stock_listing(code: str) -> pd.DataFrame | None:
    try:
        return fdr.StockListing(code)
    except Exception:
        return None


def _fallback_universe(market: Market, limit: int) -> list[UniverseStock]:
    # Minimal fallback to keep the app usable when listing endpoints are blocked/unavailable.
    if market == "KR":
        base = [
            UniverseStock(market="KR", symbol="005930", name="삼성전자"),
            UniverseStock(market="KR", symbol="000660", name="SK하이닉스"),
            UniverseStock(market="KR", symbol="005380", name="현대차"),
            UniverseStock(market="KR", symbol="035420", name="NAVER"),
            UniverseStock(market="KR", symbol="035720", name="카카오"),
        ]
        return base[:limit]
    base2 = [
        UniverseStock(market="US", symbol="AAPL", name="Apple"),
        UniverseStock(market="US", symbol="MSFT", name="Microsoft"),
        UniverseStock(market="US", symbol="NVDA", name="NVIDIA"),
        UniverseStock(market="US", symbol="AMZN", name="Amazon"),
        UniverseStock(market="US", symbol="GOOGL", name="Alphabet"),
    ]
    return base2[:limit]


def list_universe(*, market: Market, limit: int) -> list[UniverseStock]:
    """
    Try to load KOSPI200/NASDAQ100 via FinanceDataReader if supported.
    If not available, fall back to KOSPI/NASDAQ listing and take the first N rows.
    """
    if market == "KR":
        df = _safe_stock_listing("KOSPI200") or _safe_stock_listing("KOSPI")
        if df is None:
            return _fallback_universe("KR", limit)

        # Normalize column names
        sym_col = "Symbol" if "Symbol" in df.columns else ("Code" if "Code" in df.columns else None)
        name_col = "Name" if "Name" in df.columns else ("Name" if "Name" in df.columns else None)
        if sym_col is None:
            return _fallback_universe("KR", limit)

        out: list[UniverseStock] = []
        for _, row in df.head(limit).iterrows():
            sym = str(row.get(sym_col, "")).strip()
            if not sym:
                continue
            nm = str(row.get(name_col, "")).strip() if name_col else None
            out.append(UniverseStock(market="KR", symbol=sym, name=nm or None))
        return out

    # US
    df = _safe_stock_listing("NASDAQ100") or _safe_stock_listing("NASDAQ")
    if df is None:
        return _fallback_universe("US", limit)

    sym_col = "Symbol" if "Symbol" in df.columns else ("Ticker" if "Ticker" in df.columns else None)
    name_col = "Name" if "Name" in df.columns else None
    if sym_col is None:
        return _fallback_universe("US", limit)

    out2: list[UniverseStock] = []
    for _, row in df.head(limit).iterrows():
        sym = str(row.get(sym_col, "")).strip()
        if not sym:
            continue
        nm = str(row.get(name_col, "")).strip() if name_col else None
        out2.append(UniverseStock(market="US", symbol=sym, name=nm or None))
    return out2

