import os
import random
import re
import textwrap
import requests
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont, ImageOps
from dotenv import load_dotenv

import site_config as cfg

load_dotenv()

FONT_URL = "https://raw.githubusercontent.com/JulietaUla/Montserrat/master/fonts/ttf/Montserrat-Black.ttf"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOCAL_FONT_PATH = os.path.join(BASE_DIR, "Montserrat-Black.ttf")
IMAGES_DIR = os.path.join(BASE_DIR, "images")


def ensure_font_exists():
    if os.path.exists(LOCAL_FONT_PATH):
        return LOCAL_FONT_PATH
    try:
        response = requests.get(FONT_URL, timeout=10)
        if response.status_code == 200:
            with open(LOCAL_FONT_PATH, "wb") as f:
                f.write(response.content)
            return LOCAL_FONT_PATH
    except Exception as e:
        print(f"Notice: Could not download font ({e}). Using system fallback.")
    return None


def get_font(size=36):
    font_file = ensure_font_exists()
    for candidate in [font_file, "arial.ttf", "/Library/Fonts/Arial.ttf", "DejaVuSans-Bold.ttf"]:
        if candidate:
            try:
                return ImageFont.truetype(candidate, size)
            except Exception:
                continue
    return ImageFont.load_default()


def get_available_images(images_dir: str = IMAGES_DIR) -> list:
    if not os.path.exists(images_dir):
        return []
    return [
        os.path.join(images_dir, f)
        for f in os.listdir(images_dir)
        if f.lower().endswith(('.jpg', '.jpeg', '.png')) and not f.startswith('.')
    ]


def _slug(title: str, max_len: int = 60) -> str:
    return re.sub(r'[^a-zA-Z0-9]+', '-', title.lower()).strip('-')[:max_len].strip('-') or "post-image"


