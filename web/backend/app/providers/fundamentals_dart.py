from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from zipfile import ZipFile
from io import BytesIO
import xml.etree.ElementTree as ET

import httpx


@dataclass(frozen=True)
class FundamentalPoint:
    asof_date: date
    key: str
    value: float
    source: str


class DartProvider:
    """
    Minimal OpenDART connector:
    - corpCode.zip download + stock_code->corp_code mapping cache
    - basic single-account financial statement endpoint call

    NOTE: DART is KR-only, and requires corp_code (not stock_code).
    """

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    async def fetch_fundamentals(self, *, corp_code: str) -> list[FundamentalPoint]:
        # Minimal example: fetch latest annual financial statement (as raw points)
        today = date.today()
        year = today.year - 1
        params = {
            "crtfc_key": self.api_key,
            "corp_code": corp_code,
            "bsns_year": str(year),
            "reprt_code": "11011",  # annual report
        }
        async with httpx.AsyncClient(timeout=20.0) as client:
            r = await client.get("https://opendart.fss.or.kr/api/fnlttSinglAcnt.json", params=params)
            r.raise_for_status()
            data = r.json()

        if data.get("status") != "000":
            # Return empty; caller can decide how to handle.
            return []

        out: list[FundamentalPoint] = []
        for row in data.get("list") or []:
            key = (row.get("account_nm") or row.get("account_id") or "").strip()
            v = row.get("thstrm_amount")
            try:
                val = float(str(v).replace(",", ""))
            except Exception:
                continue
            out.append(FundamentalPoint(asof_date=date(year, 12, 31), key=key, value=val, source="opendart"))
        return out

    async def get_corp_code_by_stock_code(self, *, stock_code: str) -> str | None:
        m = await _load_corp_code_map(self.api_key)
        return m.get(stock_code)


async def _download_corpcode_zip(api_key: str) -> bytes:
    params = {"crtfc_key": api_key}
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get("https://opendart.fss.or.kr/api/corpCode.xml", params=params)
        r.raise_for_status()
        return r.content


def _cache_path() -> Path:
    return Path("./data/dart_corp_codes.json")


async def _load_corp_code_map(api_key: str) -> dict[str, str]:
    """
    Returns mapping: stock_code -> corp_code
    """
    p = _cache_path()
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass

    content = await _download_corpcode_zip(api_key)
    z = ZipFile(BytesIO(content))
    # zip contains CORPCODE.xml
    name = next((n for n in z.namelist() if n.lower().endswith(".xml")), None)
    if not name:
        return {}
    xml_bytes = z.read(name)

    root = ET.fromstring(xml_bytes)
    mapping: dict[str, str] = {}
    for item in root.findall(".//list"):
        corp_code = (item.findtext("corp_code") or "").strip()
        stock_code = (item.findtext("stock_code") or "").strip()
        if corp_code and stock_code:
            mapping[stock_code] = corp_code

    os.makedirs(p.parent, exist_ok=True)
    p.write_text(json.dumps(mapping, ensure_ascii=False), encoding="utf-8")
    return mapping

