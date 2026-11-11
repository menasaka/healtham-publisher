import os
import io
import time
import requests
import streamlit as st
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

# Bridge Streamlit Cloud secrets into environment variables (before other modules read them)
try:
    for k, v in st.secrets.items():
        if isinstance(v, str):
            os.environ[k] = v
except Exception:
    pass

import site_config as cfg
from generator import generate_article_content, generate_key_points
from processor import process_and_format_article
from image_maker import create_unique_images
from publisher import publish_post

st.set_page_config(
    page_title=f"SEO Article Publisher | {cfg.SITE_NAME}",
    page_icon=cfg.PAGE_ICON,
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    .main-header { font-size: 2.2rem; font-weight: 800; color: #0d6e63; margin-bottom: 0.2rem; }
    .sub-header { font-size: 1rem; color: #5e6774; margin-bottom: 1.5rem; }
    .status-badge { display: inline-block; padding: 4px 12px; background-color: #e3f1ee; color: #0d6e63;
                    border-radius: 9999px; font-size: 0.85rem; font-weight: 600; margin-right: 8px; }
    .success-card { background-color: #F0FDF4; border: 1px solid #BBF7D0; border-radius: 8px; padding: 20px; margin: 15px 0; }
</style>
""", unsafe_allow_html=True)


def get_env_status():
    return {
        "has_openai": bool(os.getenv("OPENAI_API_KEY")),
        "has_payload": bool(os.getenv("HEALTHAM_EMAIL") and os.getenv("HEALTHAM_PASSWORD")),
        "user": os.getenv("HEALTHAM_EMAIL", ""),
    }


def topic_picker(label: str, key: str) -> str:
    """One health center per article (it is also part of the address: /<center>/<slug>)."""
    titles = list(cfg.TOPICS.values())
    default = titles.index(cfg.DEFAULT_CATEGORIES[0]) if cfg.DEFAULT_CATEGORIES[0] in titles else 0
    title = st.selectbox(label, options=titles, index=default, key=key)
    return cfg.CATEGORY_MAP[title]


def run_pipeline(title: str, topic: str, report=None):
    def step(msg, pct):
        if report:
            report(msg, pct)

    step("🧠 [1/5] Writing the article with OpenAI...", 15)
    raw_content = generate_article_content(title)

    step(f"⚙️ [2/5] Article drafted ({len(raw_content.split())} words). Formatting and adding internal links...", 40)
    formatted = process_and_format_article(raw_content)

    step("📌 [3/5] Writing the key points...", 55)
    key_points = generate_key_points(title, formatted)

    step("🎨 [4/5] Creating the featured image...", 70)
    images = create_unique_images(title)

    step("🚀 [5/5] Uploading the image and publishing the article...", 90)
    post = publish_post(
        title=title,
        content=formatted,
        image_paths=images,
        topic=topic,
        key_points=key_points,
        content_type=cfg.MANUAL_CONTENT_TYPE,
    )
    return post, raw_content, formatted, key_points


def main():
    # Password gate
    app_password = os.getenv("APP_PASSWORD", "")
    if app_password:
        entered = st.text_input("🔑 Enter Access Password", type="password")
        if not entered:
            st.warning("🔒 Please enter the access password to use this application.")
            st.stop()
        elif entered != app_password:
            st.error("❌ Incorrect password. Access denied.")
            st.stop()

    env = get_env_status()

    with st.sidebar:
        st.header("⚙️ System Status")
        st.info(f"Publishing to: **{cfg.SITE_URL}** (Payload CMS)")
        if env["has_payload"]:
            st.success("health.am admin login: set")
            st.caption(f"Signed in as: **{env['user']}**")
        else:
            st.error("HEALTHAM_EMAIL / HEALTHAM_PASSWORD missing")
        if env["has_openai"]:
            st.success(f"OpenAI API: Connected ({os.getenv('OPENAI_MODEL') or cfg.DEFAULT_OPENAI_MODEL})")
        else:
            st.error("OPENAI_API_KEY missing")

        st.divider()
        st.subheader("🛠️ Publishing Parameters")
        st.markdown("""
        - **Target Word Count:** ~1,200+ words
        - **Headings:** Question-based `H2` (the site turns them into its FAQ schema and "On this page" menu)
        - **Density:** 3–4 paragraphs per H2
        - **Key points:** 4–5, at the top of the article
        - **Internal Links:** 3–4 health.am health centers
        - **SEO:** meta description in the article's SEO tab
        - **Medical review:** marked "Not reviewed"
        - **Featured image:** 1 per article
        """)

    st.markdown(f'<div class="main-header">{cfg.PAGE_ICON} {cfg.SITE_NAME}</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Automated health article writer and publisher for www.health.am</div>', unsafe_allow_html=True)
    st.markdown(
        '<div>'
        '<span class="status-badge">OpenAI</span>'
        '<span class="status-badge">Featured Image Engine</span>'
        '<span class="status-badge">Payload CMS API</span>'
        '<span class="status-badge">FAQ Schema from headings</span>'
        '</div>',
        unsafe_allow_html=True,
    )
    st.write("")

    tab_single, tab_batch = st.tabs(["📝 Single Article", "📊 Google Sheets Batch Queue"])

    with tab_single:
        st.subheader("Generate & Publish One Article")
        st.caption("Quick Select Sample Topics:")
        cols = st.columns(len(cfg.SAMPLE_TOPICS))
        for idx, topic in enumerate(cfg.SAMPLE_TOPICS):
            if cols[idx].button(f"Topic {idx + 1}", key=f"topic_btn_{idx}", help=topic):
                st.session_state["blog_title"] = topic

        title_input = st.text_input(
            "Article Title",
            value=st.session_state.get("blog_title", cfg.SAMPLE_TOPICS[0]),
            placeholder="Enter the exact article title...",
        )
        topic = topic_picker("📁 Health center", "single_topic")

        if st.button("🚀 Generate & Publish Live", type="primary", use_container_width=True):
            if not title_input.strip():
                st.warning("Please enter a valid article title.")
                return

            progress_bar = st.progress(0)
            status_box = st.empty()

            def report(msg, pct):
                status_box.info(msg)
                progress_bar.progress(pct)

            try:
                post_data, raw_content, formatted, key_points = run_pipeline(title_input, topic, report)
                progress_bar.progress(100)

                if not post_data:
                    status_box.error("❌ Failed to publish the article. Check the logs and credentials.")
                    return

                status_box.empty()
                edit_url = post_data["edit_url"]
                preview_url = post_data.get("preview_url", "")
                st.markdown(f"""
                <div class="success-card">
                    <h3 style="color: #15803D; margin-top: 0;">🎉 Article Published LIVE!</h3>
                    <p><strong>Article ID:</strong> {post_data.get("id")} | <strong>Health center:</strong> {cfg.TOPICS.get(post_data.get("topic"), "")}</p>
                    <p><strong>Edit URL:</strong> <a href="{edit_url}" target="_blank">{edit_url}</a></p>
                    <p><strong>Article URL:</strong> <a href="{preview_url}" target="_blank">{preview_url}</a></p>
                </div>
                """, unsafe_allow_html=True)

                c1, c2 = st.columns(2)
                c1.link_button("📝 Open in health.am admin", edit_url, use_container_width=True)
                c2.link_button("🌐 Open Article", preview_url, use_container_width=True)

                st.divider()
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Article Words", len(raw_content.split()))
                m2.metric("Key points", len(key_points))
                m3.metric("Status", "LIVE")
                m4.metric("Featured Image", "✅ Set" if post_data.get("featured_ok") else "❌ Missing")
                if not post_data.get("featured_ok"):
                    st.warning("The featured image was not set. Check the app logs (Manage app → logs) for the error.")

                with st.expander("🔍 SEO details", expanded=True):
                    st.markdown(f"**Title:** `{title_input}`")
                    st.markdown("**Meta Description:**")
                    st.info(post_data.get("yoast_metadesc", ""))
                    st.success("✅ The site builds the FAQPage schema from the article's question headings.")

                with st.expander("📌 Key points"):
                    for k in key_points:
                        st.markdown(f"- {k}")

                with st.expander("📄 Full HTML Body Content"):
                    st.code(formatted, language="html")

            except Exception as ex:
                status_box.error(f"❌ An error occurred during pipeline execution: {ex}")
                st.exception(ex)

    with tab_batch:
        st.subheader("Batch Publish from Google Sheet")
        st.markdown("Titles in column A of a sheet shared as **Anyone with the link can view**. Articles run one after another with a short cooldown.")

        b1, b2 = st.columns([2, 1])
        with b1:
            sheet_id_input = st.text_input("Google Sheet ID", value=os.getenv("GOOGLE_SHEET_ID", ""))
        with b2:
            batch_topic = topic_picker("Health center", "batch_topic")

        if st.button("📥 Load Sheet & Start Batch", type="secondary"):
            if not sheet_id_input.strip():
                st.warning("Enter a Google Sheet ID first.")
                return
            csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id_input.strip()}/export?format=csv"
            try:
                resp = requests.get(csv_url, timeout=15)
                if resp.status_code != 200:
                    st.error(f"Could not load Google Sheet (HTTP {resp.status_code}). Check the sharing setting.")
                    return

                df = pd.read_csv(io.StringIO(resp.text))
                raw_titles = df.iloc[:, 0].dropna().astype(str).str.strip().tolist()
                titles = [t for t in raw_titles if t and t.lower() not in ["title", "titles", "topic", "topics"]]
                st.success(f"Found {len(titles)} titles in queue!")

                batch_progress = st.progress(0)
                batch_box = st.empty()
                for idx, title in enumerate(titles, start=1):
                    batch_box.info(f"Processing ({idx}/{len(titles)}): **{title}**...")
                    try:
                        post, *_ = run_pipeline(title, batch_topic)
                    except Exception as e:
                        post = None
                        st.write(f"⚠️ Error on '{title}': {e}")
                    if post:
                        st.write(f"✅ **[{idx}/{len(titles)}] Published LIVE:** {title} — [View]({post.get('preview_url', '')}) · [Edit]({post.get('edit_url', '')})")
                    else:
                        st.write(f"⚠️ **[{idx}/{len(titles)}] Failed:** {title}")
                    batch_progress.progress(int(idx / len(titles) * 100))
                    if idx < len(titles):
                        time.sleep(5)

                batch_box.success("🏁 All batch titles processed!")
            except Exception as e:
                st.error(f"Error processing sheet: {e}")


if __name__ == "__main__":
    main()
