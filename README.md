# 🩺 health.am – Article Publisher & News Autopilot

Writes 1,200+ word health articles with OpenAI and publishes them on **https://www.health.am**
(Next.js + Payload CMS) with a featured image, key points, internal links and a meta description.

Copied from `headachecare-publisher`; that project is unchanged.

## What it does

| | |
|---|---|
| **Streamlit app** (`app.py`) | Type a title, pick a health center, click publish. Or publish a list of titles from a Google Sheet. |
| **News autopilot** (`autopublish.py`, GitHub Actions) | Twice a day (9am and 2pm California time) picks a fresh health headline from Google News, chooses the health center, writes an explainer and publishes it as a News article. |
| **Command line** (`main.py`) | `TOPIC=heart python main.py "Article title"` |

Every article gets:
- question-based H2 headings: the site turns them into the **"On this page"** menu and the **FAQPage schema** (no separate FAQ block, so nothing is repeated);
- 4–5 **key points** (the box at the top of the article);
- a featured image (free CC0 stock photo with the title on it);
- 3–4 links from the list in the health.am admin (**Site settings › Article links**: address + keywords; the built-in list in `site_config.py` is only a fallback);
- a meta description (SEO tab) and excerpt;
- Medical review status **"Not reviewed"** (until a person reviews it);
- for news articles: the news report as the article's **source** (shown under the article).

The site already shows a medical disclaimer under every article, so none is added to the text.

## How it publishes

`payload_publisher.py` signs in to Payload's API (`https://www.health.am/cms-api`) as an admin user,
uploads the image to the media library, converts the HTML to Payload's rich-text format (Lexical)
and creates the article. Saving refreshes the site's cache, so the article is live at once:
`https://www.health.am/<health-center>/<slug>`.

Autopilot articles are marked in **Legacy › Source** (`autopilot-news`, or `autopilot` for app posts),
which is how the autopilot counts its posts per day and avoids duplicates.

## Setup

1. **Admin user for the publisher.** In https://www.health.am/admin › Users › Create new, add a user
   only for the publisher (e.g. `autopilot@…`) with a long random password.
2. **GitHub repository** `healtham-publisher` (private), and push this folder to it.
3. **Secrets** (GitHub › Settings › Secrets and variables › Actions, and Streamlit › App › Settings › Secrets):
   - `OPENAI_API_KEY` (and optionally `OPENAI_MODEL`)
   - `HEALTHAM_EMAIL`, `HEALTHAM_PASSWORD` (the user from step 1)
   - Streamlit only: `APP_PASSWORD` to protect the app
   Or put them all in one GitHub secret named `AUTOMATION` (lines like `KEY = "value"`).
4. **Streamlit Cloud:** new app from the repository, main file `app.py`.
5. **Test:** GitHub › Actions › "health.am daily news autopilot" › Run workflow with *dry run* ticked
   (picks a headline only), then once without it.

## Settings

Everything site-specific is in `site_config.py`: health centers, prompts, internal links, image colors,
the publish hours, the news search and the volume (`PUBLISH_HOURS`: one slot = one article a day).
