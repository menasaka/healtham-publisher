"""
Site-specific settings for health.am (Armenian Medical Network).

Everything that ties this publisher to one website lives in this file.
Copied from headachecare-publisher; health.am runs Next.js + Payload CMS on its own server,
so articles are published through Payload's API (payload_publisher.py).
"""

SITE_NAME = "health.am"
SITE_DOMAIN = "health.am"
SITE_URL = "https://www.health.am"
PAGE_ICON = "🩺"

# OpenAI model used for articles (override with the OPENAI_MODEL secret)
DEFAULT_OPENAI_MODEL = "gpt-4o"

# ------------------------------------------------------------------------------
# Health centers (Payload "topics"). Every article belongs to exactly one, which also sets its
# address: https://www.health.am/<topic>/<slug>. Keys are the topic slugs on the site.
# ------------------------------------------------------------------------------
TOPICS = {
    "cancer": "Cancer",
    "heart": "Heart & Blood Vessels",
    "brain": "Brain & Nerves",
    "mental-health": "Mental Health",
    "diabetes": "Diabetes & Hormones",
    "nutrition": "Weight & Nutrition",
    "womens-health": "Women's Health",
    "pregnancy": "Pregnancy & Fertility",
    "childrens-health": "Children's Health",
    "sexual-health": "Sexual Health",
    "mens-health": "Men's Health",
    "infections": "Infections, HIV & STIs",
    "lungs-allergies": "Lungs, Asthma & Allergies",
    "digestive": "Digestive Health",
    "bones-joints": "Bones, Joints & Pain",
    "skin": "Skin, Hair & Beauty",
    "eyes-ears-teeth": "Eyes, Ears & Teeth",
    "addiction": "Addiction",
    "sleep": "Sleep",
    "healthy-aging": "Healthy Aging",
    "public-health": "Public Health",
    "medicines": "Medicines & Treatments",
}
DEFAULT_TOPIC = "public-health"

# Kept for the shared code (app.py picker): on health.am the "categories" are the health centers.
CATEGORY_MAP = {title: slug for slug, title in TOPICS.items()}
DEFAULT_CATEGORIES = [TOPICS["heart"]]

# Content type of articles written from the app ("guide") and by the news autopilot ("news").
MANUAL_CONTENT_TYPE = "guide"
NEWS_CONTENT_TYPE = "news"
# Shown in the article's "Medical review" tab. AI-written articles stay "unreviewed" until a
# person actually reviews them.
REVIEW_STATUS = "unreviewed"
# Stored in the article's Legacy > Source field, so the autopilot recognizes its own posts.
AUTOPILOT_SOURCE = "autopilot"
AUTOPILOT_NEWS_SOURCE = "autopilot-news"

# ------------------------------------------------------------------------------
# Writing rules
# ------------------------------------------------------------------------------
SYSTEM_PROMPT = (
    "You write consumer health articles for health.am (Armenian Medical Network), an independent "
    "health information site in English for adults. "
    "Tone: Calm, warm, plain-English, active voice, short simple sentences. Write like an experienced "
    "health writer explaining things to a friend, not like a textbook. "
    "Do NOT use em dashes, AI-style labels, or generic intros such as 'In today's world'. "
    "Length: ~1,200 words. Structure: Question-based H2 headings. "
    "Medical accuracy rules: Only state well-established facts that match current mainstream guidance "
    "(for example the WHO, CDC, NIH, NHS, FDA and major academic medical centers and specialty societies). "
    "Never invent statistics, studies, quotes, doctors, or patient stories. "
    "If you mention a number, use widely accepted figures only and keep them general. "
    "Never give personal dosing instructions; say to follow the label or ask a doctor or pharmacist. "
    "Never claim a product or treatment cures a disease. "
    "health.am is not a clinic. Do not invite readers to book appointments with health.am; "
    "encourage them to talk with their own doctor. "
    "CRITICAL LENGTH RULE: You MUST write 3 to 4 detailed paragraphs under EVERY SINGLE H2 to ensure "
    "the article reaches 1,200+ words. No brief summaries."
)

ARTICLE_PROMPT_TEMPLATE = """
Write an in-depth, trustworthy health article for health.am about: "{topic}".

Strict Article Requirements:
1. Open with 1 to 2 short paragraphs (no heading) that say what the article covers.
2. Every major section must start with a question-based H2 heading ending in a question mark (e.g., '## What Causes High Blood Pressure?').
3. Include 6 to 8 question-based H2 sections. The site turns these questions and the text under them into its FAQ markup and its "On this page" menu, so make each heading a real question a reader would ask, and answer it directly in the first sentences under it.
4. Under EVERY SINGLE H2 heading, write 3 to 4 well-developed paragraphs.
5. One H2 section must explain when to see a doctor, including warning signs that need urgent care for this topic.
6. Keep individual sentences short, natural, and clear. Avoid filler phrases, em dashes (—), and artificial AI introductions.
7. Do not add a separate FAQ section, a conclusion heading, a sources list, or a disclaimer (the site adds a disclaimer).
8. Total word count must be 1,200+ words.
"""

