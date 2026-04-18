import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import streamlit as st
import json
import sqlite3
from datetime import datetime
from src.utils.database import Database, EmailRecord, JobMatch, ReplyDraft
from config.settings import settings

st.set_page_config(
    page_title="AI Email Assistant",
    page_icon="🤖",
    layout="wide"
)

# Password protection
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.title("🔐 Login")
    password = st.text_input("Enter password:", type="password")
    if st.button("Login"):
        if password == "sarbajit2026":
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Wrong password!")
    st.stop()

# Main Dashboard
db = Database()

st.title("🤖 AI Personal Assistant Dashboard")
st.caption(f"Profile: {settings.USER_NAME} | Model: Ollama Llama3 (Local & Free)")

# Sidebar
with st.sidebar:
    st.header("⚙️ Controls")
    if st.button("🔄 Process Emails Now", type="primary", use_container_width=True):
        with st.spinner("Processing..."):
            from src.agent.orchestrator import EmailAssistantOrchestrator
            agent = EmailAssistantOrchestrator()
            stats = agent.run(max_emails=10, query="in:inbox")
            st.success(f"Done! {stats['total']} emails processed")
            st.rerun()

    st.divider()
    st.header("📊 Stats")
    stats = db.get_daily_stats()
    st.metric("Emails Processed", stats['total_processed'])
    st.metric("Job Opportunities", stats['job_emails'])
    st.metric("Replies Pending", stats['replies_pending'])

    # Professor stats
    try:
        conn = sqlite3.connect("data/assistant.db")
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM professor_outreach")
        prof_total = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM professor_outreach WHERE status='sent'")
        prof_sent = cursor.fetchone()[0]
        conn.close()
        st.metric("Professors Contacted", prof_sent)
    except:
        pass

    if st.button("🚪 Logout"):
        st.session_state.authenticated = False
        st.rerun()

# Tabs
tab1, tab2, tab3, tab4 = st.tabs([
    "💼 Job Matches",
    "✍️ Reply Drafts",
    "🎓 Professor Outreach",
    "📧 All Emails"
])

# TAB 1: Job Matches
with tab1:
    st.subheader("💼 Job Matches & Cover Letters")
    session = db.Session()
    matches = session.query(JobMatch).order_by(JobMatch.created_at.desc()).limit(20).all()

    if not matches:
        st.info("No job matches yet. Click 'Process Emails Now'.")
    else:
        for match in matches:
            score = match.match_score or 0
            emoji = "🟢" if score >= 0.8 else "🟡" if score >= 0.6 else "🔴"
            with st.expander(f"{emoji} {match.job_title} at {match.company} - {score:.0%}"):
                col1, col2, col3 = st.columns(3)
                col1.metric("Score", f"{score:.0%}")
                col2.metric("Recommendation", match.recommendation or "N/A")
                col3.metric("Applied", "Yes" if match.applied else "No")

                if match.match_json:
                    data = json.loads(match.match_json)
                    st.write("**Matching Skills:**", ", ".join(data.get('matching_skills', [])))
                    st.write("**Missing Skills:**", ", ".join(data.get('missing_skills', [])))

                if match.cover_letter:
                    st.text_area("Cover Letter", match.cover_letter, height=200, key=f"cl_{match.id}")

                if st.button("✅ Mark Applied", key=f"applied_{match.id}"):
                    s = db.Session()
                    m = s.query(JobMatch).filter_by(id=match.id).first()
                    if m:
                        m.applied = True
                        s.commit()
                    s.close()
                    st.rerun()
    session.close()

# TAB 2: Reply Drafts
with tab2:
    st.subheader("✍️ Reply Drafts")
    session = db.Session()
    drafts = session.query(ReplyDraft).filter_by(is_sent=False).order_by(ReplyDraft.created_at.desc()).all()

    if not drafts:
        st.info("No pending replies.")
    else:
        for draft in drafts:
            email = db.get_email(draft.email_id)
            subject = email.get('subject', 'Unknown') if email else 'Unknown'
            from_addr = email.get('from', 'Unknown') if email else 'Unknown'

            with st.expander(f"📧 Re: {subject[:60]}"):
                st.write(f"**To:** {from_addr}")
                st.write(f"**Confidence:** {draft.confidence:.0%}")

                edited = st.text_area("Edit reply:", draft.body, height=200, key=f"d_{draft.id}")

                col1, col2 = st.columns(2)
                if col1.button("📤 Send", key=f"send_{draft.id}", type="primary"):
                    from src.email_reader.gmail_client import GmailClient
                    gmail = GmailClient()
                    if email:
                        success = gmail.send_email(
                            to=email.get('from', ''),
                            subject=draft.subject,
                            body=edited,
                            thread_id=email.get('thread_id', '')
                        )
                        if success:
                            db.mark_reply_sent(draft.email_id)
                            st.success("Sent!")
                            st.rerun()

                if col2.button("🗑️ Discard", key=f"del_{draft.id}"):
                    s = db.Session()
                    d = s.query(ReplyDraft).filter_by(id=draft.id).first()
                    if d:
                        d.is_sent = True
                        s.commit()
                    s.close()
                    st.rerun()
    session.close()

# TAB 3: Professor Outreach
with tab3:
    st.subheader("🎓 Professor Outreach History")

    try:
        conn = sqlite3.connect("data/assistant.db")
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, professor_name, university, professor_email, "
            "application_type, alignment_score, recommendation, "
            "subject, body, status, sent_at, created_at "
            "FROM professor_outreach ORDER BY created_at DESC"
        )
        rows = cursor.fetchall()
        conn.close()

        if not rows:
            st.info("No professor outreach yet. Use Telegram: PROF <info>")
        else:
            for row in rows:
                score = row[5] or 0
                emoji = "🟢" if score >= 0.8 else "🟡" if score >= 0.6 else "🔴"
                status_icon = "✅" if row[9] == "sent" else "⏳" if row[9] == "pending" else "❌"

                with st.expander(
                    f"{emoji} {status_icon} {row[1]} at {row[2]} - {row[4]} ({score:.0%})"
                ):
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
                        st.text_area(
                            "Email Body",
                            row[8][:1500],
                            height=300,
                            disabled=True,
                            key=f"prof_{row[0]}"
                        )

    except Exception as e:
        st.error(f"Error loading professor data: {e}")

# TAB 4: All Emails
with tab4:
    st.subheader("📧 All Processed Emails")
    session = db.Session()
    emails = session.query(EmailRecord).order_by(
        EmailRecord.fetched_at.desc()
    ).limit(50).all()

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
