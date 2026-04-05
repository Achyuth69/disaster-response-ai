"""
agents/news_service.py — Real-time disaster news via GNews API (free tier)
and RSS feeds. Provides current news context to the Data Agent.
"""
from __future__ import annotations

import json
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Optional
import os


@dataclass
class NewsArticle:
    title: str
    description: str
    url: str
    published: str
    source: str


@dataclass
class NewsContext:
    location: str
    disaster_type: str
    articles: list[NewsArticle] = field(default_factory=list)
    summary: str = ""

    def to_context_string(self) -> str:
        if not self.articles:
            return f"No recent news found for {self.disaster_type} in {self.location}."
        lines = [f"Recent news for {self.disaster_type} in {self.location}:"]
        for i, a in enumerate(self.articles[:5], 1):
            lines.append(f"{i}. [{a.source}] {a.title} — {a.description[:120]}")
        return "\n".join(lines)


def fetch_news(location: str, disaster_type: str) -> NewsContext:
    """
    Fetch real disaster news using multiple free sources:
    1. GNews API (if GNEWS_API_KEY set in .env)
    2. RSS feeds from NDTV, Times of India, BBC (no key needed)
    3. ReliefWeb API (UN humanitarian data, no key needed)
    """
    articles: list[NewsArticle] = []

    # Try GNews API first (free tier: 100 req/day)
    gnews_key = os.getenv("GNEWS_API_KEY", "")
    if gnews_key:
        articles.extend(_fetch_gnews(location, disaster_type, gnews_key))

    # Always try RSS feeds (no key needed)
    if len(articles) < 3:
        articles.extend(_fetch_rss(location, disaster_type))

    # Try ReliefWeb (UN data, no key needed)
    if len(articles) < 3:
        articles.extend(_fetch_reliefweb(location, disaster_type))

    # Deduplicate by title
    seen = set()
    unique = []
    for a in articles:
        key = a.title[:50].lower()
        if key not in seen:
            seen.add(key)
            unique.append(a)

    ctx = NewsContext(location=location, disaster_type=disaster_type, articles=unique[:8])
    return ctx


def _fetch_gnews(location: str, disaster_type: str, api_key: str) -> list[NewsArticle]:
    query = urllib.parse.quote(f"{disaster_type} {location}")
    url = (
        f"https://gnews.io/api/v4/search?q={query}"
        f"&lang=en&max=5&apikey={api_key}"
    )
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "DisasterResponseAI/2.0"})
        with urllib.request.urlopen(req, timeout=6) as resp:
            data = json.loads(resp.read().decode())
        articles = []
        for a in data.get("articles", []):
            articles.append(NewsArticle(
                title=a.get("title", ""),
                description=a.get("description", "")[:200],
                url=a.get("url", ""),
                published=a.get("publishedAt", ""),
                source=a.get("source", {}).get("name", "GNews"),
            ))
        return articles
    except Exception:
        return []


def _fetch_rss(location: str, disaster_type: str) -> list[NewsArticle]:
    """Fetch from free RSS feeds — NDTV India, BBC, ReliefWeb."""
    feeds = [
        f"https://feeds.bbci.co.uk/news/world/asia/rss.xml",
        f"https://feeds.feedburner.com/ndtvnews-india-news",
    ]
    articles = []
    loc_lower = location.lower()
    dis_lower = disaster_type.lower()
    keywords = {loc_lower, dis_lower, "disaster", "flood", "earthquake", "cyclone",
                "relief", "rescue", "emergency", "evacuate"}

    for feed_url in feeds:
        try:
            req = urllib.request.Request(
                feed_url,
                headers={"User-Agent": "Mozilla/5.0 DisasterResponseAI/2.0"}
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                content = resp.read().decode("utf-8", errors="replace")
            root = ET.fromstring(content)
            for item in root.iter("item"):
                title = item.findtext("title", "")
                desc = item.findtext("description", "")
                link = item.findtext("link", "")
                pub = item.findtext("pubDate", "")
                combined = (title + " " + desc).lower()
                if any(kw in combined for kw in keywords):
                    articles.append(NewsArticle(
                        title=title,
                        description=desc[:200],
                        url=link,
                        published=pub,
                        source=feed_url.split("/")[2],
                    ))
                if len(articles) >= 5:
                    break
        except Exception:
            continue
        if len(articles) >= 5:
            break

    return articles


def _fetch_reliefweb(location: str, disaster_type: str) -> list[NewsArticle]:
    """Fetch from ReliefWeb API — UN humanitarian data, completely free."""
    params = urllib.parse.urlencode({
        "appname": "DisasterResponseAI",
        "query[value]": f"{disaster_type} {location}",
        "query[fields][]": "title",
        "fields[include][]": "title,body-html,date,source,url",
        "limit": 5,
        "sort[]": "date:desc",
    })
    url = f"https://api.reliefweb.int/v1/reports?{params}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "DisasterResponseAI/2.0"})
        with urllib.request.urlopen(req, timeout=6) as resp:
            data = json.loads(resp.read().decode())
        articles = []
        for item in data.get("data", []):
            f = item.get("fields", {})
            title = f.get("title", "")
            body = f.get("body-html", "")
            # Strip HTML tags simply
            import re
            body_clean = re.sub(r"<[^>]+>", " ", body)[:200]
            sources = f.get("source", [{}])
            source_name = sources[0].get("name", "ReliefWeb") if sources else "ReliefWeb"
            date = f.get("date", {}).get("created", "")
            url_val = f.get("url", "")
            articles.append(NewsArticle(
                title=title,
                description=body_clean,
                url=url_val,
                published=date,
                source=source_name,
            ))
        return articles
    except Exception:
        return []