# Short "Key points" box shown at the top of each article.
KEY_POINTS_PROMPT = """
Below is a health article titled "{title}". Write 4 to 5 key points that summarize it for a reader.

Rules: each key point is ONE plain-English sentence of 12 to 25 words, taken from what the article says.
No new facts, no numbers that are not in the article, no em dashes, no advice to buy anything.

Article:
{text}

Return ONLY JSON: {{"key_points": ["...", "..."]}}
"""

# No separate FAQ on health.am: the question H2s already give the site its FAQPage schema, and a
# second FAQ block would repeat the article.
GENERATE_FAQS = False
FAQ_SYSTEM_PROMPT = "You are a careful health educator. You always reply with valid JSON."
FAQ_PROMPT_TEMPLATE = """
Generate 8 frequently asked questions and answers for an article titled: "{topic}".
Each answer is exactly 3 plain-English sentences. Never invent statistics. Return ONLY JSON:
{{"faqs": [{{"question": "...", "answer": "..."}}]}}
"""

# Sample topics for the quick-select buttons in the app
SAMPLE_TOPICS = [
    "High Blood Pressure: Early Signs, Causes, and How to Lower It",
    "Type 2 Diabetes: How Diet and Exercise Help Control Blood Sugar",
    "How to Tell the Difference Between a Cold, the Flu, and COVID-19",
    "Sleep and Heart Health: Why Quality Sleep Protects Your Heart",
]

# ------------------------------------------------------------------------------
# Formatting
# ------------------------------------------------------------------------------
H2_OPEN_TAG = "<h2>"
FAQ_HEADING = "Frequently Asked Questions"
SHORTCODES_LIST = []

KEYWORDS_TO_BOLD = [
    "blood pressure",
    "cholesterol",
    "blood sugar",
    "heart disease",
    "stroke",
    "diabetes",
    "obesity",
    "depression",
    "anxiety",
    "vaccination",
    "screening",
    "physical activity",
    "healthy diet",
    "prevention",
    "side effects",
]

# Internal links to health.am health centers (all returned HTTP 200 on 2026-11-10). Relative to
# the site, so they always point at www.health.am.
INTERNAL_LINKS = [
    {"keywords": ["heart disease", "blood pressure", "hypertension", "cholesterol", "heart attack"],
     "html": '<a href="/heart">heart health</a>'},
    {"keywords": ["diabetes", "blood sugar", "insulin"],
     "html": '<a href="/diabetes">diabetes</a>'},
    {"keywords": ["cancer", "tumor", "chemotherapy"],
     "html": '<a href="/cancer">cancer</a>'},
    {"keywords": ["depression", "anxiety", "mental health", "stress"],
     "html": '<a href="/mental-health">mental health</a>'},
    {"keywords": ["stroke", "dementia", "migraine", "headache", "Alzheimer"],
     "html": '<a href="/brain">brain and nerve health</a>'},
    {"keywords": ["obesity", "weight loss", "healthy diet", "nutrition", "overweight"],
     "html": '<a href="/nutrition">weight and nutrition</a>'},
    {"keywords": ["insomnia", "sleep apnea", "sleep"],
     "html": '<a href="/sleep">sleep</a>'},
    {"keywords": ["asthma", "allergies", "allergy", "COPD"],
     "html": '<a href="/lungs-allergies">lungs and allergies</a>'},
    {"keywords": ["infection", "influenza", "flu", "HIV", "antibiotics"],
     "html": '<a href="/infections">infections</a>'},
    {"keywords": ["vaccination", "vaccines", "vaccine", "public health"],
     "html": '<a href="/public-health">public health</a>'},
    {"keywords": ["arthritis", "back pain", "joint pain", "osteoporosis"],
     "html": '<a href="/bones-joints">bones and joints</a>'},
    {"keywords": ["liver", "kidney", "digestion", "bowel"],
     "html": '<a href="/digestive">digestive health</a>'},
    {"keywords": ["smoking", "alcohol", "addiction", "nicotine"],
     "html": '<a href="/addiction">addiction</a>'},
    {"keywords": ["pregnancy", "pregnant", "fertility"],
     "html": '<a href="/pregnancy">pregnancy and fertility</a>'},
    {"keywords": ["children", "teenagers"],
     "html": '<a href="/childrens-health">children\'s health</a>'},
    {"keywords": ["medication", "medicines", "side effects"],
     "html": '<a href="/medicines">medicines and treatments</a>'},
    {"keywords": ["symptoms", "diagnosis"],
     "html": '<a href="/conditions-a-z">conditions A to Z</a>'},
]

FALLBACK_LINK_SENTENCE = (
    '<p>Want to learn more? Browse our <a href="/conditions-a-z">conditions A to Z</a> '
    'and the latest <a href="/public-health">public health</a> news.</p>'
)

# health.am article pages already show a medical disclaimer under every article.
MEDICAL_DISCLAIMER_HTML = ""