def render_title_on_top_bar(draw: ImageDraw.ImageDraw, title: str, width: int, bar_height: int,
                            font_path: str, max_font: int = None):
    """
    Renders the title centered inside the top bar, picking the largest font size
    (up to max_font) and a 1-3 line wrap that fits.
    """
    clean_title = title.strip()
    candidate_wraps = [
        [clean_title],
        textwrap.wrap(clean_title, width=max(10, int(len(clean_title) * 0.6))),
        textwrap.wrap(clean_title, width=max(10, int(len(clean_title) * 0.45))),
    ]

    best_font, best_lines, best_size = None, [clean_title], 14
    top_size = max(18, int(bar_height * 0.48))
    if max_font:
        top_size = min(top_size, max_font)
    for size in range(top_size, 12, -2):
        try:
            font = ImageFont.truetype(font_path, size)
        except Exception:
            break
        for lines in candidate_wraps:
            line_height = int(size * 1.25)
            max_w = max(draw.textlength(l, font=font) for l in lines)
            if max_w <= width * 0.92 and len(lines) * line_height <= bar_height * 0.85:
                best_font, best_lines, best_size = font, lines, size
                break
        if best_font:
            break

    if not best_font:
        best_font = get_font(18)

    line_h = int(best_size * 1.25)
    y = max(4, (bar_height - len(best_lines) * line_h) // 2)
    for line in best_lines:
        lx = (width - draw.textlength(line, font=best_font)) // 2
        draw.text((lx + 1, y + 1), line, fill=(0, 0, 0, 180), font=best_font)
        draw.text((lx, y), line, fill=(255, 255, 255, 255), font=best_font)
        y += line_h


def _photo_with_title_bar(photo, title: str, font_path: str) -> Image.Image:
    """
    Photo (PIL image or file path) cropped to IMAGE_SIZE with a light navy tint,
    and the title in white inside a dark strip across the top TITLE_BAR_RATIO of the image.
    """
    if isinstance(photo, str):
        with Image.open(photo) as raw:
            photo = raw.copy()
    width, height = cfg.IMAGE_SIZE
    photo = ImageOps.exif_transpose(photo).convert("RGB")
    base = ImageOps.fit(photo, (width, height), method=Image.LANCZOS, centering=(0.5, 0.35)).convert("RGBA")

    (r1, g1, b1), _ = cfg.TITLE_CARD_COLORS
    if cfg.PHOTO_OVERLAY_ALPHA:
        base = Image.alpha_composite(base, Image.new("RGBA", (width, height), (r1, g1, b1, cfg.PHOTO_OVERLAY_ALPHA)))

    bar_height = max(1, int(height * cfg.TITLE_BAR_RATIO))
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    draw.rectangle([(0, 0), (width, bar_height)], fill=(0, 0, 0, cfg.TITLE_BAR_ALPHA))
    render_title_on_top_bar(draw, title, width, bar_height, font_path, max_font=cfg.TITLE_MAX_FONT)
    return Image.alpha_composite(base, overlay).convert("RGB")


def _gradient_background() -> Image.Image:
    """Diagonal navy-to-teal gradient at IMAGE_SIZE."""
    width, height = cfg.IMAGE_SIZE
    (r1, g1, b1), (r2, g2, b2) = cfg.TITLE_CARD_COLORS
    img = Image.new("RGB", (width, height))
    px = img.load()
    for y in range(height):
        for x in range(0, width, 2):
            t = (x / width * 0.6 + y / height * 0.4)
            c = (int(r1 + (r2 - r1) * t), int(g1 + (g2 - g1) * t), int(b1 + (b2 - b1) * t))
            px[x, y] = c
            if x + 1 < width:
                px[x + 1, y] = c
    return img


def _photo_background(photo: Image.Image) -> Image.Image:
    """
    Crops the photo to fill IMAGE_SIZE and tints it with the brand navy so the
    white title stays readable on any photo.
    """
    width, height = cfg.IMAGE_SIZE
    photo = ImageOps.exif_transpose(photo).convert("RGB")
    photo = ImageOps.fit(photo, (width, height), method=Image.LANCZOS, centering=(0.5, 0.4))
    (r1, g1, b1), _ = cfg.TITLE_CARD_COLORS
    tint = Image.new("RGBA", (width, height), (r1, g1, b1, cfg.PHOTO_OVERLAY_ALPHA))
    # Slightly darker band behind the text area
    band = Image.new("L", (width, height), 0)
    bdraw = ImageDraw.Draw(band)
    for y in range(height):
        d = abs(y - height * 0.46) / (height * 0.5)
        bdraw.line([(0, y), (width, y)], fill=int(max(0, 1 - d) * 70))
    dark = Image.new("RGBA", (width, height), (0, 0, 0, 255))
    dark.putalpha(band)
    out = Image.alpha_composite(photo.convert("RGBA"), tint)
    return Image.alpha_composite(out, dark).convert("RGB")


def _title_card(title: str, font_path: str, variant: int = 0, background: Image.Image = None) -> Image.Image:
    """
    Featured image: centered title and the site domain, drawn on either
    a topic photo (background) or the branded navy-to-teal gradient.
    """
    width, height = cfg.IMAGE_SIZE
    img = background if background is not None else _gradient_background()

    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    if background is None:
        rng = random.Random(f"{title}-{variant}")
        for _ in range(4):
            r = rng.randint(int(height * 0.25), int(height * 0.6))
            cx, cy = rng.randint(0, width), rng.randint(0, height)
            draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(255, 255, 255, 14))
    shadow_alpha = 90 if background is None else 170

    # Title: largest size whose wrap fits in the central area
    max_w, max_h = width * 0.84, height * 0.58
    lines, font, line_h = [title], get_font(40), 50
    for size in range(96, 30, -4):
        try:
            f = ImageFont.truetype(font_path, size) if font_path else get_font(size)
        except Exception:
            f = get_font(size)
        chars = max(8, int(max_w / (size * 0.6)))
        wrapped = textwrap.wrap(title, width=chars)
        lh = int(size * 1.2)
        if max(draw.textlength(l, font=f) for l in wrapped) <= max_w and len(wrapped) * lh <= max_h:
            lines, font, line_h = wrapped, f, lh
            break

    y = (height - len(lines) * line_h) // 2 - int(height * 0.04)
    for line in lines:
        lx = (width - draw.textlength(line, font=font)) // 2
        draw.text((lx + 2, y + 2), line, fill=(0, 0, 0, shadow_alpha), font=font)
        draw.text((lx, y), line, fill=(255, 255, 255, 255), font=font)
        y += line_h

    # Accent line + domain (off by default)
    if cfg.SHOW_DOMAIN_ON_IMAGE:
        small = get_font(30)
        domain = cfg.SITE_DOMAIN.upper()
        dw = draw.textlength(domain, font=small)
        dy = height - int(height * 0.12)
        draw.rectangle([(width - dw) // 2, dy - 22, (width + dw) // 2, dy - 18], fill=(255, 255, 255, 160))
        draw.text(((width - dw) // 2, dy), domain, fill=(255, 255, 255, 220), font=small)

    return Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")


# ------------------------------------------------------------------------------
# Open-license topic photos (Openverse)
# ------------------------------------------------------------------------------
OPENVERSE_HEADERS = {"User-Agent": f"{cfg.SITE_DOMAIN}-publisher/1.0"}

# Credit/source info for each generated file, read by wp_publisher for the media description
IMAGE_CREDITS = {}
_USED_PHOTO_IDS = set()  # avoid repeating a photo within one app session / batch


def search_open_photos(query: str, sources: list) -> list:
    """Searches Openverse for wide CC0/public-domain photos matching the query."""
    params = {
        "q": query,
        "license": cfg.OPENVERSE_LICENSE,
        "source": ",".join(sources),
        "category": "photograph",
        "aspect_ratio": "wide",
        "mature": "false",
        "page_size": 20,
    }
    try:
        res = requests.get(cfg.OPENVERSE_API, params=params, headers=OPENVERSE_HEADERS, timeout=15)
        if res.status_code != 200:
            print(f"Notice: Openverse returned {res.status_code} for '{query}'")
            return []
        results = []
        for r in res.json().get("results", []):
            title_l = (r.get("title") or "").lower()
            if any(w in title_l for w in cfg.PHOTO_TITLE_BLOCKLIST):
                continue
            if (r.get("width") or 0) < cfg.IMAGE_SIZE[0] or r.get("id") in _USED_PHOTO_IDS:
                continue
            results.append(r)
        return results
    except Exception as e:
        print(f"Notice: Openverse search failed for '{query}': {e}")
        return []


def _download_photo(url: str):
    """Downloads an image (max 25 MB) and returns a PIL image, or None."""
    try:
        res = requests.get(url, headers=OPENVERSE_HEADERS, timeout=30, stream=True)
        if res.status_code != 200:
            return None
        data = BytesIO()
        for chunk in res.iter_content(65536):
            data.write(chunk)
            if data.tell() > 25 * 1024 * 1024:
                return None
        data.seek(0)
        img = Image.open(data)
        img.load()
        return img
    except Exception as e:
        print(f"Notice: photo download failed ({url}): {e}")
        return None


def find_topic_photo(title: str):
    """
    Finds a CC0/public-domain photo related to the title.
    Returns (PIL image, credit dict) or (None, None).
    """
    from generator import generate_photo_queries  # local import: needs OpenAI secrets loaded

    queries = generate_photo_queries(title)
    print(f"[Image Engine] Photo search phrases: {queries}")

    for sources in (cfg.OPENVERSE_SOURCES, cfg.OPENVERSE_FALLBACK_SOURCES):
        for query in queries:
            results = search_open_photos(query, sources)
            if not results:
                continue
            # Pick randomly among the best matches so similar topics get different photos
            for r in random.sample(results[:8], min(3, len(results[:8]))):
                photo = _download_photo(r["url"])
                if photo is None:
                    continue
                _USED_PHOTO_IDS.add(r.get("id"))
                credit = {
                    "query": query,
                    "title": r.get("title") or "",
                    "creator": r.get("creator") or "",
                    "source": r.get("source") or "",
                    "license": (r.get("license") or "").upper(),
                    "landing_url": r.get("foreign_landing_url") or r.get("url"),
                }
                print(f"[Image Engine] Using '{credit['title']}' from {credit['source']} ({credit['license']}) for '{query}'")
                return photo, credit
    return None, None


def create_unique_images(title: str, count: int = None, use_dalle: bool = False, images_dir: str = IMAGES_DIR) -> list:
    """
    Creates the featured image(s) and saves them as temporary JPEGs for upload:
    1. A CC0 / public-domain photo related to the topic (Openverse) with the title on top.
    2. If none is found: a photo from images/ (title bar on top), if that folder has photos.
    3. Otherwise: the branded gradient title card.
    """
    count = count or cfg.IMAGE_COUNT
    font_path = ensure_font_exists()
    local_photos = get_available_images(images_dir)

    generated_paths = []
    for idx in range(1, count + 1):
        try:
            final_img, credit = None, None
            if cfg.USE_OPEN_PHOTOS:
                photo, credit = find_topic_photo(title)
                if photo is not None:
                    final_img = _photo_with_title_bar(photo, title, font_path)
            if final_img is None and local_photos:
                final_img = _photo_with_title_bar(random.choice(local_photos), title, font_path)
                credit = {"source": "local images folder"}
            if final_img is None:
                final_img = _title_card(title, font_path, idx)
                credit = {"source": "branded title card"}

            output_filename = os.path.join(BASE_DIR, f"{_slug(title)}-{idx}.jpg")
            final_img.save(output_filename, "JPEG", quality=88)
            IMAGE_CREDITS[output_filename] = credit or {}
            generated_paths.append(output_filename)
            print(f" -> Generated image {idx}/{count}: {output_filename} ({(credit or {}).get('source')})")
        except Exception as e:
            print(f"⚠️ Error creating image {idx}: {e}")

    return generated_paths


def cleanup_local_images(image_paths: list) -> None:
    for path in image_paths or []:
        try:
            if path and os.path.exists(path):
                os.remove(path)
        except Exception as e:
            print(f"Notice: Could not delete local file {path}: {e}")


# Backward compatibility aliases
create_branded_template_images = create_unique_images
create_branded_images = create_unique_images
