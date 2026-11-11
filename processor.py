import html
import os
import re
import random
import time

import requests

import site_config as cfg

# Shortcodes, keywords and the fallback links come from site_config.py
SHORTCODES_LIST = cfg.SHORTCODES_LIST
KEYWORDS_TO_BOLD = cfg.KEYWORDS_TO_BOLD
INTERNAL_LINKS = cfg.INTERNAL_LINKS
FALLBACK_LINK_SENTENCE = cfg.FALLBACK_LINK_SENTENCE

_links_cache = {"at": 0.0, "links": None}


def get_internal_links() -> list:
    """
    The links articles may use, edited in the health.am admin (Site settings > Article links).
    Read from the site's public API, re-read every 5 minutes; site_config.INTERNAL_LINKS is the
    fallback when the site cannot be reached or the list is empty.
    """
    if _links_cache["links"] is not None and time.time() - _links_cache["at"] < 300:
        return _links_cache["links"]
    links = []
    try:
        api = os.getenv("PAYLOAD_API_URL", cfg.PAYLOAD_API_URL).rstrip("/")
        res = requests.get(f"{api}/globals/site-settings", params={"depth": 0},
                           headers={"User-Agent": "healtham-publisher/1.0"}, timeout=20)
        res.raise_for_status()
        for row in res.json().get("articleLinks") or []:
            url = str(row.get("url") or "").strip()
            keywords = [k.strip() for k in str(row.get("keywords") or "").split(",") if k.strip()]
            if url and keywords:
                links.append({"keywords": keywords, "html": f'<a href="{html.escape(url, quote=True)}">{html.escape(keywords[0])}</a>'})
    except Exception as e:
        print(f"Notice: could not read Article links from the site ({e}); using the built-in list.")
    if not links:
        links = list(cfg.INTERNAL_LINKS)
    _links_cache.update(at=time.time(), links=links)
    return links

H2_RE = r'<h2\b[^>]*>.*?</h2>'


def format_h2_tags(content: str) -> str:
    """
    Converts all Markdown and HTML headings to the site's H2 tag.
    Ensures every heading ends with a question mark.
    """
    if not content:
        return ""

    def replace_h2(match):
        heading_text = re.sub(r'[*_`#]', '', match.group(1).strip())
        if not heading_text.endswith('?'):
            heading_text += '?'
        return f'{cfg.H2_OPEN_TAG}{heading_text}</h2>'

    content = re.sub(r'^#{1,6}\s+(.+)$', replace_h2, content, flags=re.MULTILINE)
    content = re.sub(r'<h[1-6][^>]*>(.*?)</h[1-6]>', replace_h2, content, flags=re.IGNORECASE)
    return content


def format_paragraphs(content: str) -> str:
    """
    Wraps text sections between headings in <p>...</p> tags.
    """
    if not content:
        return ""

    h2_split = re.split(f'({H2_RE})', content, flags=re.IGNORECASE)
    formatted_parts = []

    for section in h2_split:
        if section.lower().startswith('<h2'):
            formatted_parts.append(section)
        else:
            raw_paras = [p.strip() for p in section.split("\n\n") if p.strip()]
            for p in raw_paras:
                if p.startswith(('<p', '[', '<div', '<ul', '<ol', '<blockquote')):
                    formatted_parts.append(p)
                elif re.match(r'^([-*]|\d+\.)\s+', p):
                    # Markdown list -> HTML list
                    items = [re.sub(r'^([-*]|\d+\.)\s+', '', line).strip() for line in p.split("\n") if line.strip()]
                    tag = "ol" if re.match(r'^\d+\.', p) else "ul"
                    formatted_parts.append(f"<{tag}>" + "".join(f"<li>{i}</li>" for i in items) + f"</{tag}>")
                else:
                    cleaned_p = re.sub(r'\s*\n\s*', ' ', p)
                    formatted_parts.append(f"<p>{cleaned_p}</p>")

    return "\n\n".join(formatted_parts)


def distribute_shortcodes_evenly(content: str, shortcodes: list = None) -> str:
    """
    Evenly distributes shortcodes throughout the article.
    Does nothing when the site has no shortcodes configured.
    """
    if shortcodes is None:
        shortcodes = list(SHORTCODES_LIST)

    if not content or not shortcodes:
        return content

    raw_blocks = [b.strip() for b in content.split("\n\n") if b.strip()]
    blocks = [b for b in raw_blocks if not any(sc in b for sc in shortcodes)]

    total_blocks = len(blocks)
    num_shortcodes = len(shortcodes)

    if total_blocks <= num_shortcodes:
        interleaved = []
        for i, block in enumerate(blocks):
            interleaved.append(block)
            if i < num_shortcodes:
                interleaved.append(shortcodes[i])
        if num_shortcodes > len(blocks):
            interleaved.extend(shortcodes[len(blocks):])
        return "\n\n".join(interleaved)

    step = max(1.0, (total_blocks + 1) / (num_shortcodes + 1))
    target_indices = [min(max(1, int(round(step * (i + 1)))), total_blocks) for i in range(num_shortcodes)]

    result_blocks = []
    sc_idx = 0
    for block_num, block in enumerate(blocks, start=1):
        result_blocks.append(block)
        while sc_idx < num_shortcodes and target_indices[sc_idx] == block_num:
            result_blocks.append(shortcodes[sc_idx])
            sc_idx += 1

    while sc_idx < num_shortcodes:
        result_blocks.insert(-1, shortcodes[sc_idx]) if len(result_blocks) > 1 else result_blocks.append(shortcodes[sc_idx])
        sc_idx += 1

    return "\n\n".join(result_blocks)