# ------------------------------------------------------------------------------
# Meta description (SEO tab)
# ------------------------------------------------------------------------------
META_DESC_SUFFIX = ""
META_DESC_FALLBACK = "Clear, trustworthy health information from health.am."
META_DESC_MAX_CHARS = 155

# ------------------------------------------------------------------------------
# Images
# ------------------------------------------------------------------------------
IMAGE_COUNT = 1
IMAGE_SIZE = (1200, 800)
TITLE_CARD_COLORS = ((13, 110, 99), (8, 70, 64))  # health.am brand teal

USE_OPEN_PHOTOS = True
OPENVERSE_API = "https://api.openverse.org/v1/images/"
OPENVERSE_SOURCES = ["stocksnap"]
OPENVERSE_FALLBACK_SOURCES = ["stocksnap", "flickr", "wikimedia"]
OPENVERSE_LICENSE = "cc0,pdm"
PHOTO_OVERLAY_ALPHA = 30
TITLE_BAR_RATIO = 0.20
TITLE_BAR_ALPHA = 150
TITLE_MAX_FONT = 44
SHOW_DOMAIN_ON_IMAGE = False

PHOTO_QUERY_PROMPT = """
Suggest stock photo search phrases for a featured image for a health article titled: "{topic}".

Rules:
- 6 phrases, best first. Each is 1 to 3 plain visual words that a free stock photo site would tag
  (for example: "doctor patient", "blood pressure", "healthy food", "running", "pills medicine",
  "woman sleeping", "laboratory", "stethoscope", "family", "pharmacy").
- Describe things a camera can photograph. No medical jargon, no brand names, no drug names, no text.
- Mix specific phrases with broader fallbacks.

Return ONLY JSON: {{"queries": ["...", "..."]}}
"""
DEFAULT_PHOTO_QUERIES = ["doctor patient", "stethoscope", "healthy food", "pills medicine", "laboratory", "running"]

PHOTO_TITLE_BLOCKLIST = [
    "quote", "typography", "text", "logo", "sign", "advert", "poster", "cure", "dog", "cat",
    "chart", "graph", "map", "diagram", "screenshot", "etching", "engraving", "illustration",
]

# ------------------------------------------------------------------------------
# Daily news autopilot (autopublish.py, run by GitHub Actions)
# ------------------------------------------------------------------------------
TIMEZONE = "America/Los_Angeles"
PUBLISH_HOURS = [9, 14]          # local times: 9am = 1st headline, 2pm = 2nd headline
LAST_CATCH_UP_HOUR = 17          # a missed slot is made up by the hourly runs until 5:59pm
# Broad health news; OpenAI keeps the medical stories and picks the health center for each.
NEWS_QUERY = "health study OR researchers OR FDA OR CDC OR disease OR medical"
NEWS_WINDOW = "1d"
NEWS_FALLBACK_WINDOW = "3d"
NEWS_SOURCE_BLOCKLIST = ["YouTube", "TikTok", "Facebook", "Instagram", "Reddit"]
# Keyword fallback (when OpenAI cannot judge headlines)
NEWS_KEYWORD_RE = r"\b(study|researchers|FDA|CDC|disease|cancer|diabetes|heart|vaccine|patients?|treatment)\b"

NEWS_PICK_PROMPT = """
Below are recent news headlines found by searching Google News for health and medical news.

{listing}

Keep ONLY headlines that are genuinely about human health or medicine: research, treatments, drugs,
diseases, symptoms, prevention, public health, or patient care. REJECT politics, business and stock
news, celebrity gossip, product promotions, miracle-cure claims, crime, and non-English headlines.

For each kept headline:
- write an original, accurate, SEO-friendly article title for health.am (55-75 characters, plain English,
  no clickbait, no em dashes, do not copy the headline word for word, do not promise cures);
- choose the best health center for it from these slugs: {topics}

Return ONLY JSON: {{"picks": [{{"index": <number>, "title": "...", "topic": "<slug>"}}]}}
Return an empty list if none qualify.
"""

NEWS_ARTICLE_EXTRA = """
News context: this article is prompted by a recent news report.
- Headline: "{headline}"
- Published by: {source}

How to use it:
- In the opening paragraphs, briefly say what the news report covers, using ONLY what the headline states.
  You have not read the report, so do NOT invent study details, numbers, names, dates, quotes, or results.
  Use cautious wording such as "a recent report from {source} highlights..." and "early research suggests".
- Then write a helpful, accurate explainer on the wider topic: background, what is already well
  established, what it may mean for patients, and practical next steps.
- Do not include a link or a sources list (the news report is added as the article's source).
"""

# ------------------------------------------------------------------------------
# Publishing (Payload CMS on www.health.am)
# ------------------------------------------------------------------------------
# Payload's REST API (served at /cms-api). The publisher signs in as an admin user
# (HEALTHAM_EMAIL / HEALTHAM_PASSWORD secrets), ideally one created only for the autopilot.
PAYLOAD_API_URL = "https://www.health.am/cms-api"
PAYLOAD_ADMIN_URL = "https://www.health.am/admin"
