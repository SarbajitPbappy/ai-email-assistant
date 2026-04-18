import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import streamlit as st
import json
from datetime import datetime
from src.utils.firebase_db import FirebaseDatabase
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

# Initialize Firebase
@st.cache_resource
def get_db():
    return FirebaseDatabase()

db = get_db()

st.title("🤖 AI Personal Assistant Dashboard")
st.caption(f"Profile: {settings.USER_NAME} | Powered by Ollama (Local & Free)")

# Sidebar
with st.sidebar:
    st.header("⚙️ Controls")
    if st.button("🔄 Process Emails Now", type="primary", use_container_width=True):
        with st.spinner("Processing..."):
            try:
                from src.agent.orchestrator import EmailAssistantOrchestrator
                agent = EmailAssistantOrchestrator()
                stats = agent.run(max_emails=10, query="in:inbox")
                st.success(f"Done! {stats['total']} emails processed")
                st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")

    st.divider()
    st.header("📊 Today's Stats")
    try:
        stats = db.get_daily_stats()
        st.metric("Emails Processed", stats['total_processed'])
        st.metric("Job Opportunities", stats['job_emails'])
        st.metric("Replies Pending", stats['replies_pending'])
        st.metric("Replies Sent", stats['replies_sent'])
    except Exception as e:
        st.error(f"Stats error: {e}")

    if st.button("🚪 Logout"):
        st.session_state.authenticated = False
        st.rerun()

# Main Tabs
tab1, tab2, tab3, tab4 = st.tabs([
    "💼 Job Matches",
    "✍️ Reply Drafts",
    "🎓 Professor Outreach",
    "📧 All Emails"
])

# TAB 1: Job Matches
with tab1:
    st.subheader("💼 Job Matches & Cover Letters")
    try:
        matches = db.get_all_job_matches(limit=20)
        if not matches:
            st.info("No job matches yet. Click 'Process Emails Now'.")
        else:
            for match in matches:
                score = match.get('match_score', 0)
                emoji = "🟢" if score >= 0.8 else "🟡" if score >= 0.6 else "🔴"
                rec = match.get('recommendation', 'N/A')

                with st.expander(
                    f"{emoji} {match.get('job_title','Unknown')} at "
                    f"{match.get('company','Unknown')} - {score:.0%}"
                ):
                    col1, col2, col3 = st.columns(3)
                    col1.metric("Score", f"{score:.0%}")
                    col2.metric("Recommendation", rec)
                    col3.metric("Applied", "Yes ✅" if match.get('applied') else "No")

                    match_data = match.get('match_data', {})
                    if match_data:
                        st.write("**Matching Skills:**",
                                ", ".join(match_data.get('matching_skills', [])))
                        st.write("**Missing Skills:**",
                                ", ".join(match_data.get('missing_skills', [])))
                        st.write("**Reasoning:**", match_data.get('reasoning', ''))

                    if match.get('cover_letter'):
                        st.text_area(
                            "Cover Letter",
                            match['cover_letter'],
                            height=200,
                            key=f"cl_{match['id']}"
                        )

                    if st.button("✅ Mark Applied", key=f"applied_{match['id']}"):
                        db.mark_job_applied(match['id'])
                        st.success("Marked!")
                        st.rerun()
    except Exception as e:
        st.error(f"Error: {e}")