def bold_keywords(content: str, max_bold_count: int = 8) -> str:
    """
    Bolds the first plain-text occurrence of a random selection of keywords,
    skipping text inside tags, links and headings.
    """
    if not content:
        return ""

    bolded_count = 0
    available_keywords = list(KEYWORDS_TO_BOLD)
    random.shuffle(available_keywords)

    for kw in available_keywords:
        if bolded_count >= max_bold_count:
            break

        tag = random.choice(["b", "strong"])
        pattern = re.compile(
            r'\b(' + re.escape(kw) + r')\b(?![^<]*>|[^<]*</a>|[^<]*</h2>|[^<]*</b>|[^<]*</strong>)',
            re.IGNORECASE,
        )
        content, count = pattern.subn(lambda m, t=tag: f'<{t}>{m.group(0)}</{t}>', content, count=1)
        if count > 0:
            bolded_count += 1

    return content


def inject_internal_links(content: str, target_count: int = None) -> str:
    """
    Shuffles the internal links and links the first matching keyword for 3-4 of them.
    If none match, appends the fallback sentence.
    """
    if not content:
        return content

    if target_count is None:
        target_count = random.choice([3, 4])

    shuffled_links = list(get_internal_links())
    random.shuffle(shuffled_links)

    links_injected = 0
    tokens = re.split(
        f'({H2_RE}|<a\\s+[^>]*>.*?</a>|<(?:b|strong)>.*?</(?:b|strong)>|<[^>]+>)',
        content,
        flags=re.IGNORECASE | re.DOTALL,
    )

    for link_data in shuffled_links:
        if links_injected >= target_count:
            break

        matched = False
        for kw in link_data["keywords"]:
            if matched:
                break
            pattern = re.compile(r'\b(' + re.escape(kw) + r')\b', re.IGNORECASE)
            for idx in range(len(tokens)):
                if tokens[idx].startswith('<'):
                    continue
                if pattern.search(tokens[idx]):
                    # Keep the article's own wording as the anchor text
                    href = re.search(r'href="([^"]+)"', link_data["html"]).group(1)
                    tokens[idx] = pattern.sub(lambda m: f'<a href="{href}">{m.group(0)}</a>', tokens[idx], count=1)
                    links_injected += 1
                    matched = True
                    break

    result = "".join(tokens)

    if links_injected == 0:
        result = result.rstrip() + f"\n\n{FALLBACK_LINK_SENTENCE}"

    return result


def extract_yoast_description(content: str) -> str:
    """
    Builds the Yoast meta description from the last two sentences of the first
    paragraph plus the site's suffix, trimmed to ~160 characters.
    """
    suffix = cfg.META_DESC_SUFFIX
    max_len = cfg.META_DESC_MAX_CHARS

    clean_paragraphs = []
    for match in re.finditer(r'<p>(.*?)</p>', content or "", flags=re.DOTALL | re.IGNORECASE):
        para_text = re.sub(r'<[^>]+>', '', match.group(1)).strip()
        if para_text and not para_text.startswith('[') and len(para_text) > 40:
            clean_paragraphs.append(para_text)

    first_para = clean_paragraphs[0] if clean_paragraphs else ""
    sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', first_para) if s.strip()]

    # Use as many trailing sentences (max 2) as fit together with the suffix
    for n in (2, 1):
        if len(sentences) >= n:
            candidate = f"{' '.join(sentences[-n:])} {suffix}".strip()
            if len(candidate) <= max_len:
                return candidate

    base = sentences[0] if sentences else cfg.META_DESC_FALLBACK
    room = max_len - len(suffix) - 1
    if len(base) > room:
        base = base[:room].rsplit(' ', 1)[0].rstrip(',;:') + "..."
    return f"{base} {suffix}".strip()


def process_and_format_article(content: str) -> str:
    """
    1. Removes em dashes.
    2. Strips markdown bold/italic asterisks.
    3. Converts headings to question-style H2s.
    4. Wraps paragraphs and lists in HTML.
    5. Bolds a few keywords.
    6. Injects 3-4 internal links (with fallback).
    7. Distributes shortcodes (if any are configured).
    """
    if not content:
        return ""

    content = content.replace("—", "-")
    content = re.sub(r'\*\*(.*?)\*\*', r'\1', content)
    content = re.sub(r'(?<!\w)\*(?!\s)(.*?)(?<!\s)\*(?!\w)', r'\1', content)

    content = format_h2_tags(content)
    content = format_paragraphs(content)
    content = bold_keywords(content)
    content = inject_internal_links(content)
    content = distribute_shortcodes_evenly(content)

    return content


# Aliases for backward compatibility
clean_and_format_text = process_and_format_article
inject_shortcodes = distribute_shortcodes_evenly
