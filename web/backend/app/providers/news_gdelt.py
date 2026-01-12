from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import httpx
from httpx import HTTPStatusError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential_jitter

from app.util.rate_limit import AsyncRateLimiter
from app.providers.sentiment_simple_en import estimate_tone_en
from app.providers.sentiment_simple_ko import estimate_tone_ko


@dataclass(frozen=True)
class NewsItem:
    published_at: datetime
    title: str
    source: str | None
    url: str
    tone: float | None


_GDELT_LIMITER = AsyncRateLimiter(min_interval_s=0.8)


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential_jitter(initial=1.0, max=8.0),
    retry=retry_if_exception_type((httpx.TimeoutException, httpx.HTTPError)),
)
async def _gdelt_get(*, params: dict) -> httpx.Response:
    await _GDELT_LIMITER.wait()
    async with httpx.AsyncClient(
        timeout=8.0,
        headers={"User-Agent": "Mozilla/5.0"},
        follow_redirects=True,
    ) as client:
        return await client.get("https://api.gdeltproject.org/api/v2/doc/doc", params=params)


async def fetch_news_gdelt(
    *,
    query: str,
    max_records: int = 20,
    mode: str = "ArtList",
) -> list[NewsItem]:
    """
    Fetch news list from GDELT 2.1 DOC API.

    DOC API: https://api.gdeltproject.org/api/v2/doc/doc
    """
    params = {
        "query": query,
        "mode": mode,
        "format": "json",
        "maxrecords": str(max_records),
        "sort": "HybridRel",
    }
    try:
        r = await _gdelt_get(params=params)
        r.raise_for_status()
    except HTTPStatusError as e:
        # Rate limit / transient errors should not break the app.
        status = getattr(e.response, "status_code", None)
        if status in (429, 500, 502, 503, 504):
            return []
        raise
    except Exception:
        return []

    try:
        data = r.json()
    except Exception:
        # Occasionally GDELT returns non-JSON (HTML/error pages). Treat as no news.
        return []

    articles = data.get("articles") or []
    out: list[NewsItem] = []
    for a in articles:
        # seendate may be like "20250102123456" or "20260108T020000Z"
        seendate = a.get("seendate")
        published_at = datetime.utcnow()
        if isinstance(seendate, str):
            try:
                published_at = datetime.strptime(seendate, "%Y%m%d%H%M%S")
            except Exception:
                try:
                    published_at = datetime.strptime(seendate, "%Y%m%dT%H%M%SZ")
                except Exception:
                    published_at = datetime.utcnow()
        out.append(
            NewsItem(
                published_at=published_at,
                title=a.get("title") or "",
                source=a.get("sourceCountry") or a.get("source") or None,
                url=a.get("url") or "",
                # DOC API often doesn't include tone. If missing, estimate from title (EN/KO).
                tone=(
                    float(a["tone"])
                    if "tone" in a and a["tone"] is not None
                    else (estimate_tone_ko(a.get("title") or "") or estimate_tone_en(a.get("title") or ""))
                ),
            )
        )
    return out