# TAB 2: Reply Drafts
with tab2:
    st.subheader("✍️ Reply Drafts - Review & Send")
    try:
        drafts = db.get_all_reply_drafts(limit=20)
        if not drafts:
            st.info("No pending replies.")
        else:
            for draft in drafts:
                email = db.get_email(draft.get('email_id', ''))
                subject = email.get('subject', 'Unknown') if email else 'Unknown'
                from_addr = email.get('from', 'Unknown') if email else 'Unknown'

                with st.expander(f"📧 Re: {subject[:60]}"):
                    st.write(f"**To:** {from_addr}")
                    st.write(f"**Subject:** {draft.get('subject', '')}")
                    st.write(f"**Confidence:** {draft.get('confidence', 0):.0%}")

                    edited = st.text_area(
                        "Edit reply:",
                        draft.get('body', ''),
                        height=200,
                        key=f"draft_{draft['id']}"
                    )

                    col1, col2 = st.columns(2)
                    if col1.button("📤 Send", key=f"send_{draft['id']}", type="primary"):
                        from src.email_reader.gmail_client import GmailClient
                        gmail = GmailClient()
                        if email:
                            success = gmail.send_email(
                                to=email.get('from', ''),
                                subject=draft.get('subject', ''),
                                body=edited,
                                thread_id=email.get('thread_id', '')
                            )
                            if success:
                                db.mark_reply_sent(draft['email_id'])
                                st.success("Sent! ✅")
                                st.rerun()

                    if col2.button("🗑️ Discard", key=f"del_{draft['id']}"):
                        from firebase_admin import firestore as fs
                        db.db.collection("reply_drafts")\
                            .document(draft['id'])\
                            .update({'is_sent': True})
                        st.rerun()
    except Exception as e:
        st.error(f"Error: {e}")

# TAB 3: Professor Outreach
with tab3:
    st.subheader("🎓 Professor Outreach History")
    try:
        outreaches = db.get_professor_outreach(limit=20)
        if not outreaches:
            st.info("No professor outreach yet.\nUse Telegram: PROF <info>")
        else:
            for item in outreaches:
                score = item.get('alignment_score', 0)
                emoji = "🟢" if score >= 0.8 else "🟡" if score >= 0.6 else "🔴"
                status = item.get('status', 'pending')
                status_icon = "✅" if status == "sent" else "⏳" if status == "pending" else "❌"

                with st.expander(
                    f"{emoji} {status_icon} {item.get('professor_name','Unknown')} "
                    f"at {item.get('university','Unknown')} - "
                    f"{item.get('application_type','N/A')} ({score:.0%})"
                ):
                    col1, col2, col3 = st.columns(3)
                    col1.metric("Score", f"{score:.0%}")
                    col2.metric("Type", item.get('application_type', 'N/A'))
                    col3.metric("Status", status)

                    st.write(f"**Email:** {item.get('professor_email', 'N/A')}")
                    st.write(f"**Intake:** {item.get('intake', 'N/A')}")
                    st.write(f"**Subject:** {item.get('subject', 'N/A')}")

                    if item.get('sent_at'):
                        st.write(f"**Sent:** {item['sent_at']}")

                    if item.get('body'):
                        st.text_area(
                            "Email Body",
                            item['body'],
                            height=300,
                            disabled=True,
                            key=f"prof_{item['id']}"
                        )
    except Exception as e:
        st.error(f"Error loading professor data: {e}")

# TAB 4: All Emails
with tab4:
    st.subheader("📧 All Processed Emails")
    try:
        emails = db.get_all_emails(limit=50)
        icons = {
            'critical': '🔴', 'high': '🟠',
            'medium': '🟡', 'low': '🟢', 'ignore': '⚪'
        }
        if not emails:
            st.info("No emails processed yet.")
        else:
            for email in emails:
                icon = icons.get(email.get('importance', ''), '⚪')
                job = "💼" if email.get('is_job_related') else ""
                subject = email.get('subject', 'No Subject')

                with st.expander(f"{icon}{job} {subject}"):
                    col1, col2 = st.columns(2)
                    col1.write(f"**From:** {email.get('from_address', '')}")
                    col1.write(f"**Category:** {email.get('category', '')}")
                    col2.write(f"**Importance:** {email.get('importance', '')}")
                    col2.write(f"**Job:** {'Yes ✅' if email.get('is_job_related') else 'No'}")

                    if email.get('body_text'):
                        st.text_area(
                            "Body",
                            email['body_text'][:500],
                            disabled=True,
                            key=f"email_{email.get('id', '')}"
                        )
    except Exception as e:
        st.error(f"Error: {e}")
