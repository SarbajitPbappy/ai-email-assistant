import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import streamlit as st
import json
import sqlite3
from datetime import datetime

# ── Cloud-aware DB URL resolution ──────────────────────────────────────────
def get_database_url() -> str:
    """
    Priority:
    1. st.secrets["DATABASE_URL"]  (Streamlit Cloud)
    2. Environment variable DATABASE_URL  (local .env)
    3. Default local SQLite
    """
    try:
        return st.secrets["DATABASE_URL"]
    except Exception:
        pass
    url = os.environ.get("DATABASE_URL", "")
    if url:
        # Supabase / Heroku give postgres:// but SQLAlchemy 2.x needs postgresql://
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        return url
    return "sqlite:///data/assistant.db"

DATABASE_URL = get_database_url()

# ── SQLAlchemy models (inline so no local imports needed) ──────────────────
from sqlalchemy import (
    create_engine, Column, String, Text, DateTime,
    Float, Boolean, Integer
)
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()

class EmailRecord(Base):
    __tablename__ = 'emails'
    id = Column(String, primary_key=True)
    thread_id = Column(String)
    from_address = Column(String)
    to_address = Column(String)
    subject = Column(String)
    body_text = Column(Text)
    snippet = Column(Text)
    date_received = Column(String)
    category = Column(String)
    importance = Column(String)
    is_job_related = Column(Boolean, default=False)
    needs_reply = Column(Boolean, default=False)
    classification_json = Column(Text)
    is_processed = Column(Boolean, default=False)
    is_replied = Column(Boolean, default=False)
    is_applied = Column(Boolean, default=False)
    fetched_at = Column(DateTime, default=datetime.utcnow)
    processed_at = Column(DateTime)

class JobMatch(Base):
    __tablename__ = 'job_matches'
    id = Column(Integer, primary_key=True, autoincrement=True)
    email_id = Column(String)
    job_title = Column(String)
    company = Column(String)
    match_score = Column(Float)
    recommendation = Column(String)
    match_json = Column(Text)
    cover_letter = Column(Text)
    applied = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class ReplyDraft(Base):
    __tablename__ = 'reply_drafts'
    id = Column(Integer, primary_key=True, autoincrement=True)
    email_id = Column(String)
    subject = Column(String)
    body = Column(Text)
    confidence = Column(Float)
    requires_review = Column(Boolean, default=True)
    is_sent = Column(Boolean, default=False)
    is_approved = Column(Boolean, default=False)
    review_reason = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    sent_at = Column(DateTime)

@st.cache_resource
def get_engine():
    return create_engine(DATABASE_URL)

def get_session():
    engine = get_engine()
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()

# ── Page config ────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="AI Email Assistant",
    page_icon="🤖",
    layout="wide"
)

# ── Password protection ────────────────────────────────────────────────────
DASHBOARD_PASSWORD = (
    st.secrets.get("DASHBOARD_PASSWORD", None)
    or os.environ.get("DASHBOARD_PASSWORD", "sarbajit2026")
)

if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.title("🔐 Login")
    password = st.text_input("Enter password:", type="password")
    if st.button("Login"):
        if password == DASHBOARD_PASSWORD:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Wrong password!")
    st.stop()

# ── Main Dashboard ─────────────────────────────────────────────────────────
st.title("🤖 AI Personal Assistant Dashboard")
st.caption("Profile: Sarbajit Paul Bappy | Read-only cloud view | Backend runs locally")

# ── Sidebar ────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Controls")

    # ℹ️  "Process Emails" runs Ollama locally — not available on cloud
    st.info(
        "⚙️ **Email processing runs on your local machine.**\n\n"
        "Run `python main.py` locally to process new emails. "
        "This dashboard auto-refreshes the data below.",
        icon="🏠"
    )

    if st.button("🔄 Refresh Data", type="primary", use_container_width=True):
        st.cache_resource.clear()
        st.rerun()

    st.divider()
    st.header("📊 Stats")

    try:
        session = get_session()
        total = session.query(EmailRecord).count()
        jobs = session.query(EmailRecord).filter_by(is_job_related=True).count()
        pending = session.query(ReplyDraft).filter_by(is_sent=False).count()
        session.close()
        st.metric("Emails Processed", total)
        st.metric("Job Opportunities", jobs)
        st.metric("Replies Pending", pending)
    except Exception as e:
        st.error(f"DB error: {e}")

    if st.button("🚪 Logout"):
        st.session_state.authenticated = False
        st.rerun()

# ── Tabs ───────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs([
    "💼 Job Matches",
    "✍️ Reply Drafts",
    "🎓 Professor Outreach",
    "📧 All Emails"
])

