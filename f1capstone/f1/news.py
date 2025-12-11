from __future__ import annotations
from dataclasses import dataclass
from typing import List
import httpx, html, urllib.parse, xml.etree.ElementTree as ET
from django.conf import settings
from django.core.cache import cache

@dataclass
class Article:
    title: str
    url: str
    source: str | None = None
    published_at: str | None = None

GOOGLE_NEWS_BASE = "https://news.google.com/rss/search"

def _gn_url(q: str, *, lang="en-CA", country="CA") -> str:
    params = {
        "q": q,
        "hl": lang,
        "gl": country,
        "ceid": f"{country}:{lang.split('-')[0]}",
    }
    return f"{GOOGLE_NEWS_BASE}?{urllib.parse.urlencode(params)}"

def _parse_rss(xml_text: str, limit: int) -> List[Article]:
    items: List[Article] = []
    root = ET.fromstring(xml_text)
    for item in root.findall("./channel/item")[:limit]:
        title = html.unescape(item.findtext("title") or "")
        link = item.findtext("link") or ""
        pub = item.findtext("pubDate")
        src_el = item.find("{*}source") or item.find("source")
        source = src_el.text if src_el is not None else None
        items.append(Article(title=title, url=link, source=source, published_at=pub))
    return items

def fetch_news_rss(query: str, *, limit: int = 8, timeout: float = 5.0, ttl: int = 1800) -> List[Article]:
    """
    Fetch top N Google News RSS results for query. Cached for `ttl` seconds.
    Cache key is made safe for all backends (no spaces or invalid chars).
    """
    safe_query = urllib.parse.quote_plus(query.strip().lower())

    key = f"gnrss:{safe_query}:{limit}"

    cached = cache.get(key)
    if cached is not None:
        return cached

    try:
        url = _gn_url(query)
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            r = client.get(url)
            r.raise_for_status()
        articles = _parse_rss(r.text, limit)
    except Exception:
        articles = []

    cache.set(key, articles, ttl)
    return articles


def driver_query(given: str, family: str, constructor: str | None = None) -> str:
    parts = [f"{given} {family}", "F1"]
    if constructor:
        parts.append(constructor)
    return " ".join(p for p in parts if p)

def team_query(name: str) -> str:
    return f"{name} F1"
