"""
Publishes articles to health.am (Next.js + Payload CMS on www.health.am).

Input is the same as the other publishers: the formatted HTML body from processor.py and the
featured image file. The HTML is converted to Payload's rich-text format (Lexical); question H2s
give the article its "On this page" menu and FAQPage schema on the site, so no separate FAQ block
is added. Saving in Payload refreshes the site's cache, so the article is live at once.

Needs HEALTHAM_EMAIL and HEALTHAM_PASSWORD: an admin user of www.health.am/admin, ideally one
created only for the autopilot (Users > Create new).
"""
import html
import json
import os
import re
import time
import unicodedata
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser

import requests

import site_config as cfg
from processor import extract_yoast_description

UA = {"User-Agent": "healtham-publisher/1.0 (+https://www.health.am)"}
_token = None
_token_at = 0.0
# Payload login sessions expire after 2 hours. The Streamlit app runs for days, so a login is reused
# for 30 minutes at most, and a save refused with 401/403 signs in again and retries once.
TOKEN_MAX_AGE = 30 * 60
_topic_ids = {}


# ---------------------------------------------------------------- API

def _api() -> str:
    return os.getenv("PAYLOAD_API_URL", cfg.PAYLOAD_API_URL).rstrip("/")


def payload_configured() -> bool:
    return bool(os.getenv("HEALTHAM_EMAIL") and os.getenv("HEALTHAM_PASSWORD"))


def _login(force: bool = False) -> str:
    global _token, _token_at
    if _token and not force and time.time() - _token_at < TOKEN_MAX_AGE:
        return _token
    if not payload_configured():
        raise RuntimeError("HEALTHAM_EMAIL / HEALTHAM_PASSWORD are not set.")
    res = requests.post(
        f"{_api()}/users/login",
        json={"email": os.getenv("HEALTHAM_EMAIL"), "password": os.getenv("HEALTHAM_PASSWORD")},
        headers=UA,
        timeout=30,
    )
    if res.status_code != 200 or not res.json().get("token"):
        raise RuntimeError(f"Login to {_api()} failed: {res.status_code} - {res.text[:200]}")
    _token = res.json()["token"]
    _token_at = time.time()
    return _token


def _post(path: str, **kwargs) -> requests.Response:
    """POST with the login token; if the server refuses (401/403, e.g. an expired session), sign in again and retry once."""
    res = requests.post(f"{_api()}/{path}", headers=_headers(), **kwargs)
    if res.status_code in (401, 403):
        _login(force=True)
        res = requests.post(f"{_api()}/{path}", headers=_headers(), **kwargs)
    return res


def _headers(auth: bool = True) -> dict:
    h = dict(UA)
    if auth:
        h["Authorization"] = f"JWT {_login()}"
    return h


def _get(path: str, params: dict = None, auth: bool = True):
    res = requests.get(f"{_api()}/{path}", params=params, headers=_headers(auth), timeout=45)
    if res.status_code != 200:
        raise RuntimeError(f"GET {path} failed: {res.status_code} - {res.text[:300]}")
    return res.json()


def _where(**conditions) -> dict:
    """{"slug": ("equals", "x")} -> Payload's bracket query params: where[slug][equals]=x"""
    params = {}
    for field, (op, value) in conditions.items():
        params[f"where[{field}][{op}]"] = value
    return params


def topic_id(slug: str) -> int:
    if slug not in _topic_ids:
        docs = _get("topics", {**_where(slug=("equals", slug)), "limit": 1, "depth": 0}, auth=False).get("docs", [])
        if not docs:
            raise RuntimeError(f"No health center with slug '{slug}' on the site.")
        _topic_ids[slug] = docs[0]["id"]
    return _topic_ids[slug]


# ---------------------------------------------------------------- HTML -> Lexical

FORMAT = {"strong": 1, "em": 2, "underline": 8}
SITE_HOST_RE = re.compile(r"^https?://(?:www\.)?health\.am(?=/|$)", re.I)


def _el(**extra) -> dict:
    return {"direction": None, "format": "", "indent": 0, "version": 1, **extra}


def _text(text: str, fmt: int) -> dict:
    return {"type": "text", "text": text, "format": fmt, "mode": "normal", "style": "", "detail": 0, "version": 1}