# TAB 1 ─────────────────────────────────────────────────────────────────────
with tab1:
    st.subheader("💼 Job Matches & Cover Letters")
    try:
        session = get_session()
        matches = session.query(JobMatch).order_by(JobMatch.created_at.desc()).limit(20).all()
        if not matches:
            st.info("No job matches yet. Run `python main.py` on your local machine.")
        else:
            for match in matches:
                score = match.match_score or 0
                emoji = "🟢" if score >= 0.8 else "🟡" if score >= 0.6 else "🔴"
                with st.expander(f"{emoji} {match.job_title} at {match.company} — {score:.0%}"):
                    col1, col2, col3 = st.columns(3)
                    col1.metric("Score", f"{score:.0%}")
                    col2.metric("Recommendation", match.recommendation or "N/A")
                    col3.metric("Applied", "Yes" if match.applied else "No")
                    if match.match_json:
                        try:
                            data = json.loads(match.match_json)
                            st.write("**Matching Skills:**", ", ".join(data.get('matching_skills', [])))
                            st.write("**Missing Skills:**", ", ".join(data.get('missing_skills', [])))
                        except Exception:
                            pass
                    if match.cover_letter:
                        st.text_area("Cover Letter", match.cover_letter, height=200, key=f"cl_{match.id}")
        session.close()
    except Exception as e:
        st.error(f"Error loading job matches: {e}")

# TAB 2 ─────────────────────────────────────────────────────────────────────
with tab2:
    st.subheader("✍️ Reply Drafts")
    st.warning("📌 Sending emails requires Gmail OAuth — run that from your local machine.", icon="🏠")
    try:
        session = get_session()
        drafts = session.query(ReplyDraft).filter_by(is_sent=False).order_by(ReplyDraft.created_at.desc()).all()
        if not drafts:
            st.info("No pending replies.")
        else:
            for draft in drafts:
                with st.expander(f"📧 Re: {(draft.subject or 'No Subject')[:60]}"):
                    st.write(f"**Confidence:** {(draft.confidence or 0):.0%}")
                    st.text_area("Draft body:", draft.body or "", height=200, disabled=True, key=f"d_{draft.id}")
                    st.caption("To send this reply, approve it via Telegram or your local machine.")
        session.close()
    except Exception as e:
        st.error(f"Error loading drafts: {e}")

# TAB 3 ─────────────────────────────────────────────────────────────────────
with tab3:
    st.subheader("🎓 Professor Outreach History")
    try:
        engine = get_engine()
        with engine.connect() as conn:
            from sqlalchemy import text as sql_text
            rows = conn.execute(sql_text(
                "SELECT id, professor_name, university, professor_email, "
                "application_type, alignment_score, recommendation, "
                "subject, body, status, sent_at, created_at "
                "FROM professor_outreach ORDER BY created_at DESC"
            )).fetchall()

        if not rows:
            st.info("No professor outreach yet. Use Telegram: PROF <info>")
        else:
            for row in rows:
                score = row[5] or 0
                emoji = "🟢" if score >= 0.8 else "🟡" if score >= 0.6 else "🔴"
                status_icon = "✅" if row[9] == "sent" else "⏳" if row[9] == "pending" else "❌"
                with st.expander(f"{emoji} {status_icon} {row[1]} at {row[2]} — {row[4]} ({score:.0%})"):
                    col1, col2, col3 = st.columns(3)
                    col1.metric("Alignment", f"{score:.0%}")
                    col2.metric("Type", row[4])
                    col3.metric("Status", row[9])
                    st.write(f"**Email:** {row[3]}")
                    st.write(f"**Subject:** {row[7]}")
                    st.write(f"**Recommendation:** {row[6]}")
                    if row[10]:
                        st.write(f"**Sent at:** {row[10]}")
                    if row[8]:
                        st.text_area("Email Body", row[8][:1500], height=300, disabled=True, key=f"prof_{row[0]}")
    except Exception as e:
        st.info(f"No professor outreach data yet. ({e})")

# TAB 4 ─────────────────────────────────────────────────────────────────────
with tab4:
    st.subheader("📧 All Processed Emails")
    try:
        session = get_session()
        emails = session.query(EmailRecord).order_by(EmailRecord.fetched_at.desc()).limit(50).all()
        icons = {'critical': '🔴', 'high': '🟠', 'medium': '🟡', 'low': '🟢', 'ignore': '⚪'}
        if not emails:
            st.info("No emails processed yet.")
        else:
            for email in emails:
                icon = icons.get(email.importance, '⚪')
                job = "💼" if email.is_job_related else ""
                with st.expander(f"{icon}{job} {email.subject or 'No Subject'}"):
                    col1, col2 = st.columns(2)
                    col1.write(f"**From:** {email.from_address}")
                    col1.write(f"**Category:** {email.category}")
                    col2.write(f"**Importance:** {email.importance}")
                    col2.write(f"**Job:** {'Yes' if email.is_job_related else 'No'}")
                    if email.body_text:
                        st.text_area("Body", email.body_text[:500], disabled=True, key=f"e_{email.id}")
        session.close()
    except Exception as e:
        st.error(f"Error loading emails: {e}")
