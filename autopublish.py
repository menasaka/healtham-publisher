"""
Daily news autopilot for health.am (Payload CMS on www.health.am).

Run by GitHub Actions (.github/workflows/autopublish.yml) every hour during the day.
Each run publishes whichever slot is due (local time, America/Los_Angeles) but not done yet:
    from 9am  -> slot 1: newest health/medical headline not yet covered
    from 2pm  -> slot 2: the next one
So a late or skipped GitHub run is made up by the next hourly run.

Safety:
- Skips a headline that already has a post (checked on the live site).
- Publishes at most N posts per day for slot N, so a re-run never double-posts.

Usage:
    python autopublish.py                # normal scheduled run (checks the clock)
    python autopublish.py --slot 1       # force a slot now (manual run)
    python autopublish.py --dry-run      # pick a headline, don't write or publish
"""
import argparse
import html
import os
import re
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import requests
from dotenv import load_dotenv

load_dotenv()


def load_combined_secret(var: str = "AUTOMATION") -> None:
    """
    Lets all settings live in ONE GitHub secret (same format as Streamlit secrets or .env):
        OPENAI_API_KEY = "sk-..."      or      OPENAI_API_KEY=sk-...
    Values never get printed; only the names that were found.
    """
    blob = os.getenv(var, "")
    if not blob.strip():
        return
    found = []
    for line in blob.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("[") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip().removeprefix("export ").strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if re.fullmatch(r"[A-Z][A-Z0-9_]*", key) and value and not os.getenv(key):
            os.environ[key] = value
            found.append(key)
    print(f"Settings loaded from {var} secret: {', '.join(found) or 'none'}")


load_combined_secret()

import site_config as cfg
import news

def _norm(text: str) -> str:
    text = html.unescape(re.sub(r"<[^>]+>", " ", text or ""))
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def recent_site_posts(days: int = 10) -> list:
    """Articles created on health.am in the last `days` days (title, news source, excerpt), newest first."""
    from payload_publisher import recent_posts
    return recent_posts(days)


def auto_posts_today(posts: list, tz: ZoneInfo) -> int:
    """How many autopilot news posts went live today (local date)."""
    today = datetime.now(tz).date()
    count = 0
    for p in posts:
        if not p.get("autopilot_news"):
            continue
        try:
            published = datetime.fromisoformat(p["date_gmt"]).replace(tzinfo=ZoneInfo("UTC")).astimezone(tz)
        except Exception:
            continue
        if published.date() == today:
            count += 1
    return count


def already_covered(item: dict, posts: list) -> bool:
    headline = _norm(item["headline"])
    title = _norm(item.get("title", ""))
    for p in posts:
        content = _norm(p.get("content", {}).get("rendered", ""))
        if headline and headline in content:
            return True
        if title and title == _norm(p.get("title", {}).get("rendered", "")):
            return True
    return False


def pick_next_headline(posts: list) -> dict:
    for window in (cfg.NEWS_WINDOW, cfg.NEWS_FALLBACK_WINDOW):
        items = news.fetch_google_news(when=window)
        print(f"Google News ({window}): {len(items)} headlines")
        picks = news.pick_medical_headlines(items)
        print(f"Medical headlines: {len(picks)}")
        for p in picks:
            print(f"   - [{p['published']:%m-%d %H:%M}] {p['headline']} ({p['source']})")
        for p in picks:
            if not already_covered(p, posts):
                return p
            print(f"   (already covered: {p['headline']})")
    return None


def publish_news_post(item: dict) -> dict:
    from generator import generate_article_content, generate_key_points
    from processor import process_and_format_article
    from image_maker import create_unique_images
    from publisher import publish_post

    title = item["title"]
    topic = item.get("topic") or cfg.DEFAULT_TOPIC
    print(f"\n🚀 Writing: {title}\n   from: {item['headline']} ({item['source']})\n   health center: {topic}")
    raw = generate_article_content(title, news=item)
    formatted = process_and_format_article(raw)
    key_points = generate_key_points(title, formatted)
    images = create_unique_images(title)
    # The news report is stored as the article's source (shown under it as "Sources").
    return publish_post(
        title=title,
        content=formatted,
        image_paths=images,
        topic=topic,
        key_points=key_points,
        content_type=cfg.NEWS_CONTENT_TYPE,
        news=item,
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slot", type=int, choices=range(1, len(cfg.PUBLISH_HOURS) + 1),
                    help="force this slot now instead of checking the clock")
    ap.add_argument("--dry-run", action="store_true", help="only pick a headline")
    args = ap.parse_args()

    tz = ZoneInfo(cfg.TIMEZONE)
    now = datetime.now(tz)
    slot = args.slot
    if slot is None:
        # Catch-up: GitHub's scheduled runs can start late or be skipped, so instead of
        # requiring the exact hour, use the latest slot whose time has passed today.
        # The "done_today" check below makes sure each slot only publishes once.
        slot = sum(1 for h in cfg.PUBLISH_HOURS if now.hour >= h)
        if slot == 0:
            print(f"{now:%Y-%m-%d %H:%M %Z}: before the first publish hour {cfg.PUBLISH_HOURS}; nothing to do.")
            return 0
        if now.hour > cfg.LAST_CATCH_UP_HOUR:
            print(f"{now:%Y-%m-%d %H:%M %Z}: past {cfg.LAST_CATCH_UP_HOUR}:59, too late to catch up today.")
            return 0
    print(f"{now:%Y-%m-%d %H:%M %Z}: slot {slot}")

    posts = recent_site_posts()
    done_today = auto_posts_today(posts, tz)
    if done_today >= slot and not args.dry_run:
        print(f"Already {done_today} news post(s) today; slot {slot} is done.")
        return 0

    item = pick_next_headline(posts)
    if not item:
        print("No new medical headline found. Nothing published.")
        return 0
    print(f"\n✅ Picked: {item['headline']} ({item['source']})\n   Article title: {item['title']}\n   Health center: {item.get('topic')}")
    if args.dry_run:
        return 0

    post = publish_news_post(item)
    if not post:
        print("❌ Publishing failed.")
        return 1
    print(f"\n🎉 Published: {post.get('link')}")
    if not post.get("featured_ok"):
        print("⚠️ Featured image was not set.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