class _Lexical(HTMLParser):
    """
    Converts the HTML that processor.py produces (h2-h4, p, ul/ol/li, strong/b, em/i, u, a, br,
    blockquote) into a Lexical document as Payload's editor stores it. Same node shapes as the
    site's own importer (src/lib/richtext.ts toLexical).
    """

    BLOCKS = {"p": "paragraph", "h2": "h2", "h3": "h3", "h4": "h4", "blockquote": "quote"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = []
        self.block = None          # current block node (paragraph, heading, quote or listitem)
        self.lists = []            # open list nodes
        self.formats = []          # active format names
        self.link = None           # current link node

    def _inline_target(self) -> list:
        if self.block is None:
            self._open("paragraph")
        return (self.link or self.block)["children"]

    def _open(self, kind: str):
        self._close()
        if kind == "paragraph":
            node = _el(type="paragraph", children=[], textFormat=0, textStyle="")
        elif kind == "quote":
            node = _el(type="quote", children=[])
        else:
            node = _el(type="heading", tag=kind, children=[])
        self.block = node

    def _close(self):
        b, self.block, self.link = self.block, None, None
        if b is None or b["type"] == "listitem":
            return
        if self._trim(b["children"]):
            self.root.append(b)

    @staticmethod
    def _trim(children: list) -> bool:
        """Strip outer whitespace; True if any text is left."""
        texts = [c for c in children if c["type"] == "text"] + [g for c in children if c["type"] == "link" for g in c["children"]]
        if not "".join(t["text"] for t in texts).strip():
            return False
        first, last = children[0], children[-1]
        first = first["children"][0] if first["type"] == "link" and first["children"] else first
        last = last["children"][-1] if last["type"] == "link" and last["children"] else last
        if first.get("type") == "text":
            first["text"] = first["text"].lstrip()
        if last.get("type") == "text":
            last["text"] = last["text"].rstrip()
        return True

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in ("ul", "ol"):
            # processor.py makes flat lists; a nested list is read as items of the outer one.
            if not self.lists:
                self._close()
                kind = "bullet" if tag == "ul" else "number"
                self.lists.append(_el(type="list", listType=kind, tag=tag, start=1, children=[]))
            else:
                self.lists.append(self.lists[-1])
        elif tag == "li" and self.lists:
            lst = self.lists[-1]
            item = _el(type="listitem", value=len(lst["children"]) + 1, children=[])
            lst["children"].append(item)
            self.block, self.link = item, None
        elif tag in self.BLOCKS:
            self._open(self.BLOCKS[tag])
        elif tag in ("strong", "b"):
            self.formats.append("strong")
        elif tag in ("em", "i"):
            self.formats.append("em")
        elif tag == "u":
            self.formats.append("underline")
        elif tag == "a" and a.get("href"):
            href = SITE_HOST_RE.sub("", a["href"].strip()) or "/"
            href = href.replace(" ", "%20")
            node = {"type": "link", "version": 3, "children": [], "direction": None, "format": "", "indent": 0,
                    "fields": {"linkType": "custom", "url": href, "newTab": href.startswith("http")}}
            self._inline_target().append(node)
            self.link = node
        elif tag == "br":
            self._inline_target().append({"type": "linebreak", "version": 1})

    def handle_endtag(self, tag):
        if tag in ("ul", "ol"):
            if self.lists:
                lst = self.lists.pop()
                if not self.lists:
                    lst["children"] = [i for i in lst["children"] if self._trim(i["children"])] if lst["children"] else []
                    for n, item in enumerate(lst["children"], start=1):
                        item["value"] = n
                    if lst["children"]:
                        self.root.append(lst)
            self.block, self.link = None, None
        elif tag == "li":
            self.link = None
        elif tag in self.BLOCKS:
            self._close()
        elif tag in ("strong", "b", "em", "i", "u"):
            want = {"strong": "strong", "b": "strong", "em": "em", "i": "em", "u": "underline"}[tag]
            for i in range(len(self.formats) - 1, -1, -1):
                if self.formats[i] == want:
                    del self.formats[i]
                    break
        elif tag == "a":
            self.link = None

    def handle_data(self, data):
        text = re.sub(r"\s+", " ", data)
        if not text.strip() and (self.block is None or not (self.link or self.block)["children"]):
            return
        fmt = sum(FORMAT[f] for f in set(self.formats))
        target = self._inline_target()
        last = target[-1] if target else None
        if last and last["type"] == "text" and last["format"] == fmt:
            last["text"] += text
        else:
            target.append(_text(text, fmt))


def html_to_lexical(markup: str) -> dict:
    markup = re.sub(r"<script\b[^>]*>.*?</script>", "", markup or "", flags=re.S | re.I)
    markup = re.sub(r"<!--.*?-->", "", markup, flags=re.S)
    parser = _Lexical()
    parser.feed(markup)
    parser.close()
    parser._close()
    return {"root": {"type": "root", "children": parser.root, "direction": None, "format": "", "indent": 0, "version": 1}}


def lexical_text(doc: dict) -> str:
    """Plain text of a Lexical document (for duplicate checks and key points)."""
    out = []

    def walk(n):
        if n.get("type") == "text":
            out.append(n.get("text", ""))
        for c in n.get("children", []) or []:
            walk(c)
        if n.get("type") in ("paragraph", "heading", "listitem", "quote"):
            out.append("\n")

    walk((doc or {}).get("root", {}))
    return re.sub(r"\n{2,}", "\n", "".join(out)).strip()


# ---------------------------------------------------------------- helpers

def slugify(title: str) -> str:
    s = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-z0-9\s-]", "", s.lower())
    return re.sub(r"[\s-]+", "-", s).strip("-")[:90].rstrip("-") or "article"


def unique_slug(slug: str, tid: int) -> str:
    """slug, slug-2, ... not used yet by another article in the same health center."""
    base, n = slug, 1
    while True:
        found = _get("articles", {**_where(slug=("equals", slug), topic=("equals", tid)), "limit": 1, "depth": 0}, auth=False)
        if not found.get("docs"):
            return slug
        n += 1
        slug = f"{base}-{n}"


