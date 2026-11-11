"""
One entry point for publishing. health.am runs on Payload CMS, so articles go to
payload_publisher (the Headache Care original also had WordPress and Sanity targets).
"""
import site_config as cfg
from image_maker import cleanup_local_images


def publish_target() -> str:
    return "payload"


def topic_from_names(category_name: str = None, category_ids: list = None) -> str:
    """The app's picker gives health center titles (or slugs); returns the first known slug."""
    names = [n.strip() for n in (category_name or "").split(",") if n.strip()] + [str(i) for i in category_ids or []]
    for n in names:
        if n in cfg.TOPICS:
            return n
        if n in cfg.CATEGORY_MAP:
            return cfg.CATEGORY_MAP[n]
    return cfg.DEFAULT_TOPIC


def publish_post(
    title: str,
    content: str,
    image_paths: list = None,
    faq_items: list = None,
    category_name: str = None,
    category_ids: list = None,
    status: str = "publish",
    extra_html: str = "",
    news: dict = None,
    topic: str = None,
    key_points: list = None,
    content_type: str = None,
):
    """
    Publishes one article. faq_items are not used on health.am: the article's question H2s
    give the site its FAQPage schema. Returns the publisher's result dict or None.
    """
    from payload_publisher import publish_payload_post

    try:
        post = publish_payload_post(
            title=title,
            content=content,
            image_paths=image_paths,
            topic=topic or topic_from_names(category_name, category_ids),
            content_type=content_type or (cfg.NEWS_CONTENT_TYPE if news else cfg.MANUAL_CONTENT_TYPE),
            key_points=key_points,
            news=news,
            extra_html=extra_html,
        )
    finally:
        cleanup_local_images(image_paths)
    if post is not None:
        post = dict(post)
        post["targets"] = {"payload": True}
    return post
