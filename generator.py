import os
import re
import json
from openai import OpenAI
from dotenv import load_dotenv

import site_config as cfg

load_dotenv()

_client = None
_client_key = None


def _get_client() -> OpenAI:
    # Created lazily so Streamlit secrets are already loaded into the environment, and created again
    # when the key changes (Streamlit keeps this module loaded after its secrets are edited).
    global _client, _client_key
    key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if _client is None or key != _client_key:
        _client = OpenAI(api_key=key)
        _client_key = key
    return _client


def _model() -> str:
    # "or": an empty OPENAI_MODEL (e.g. unset GitHub secret) falls back to the default
    return os.getenv("OPENAI_MODEL") or cfg.DEFAULT_OPENAI_MODEL


def generate_article_content(topic_title: str, news: dict = None) -> str:
    """
    Generates a ~1,200+ word health education article with question-based H2 headings.
    news: optional {"headline", "source"} for articles based on a news report.
    All site-specific rules come from site_config.py.
    """
    user_prompt = cfg.ARTICLE_PROMPT_TEMPLATE.format(topic=topic_title)
    if news:
        user_prompt += cfg.NEWS_ARTICLE_EXTRA.format(headline=news["headline"], source=news.get("source") or "a news outlet")
    response = _get_client().chat.completions.create(
        model=_model(),
        messages=[
            {"role": "system", "content": cfg.SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        max_tokens=4200,
        temperature=0.7,
    )
    return response.choices[0].message.content


def generate_key_points(title: str, article_text: str) -> list:
    """
    4-5 one-sentence key points for the article's "Key points" box, taken from the article text.
    Returns [] if anything goes wrong (the site then derives key points from the body itself).
    """
    try:
        text = re.sub(r"<[^>]+>", " ", article_text or "")
        text = re.sub(r"\s+", " ", text)[:12000]
        response = _get_client().chat.completions.create(
            model=_model(),
            messages=[{"role": "user", "content": cfg.KEY_POINTS_PROMPT.format(title=title, text=text)}],
            response_format={"type": "json_object"},
            max_tokens=600,
            temperature=0.3,
        )
        data = json.loads(response.choices[0].message.content)
        points = [str(p).strip().replace("—", "-") for p in data.get("key_points", []) if str(p).strip()]
        return points[:5]
    except Exception as e:
        print(f"Notice: key points generation failed ({e}); the site will derive them.")
        return []


def generate_faqs(topic_title: str) -> list:
    """
    Generates 12 topic-specific Q&A pairs (3-sentence answers) as JSON.
    Raises if generation fails, rather than publishing FAQs that don't match the article.
    """
    response = _get_client().chat.completions.create(
        model=_model(),
        messages=[
            {"role": "system", "content": cfg.FAQ_SYSTEM_PROMPT},
            {"role": "user", "content": cfg.FAQ_PROMPT_TEMPLATE.format(topic=topic_title)},
        ],
        response_format={"type": "json_object"},
        max_tokens=3000,
        temperature=0.6,
    )

    data = json.loads(response.choices[0].message.content)

    parsed_faqs = []
    for item in data.get("faqs", []):
        clean_q = str(item.get("question", "")).strip()
        clean_a = re.sub(r'\s*\n\s*', ' ', str(item.get("answer", "")).strip())
        clean_a = clean_a.replace("—", "-")
        if clean_q and clean_a:
            parsed_faqs.append({"question": clean_q, "answer": clean_a})

    if not parsed_faqs:
        raise ValueError(f"FAQ generation returned no usable questions for: {topic_title}")

    return parsed_faqs[:12]


def generate_photo_queries(topic_title: str) -> list:
    """
    Asks OpenAI for short, visual stock-photo search phrases for the topic.
    Falls back to generic headache phrases if anything goes wrong.
    """
    try:
        response = _get_client().chat.completions.create(
            model=_model(),
            messages=[{"role": "user", "content": cfg.PHOTO_QUERY_PROMPT.format(topic=topic_title)}],
            response_format={"type": "json_object"},
            max_tokens=200,
            temperature=0.4,
        )
        data = json.loads(response.choices[0].message.content)
        queries = [str(q).strip().lower() for q in data.get("queries", []) if str(q).strip()]
        if queries:
            # Always keep generic fallbacks at the end
            return queries[:6] + [q for q in cfg.DEFAULT_PHOTO_QUERIES if q not in queries]
    except Exception as e:
        print(f"Notice: photo query generation failed ({e}); using defaults.")
    return list(cfg.DEFAULT_PHOTO_QUERIES)


# Backward compatibility alias
generate_faq_items = generate_faqs