def upload_image(path: str, title: str):
    """Uploads the featured image to the media library. Returns the media id or None."""
    if not path or not os.path.exists(path):
        return None
    ext = os.path.splitext(path)[1].lower().lstrip(".") or "jpg"
    ctype = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}.get(ext, "image/jpeg")
    name = f"{slugify(title)[:70]}-{datetime.now(timezone.utc):%Y%m%d%H%M%S}.{ext}"
    with open(path, "rb") as f:
        content = f.read()  # bytes, so a retry can send the file again
    res = _post(
        "media",
        files={"file": (name, content, ctype)},
        data={"_payload": json.dumps({"alt": title})},
        timeout=120,
    )
    if res.status_code not in (200, 201):
        print(f"⚠️ Image upload failed: {res.status_code} - {res.text[:300]}")
        return None
    return (res.json().get("doc") or {}).get("id")


# ---------------------------------------------------------------- publish

def publish_payload_post(
    title: str,
    content: str,
    image_paths: list = None,
    topic: str = None,
    content_type: str = None,
    key_points: list = None,
    news: dict = None,
    extra_html: str = "",
):
    """
    Creates a published article. Returns a dict shaped like the other publishers' results
    (link, edit_url, featured_ok, ...) or None on failure.
    """
    if not payload_configured():
        print("❌ HEALTHAM_EMAIL / HEALTHAM_PASSWORD are not set.")
        return None
    site = os.getenv("SITE_PUBLIC_URL", cfg.SITE_URL).rstrip("/")
    topic = topic if topic in cfg.TOPICS else cfg.DEFAULT_TOPIC
    try:
        tid = topic_id(topic)
        slug = unique_slug(slugify(title), tid)
        media_id = None
        for p in image_paths or []:
            media_id = upload_image(p, title)
            if media_id:
                break

        body = html_to_lexical(content + (extra_html or ""))
        metadesc = extract_yoast_description(content)
        doc = {
            "language": "en",
            "contentType": content_type or cfg.MANUAL_CONTENT_TYPE,
            "topic": tid,
            "title": title,
            "slug": slug,
            "excerpt": metadesc,
            "body": body,
            "publishedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "seoDescription": metadesc,
            "reviewStatus": cfg.REVIEW_STATUS,
            "legacy": {"source": cfg.AUTOPILOT_NEWS_SOURCE if news else cfg.AUTOPILOT_SOURCE},
        }
        if key_points:
            doc["keyPoints"] = [{"text": k} for k in key_points if k]
        if media_id:
            doc["mainImage"] = media_id
            doc["mainImageAlt"] = title
        if news:
            doc["sources"] = [{"title": f'{news.get("headline", "")} ({news.get("source", "")})', "url": news.get("link", "")}]

        res = _post("articles", json=doc, timeout=90)
        if res.status_code not in (200, 201):
            print(f"❌ Publish failed: {res.status_code} - {res.text[:600]}")
            return None
        created = res.json().get("doc") or {}
        link = f"{site}/{topic}/{slug}"
        edit_url = f"{os.getenv('PAYLOAD_ADMIN_URL', cfg.PAYLOAD_ADMIN_URL).rstrip('/')}/collections/articles/{created.get('id')}"
        print(f"\n✅ Published: {link}")
        print(f"🖼️ Featured image: {'set' if media_id else 'NOT set'}")
        return {
            "id": created.get("id"),
            "status": "publish",
            "link": link,
            "preview_url": link,
            "edit_url": edit_url,
            "yoast_metadesc": metadesc,
            "yoast_saved": True,
            "featured_media_id": media_id,
            "featured_ok": bool(media_id),
            # The site builds FAQPage schema from the article's question headings.
            "schema_in_head": True,
            "schema_script": "",
            "target": "payload",
            "topic": topic,
            "slug": slug,
        }
    except Exception as e:
        print(f"❌ Exception while publishing: {e}")
        return None


def recent_posts(days: int = 10) -> list:
    """
    Recent articles in the shape autopublish.py expects:
    [{date_gmt, title: {rendered}, content: {rendered}, autopilot_news: bool}], newest first.
    """
    after = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    data = _get("articles", {
        **_where(createdAt=("greater_than", after)),
        "sort": "-createdAt", "limit": 100, "depth": 0,
        "select[title]": "true", "select[createdAt]": "true", "select[sources]": "true",
        "select[legacy]": "true", "select[excerpt]": "true",
    }, auth=False)
    out = []
    for d in data.get("docs", []):
        sources = " ".join(html.escape(s.get("title") or "") for s in d.get("sources") or [])
        out.append({
            "date_gmt": (d.get("createdAt") or "")[:19],
            "title": {"rendered": d.get("title", "")},
            "content": {"rendered": f"{sources} {html.escape(d.get('excerpt') or '')}"},
            "autopilot_news": (d.get("legacy") or {}).get("source") == cfg.AUTOPILOT_NEWS_SOURCE,
        })
    return out
