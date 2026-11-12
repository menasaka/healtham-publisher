"""
Google News headlines for the daily auto-publisher.

Fetches the Google News RSS search feed (same results as news.google.com search),
keeps only real health/medical news (OpenAI judges relevance and picks the health.am health
center for each headline), newest first.
"""
import json
import os
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote, quote_plus

import requests

import site_config as cfg

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; healtham-publisher/1.0)"}
BROWSER_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"}


def resolve_google_news_url(link: str) -> str:
    """
    Google News RSS items link to news.google.com/rss/articles/<id>, not to the publisher. Returns the
    real article address (Google's own "batchexecute" lookup, as news.google.com does in the browser),
    the link itself if it is not a Google News link, or "" if it cannot be resolved (then the article
    lists the source without a link rather than a Google one).
    """
    m = re.search(r"news\.google\.com/(?:rss/)?(?:articles|read)/([^?/#]+)", link or "")
    if not m:
        return link or ""
    gid = m.group(1)
    try:
        page = requests.get(f"https://news.google.com/articles/{gid}", headers=BROWSER_HEADERS, timeout=20)
        sg = re.search(r'data-n-a-sg="([^"]+)"', page.text)
        ts = re.search(r'data-n-a-ts="([^"]+)"', page.text)
        if not (sg and ts):
            raise ValueError("signature not found on the Google News page")
        inner = ["garturlreq", [["X", "X", ["X", "X"], None, None, 1, 1, "US:en", None, 1, None, None, None, None, None, 0, 1],
                                "X", "X", 1, [1, 1, 1], 1, 1, None, 0, 0, None, 0], gid, int(ts.group(1)), sg.group(1)]
        payload = [[["Fbv4je", json.dumps(inner), None, "generic"]]]
        res = requests.post(
            "https://news.google.com/_/DotsSplashUi/data/batchexecute",
            headers={**BROWSER_HEADERS, "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"},
            data="f.req=" + quote(json.dumps(payload)),
            timeout=20,
        )
        res.raise_for_status()
        url = json.loads(json.loads(res.text.split("\n\n", 1)[-1])[0][2])[1]
        if not str(url).startswith("http") or "news.google.com" in url:
            raise ValueError(f"unexpected answer: {str(url)[:80]}")
        return url
    except Exception as e:
        print(f"Notice: could not resolve the Google News link ({e}); the source is listed without a link.")
        return ""


def fetch_google_news(query: str = None, when: str = None) -> list:
    """Returns feed items: [{headline, source, link, published (UTC datetime)}], newest first."""
    query = query or cfg.NEWS_QUERY
    when = when or cfg.NEWS_WINDOW
    url = (
        "https://news.google.com/rss/search?q="
        + quote_plus(f"{query} when:{when}")
        + "&hl=en-US&gl=US&ceid=US:en"
    )
    # Google News sometimes answers 503/429 to cloud servers (GitHub Actions); retry with a pause.
    waits = [10, 30, 60, 120]
    for attempt in range(len(waits) + 1):
        try:
            res = requests.get(url, headers=HEADERS, timeout=20)
            if res.status_code not in (429, 500, 502, 503, 504):
                break
            problem = f"HTTP {res.status_code}"
        except requests.RequestException as e:
            res, problem = None, str(e)
        if attempt == len(waits):
            raise RuntimeError(f"Google News unavailable after {attempt + 1} tries ({problem})")
        print(f"Google News: {problem}, retrying in {waits[attempt]}s...")
        time.sleep(waits[attempt])
    res.raise_for_status()
    root = ET.fromstring(res.content)

    items, seen = [], set()
    for it in root.findall(".//item"):
        title = (it.findtext("title") or "").strip()
        source = (it.findtext("source") or "").strip()
        # Google appends " - Publisher" to titles
        if source and title.endswith(f" - {source}"):
            title = title[: -len(source) - 3].strip()
        if not title or title.lower() in seen:
            continue
        if source.lower() in [s.lower() for s in cfg.NEWS_SOURCE_BLOCKLIST]:
            continue
        seen.add(title.lower())
        try:
            published = parsedate_to_datetime(it.findtext("pubDate"))
        except Exception:
            published = datetime.now(timezone.utc)
        items.append({
            "headline": title,
            "source": source,
            "link": (it.findtext("link") or "").strip(),
            "published": published,
        })

    items.sort(key=lambda x: x["published"], reverse=True)
    return items


def _keyword_filter(items: list) -> list:
    """Fallback when OpenAI is unavailable: headline must contain a medical keyword."""
    medical = re.compile(cfg.NEWS_KEYWORD_RE, re.I)
    return [dict(i, title=i["headline"], topic=cfg.DEFAULT_TOPIC) for i in items if medical.search(i["headline"])]


def pick_medical_headlines(items: list, limit: int = 10) -> list:
    """
    Keeps only headlines that are genuinely about human health, newest first.
    Adds 'title' (an original, SEO-friendly article title for health.am) and 'topic' (a health
    center slug from site_config.TOPICS).
    """
    if not items:
        return []
    candidates = items[:40]
    listing = "\n".join(f"{n}. {i['headline']} ({i['source']})" for n, i in enumerate(candidates))

    try:
        from generator import _get_client, _model
        response = _get_client().chat.completions.create(
            model=_model(),
            messages=[{"role": "user", "content": cfg.NEWS_PICK_PROMPT.format(listing=listing, topics=", ".join(cfg.TOPICS))}],
            response_format={"type": "json_object"},
            max_tokens=1500,
            temperature=0.2,
        )
        data = json.loads(response.choices[0].message.content)
        picked = []
        for p in data.get("picks", []):
            idx = int(p.get("index", -1))
            if 0 <= idx < len(candidates) and p.get("title"):
                topic = str(p.get("topic") or "").strip()
                picked.append(dict(
                    candidates[idx],
                    title=str(p["title"]).strip().replace("—", "-"),
                    topic=topic if topic in cfg.TOPICS else cfg.DEFAULT_TOPIC,
                ))
        picked.sort(key=lambda x: x["published"], reverse=True)
        return picked[:limit]
    except Exception as e:
        print(f"Notice: OpenAI headline selection failed ({e}); using keyword filter.")
        return _keyword_filter(candidates)[:limit]
