from __future__ import annotations

from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import List
import xml.etree.ElementTree as ET

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential_jitter

from app.providers.news_gdelt import NewsItem
from app.util.rate_limit import AsyncRateLimiter
from app.providers.sentiment_simple_ko import estimate_tone_ko
from app.providers.sentiment_simple_en import estimate_tone_en


_GNEWS_LIMITER = AsyncRateLimiter(min_interval_s=0.8)


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential_jitter(initial=1.0, max=8.0),
    retry=retry_if_exception_type((httpx.TimeoutException, httpx.HTTPError)),
)
async def _rss_get(*, params: dict) -> httpx.Response:
    await _GNEWS_LIMITER.wait()
    async with httpx.AsyncClient(
        timeout=8.0,
        headers={"User-Agent": "Mozilla/5.0"},
        follow_redirects=True,
    ) as client:
        return await client.get("https://news.google.com/rss/search", params=params)


async def fetch_news_google_rss(
    *,
    query: str,
    max_records: int = 20,
    hl: str = "ko",
    gl: str = "KR",
    ceid: str = "KR:ko",
) -> list[NewsItem]:
    """
    Google News RSS (no API key).

    Example:
      https://news.google.com/rss/search?q=Samsung&hl=en-US&gl=US&ceid=US:en
    """
    q = (query or "").strip()
    if not q:
        return []

    params = {
        "q": q,
        "hl": hl,
        "gl": gl,
        "ceid": ceid,
    }

    try:
        r = await _rss_get(params=params)
        r.raise_for_status()
        xml_text = r.text
    except Exception:
        return []

    try:
        root = ET.fromstring(xml_text)
    except Exception:
        return []

    items: list[NewsItem] = []
    for it in root.findall(".//item"):
        title = (it.findtext("title") or "").strip()
        link = (it.findtext("link") or "").strip()
        pub = (it.findtext("pubDate") or "").strip()
        source = (it.findtext("source") or "google-news").strip()
        if not link:
            continue
        published_at = datetime.utcnow()
        if pub:
            try:
                published_at = parsedate_to_datetime(pub)
            except Exception:
                published_at = datetime.utcnow()
        # RSS doesn't provide tone; estimate from title keywords so UI/score isn't always blank.
        if (hl or "").lower().startswith("ko"):
            tone = estimate_tone_ko(title)
        else:
            tone = estimate_tone_en(title)
        items.append(NewsItem(published_at=published_at, title=title, source=source, url=link, tone=tone))
        if len(items) >= max_records:
            break
    return items

