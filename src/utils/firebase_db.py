import json
import os
from datetime import datetime, date
from typing import Dict, Any, List, Optional
import firebase_admin
from firebase_admin import credentials, firestore
from src.utils.logger import get_logger

logger = get_logger(__name__)


def init_firebase():
    """Initialize Firebase from file or Streamlit secrets."""
    if firebase_admin._apps:
        return

    # Method 1: Local file (Mac Mini)
    if os.path.exists("config/firebase_key.json"):
        cred = credentials.Certificate("config/firebase_key.json")
        firebase_admin.initialize_app(cred)
        logger.info("Firebase initialized from local key file ✅")
        return

    # Method 2: Streamlit secrets (Cloud deployment)
    try:
        import streamlit as st
        firebase_config = dict(st.secrets["firebase"])
        # Fix private key newlines
        firebase_config["private_key"] = firebase_config["private_key"].replace("\\n", "\n")
        cred = credentials.Certificate(firebase_config)
        firebase_admin.initialize_app(cred)
        logger.info("Firebase initialized from Streamlit secrets ✅")
        return
    except Exception as e:
        logger.warning(f"Streamlit secrets not available: {e}")

    # Method 3: Environment variable
    firebase_json = os.environ.get("FIREBASE_KEY_JSON")
    if firebase_json:
        firebase_config = json.loads(firebase_json)
        cred = credentials.Certificate(firebase_config)
        firebase_admin.initialize_app(cred)
        logger.info("Firebase initialized from environment variable ✅")
        return

    raise ValueError("No Firebase credentials found!")


class FirebaseDatabase:
    """Firebase Firestore database handler."""

    def __init__(self):
        init_firebase()
        self.db = firestore.client()
        logger.info("Firebase connected ✅")

    def store_emails(self, emails: List[Dict[str, Any]]):
        """Store emails in Firestore."""
        for email in emails:
            ref = self.db.collection("emails").document(email['id'])
            if not ref.get().exists:
                ref.set({
                    'id': email['id'],
                    'thread_id': email.get('thread_id', ''),
                    'from_address': email.get('from', ''),
                    'to_address': email.get('to', ''),
                    'subject': email.get('subject', ''),
                    'body_text': email.get('body_text', '')[:5000],
                    'snippet': email.get('snippet', ''),
                    'date_received': email.get('date', ''),
                    'is_processed': False,
                    'is_replied': False,
                    'is_applied': False,
                    'fetched_at': datetime.utcnow().isoformat()
                })
        logger.info(f"Stored {len(emails)} emails to Firebase")

    def get_email(self, email_id: str) -> Optional[Dict[str, Any]]:
        """Get single email by ID."""
        doc = self.db.collection("emails").document(email_id).get()
        if doc.exists:
            data = doc.to_dict()
            return {
                'id': data.get('id', ''),
                'thread_id': data.get('thread_id', ''),
                'from': data.get('from_address', ''),
                'to': data.get('to_address', ''),
                'subject': data.get('subject', ''),
                'body_text': data.get('body_text', ''),
                'snippet': data.get('snippet', ''),
                'date': data.get('date_received', ''),
                'classification': data.get('classification', {})
            }
        return None

    def get_unclassified_emails(self) -> List[Dict[str, Any]]:
        """Get unprocessed emails."""
        docs = self.db.collection("emails")\
            .where(filter=firestore.FieldFilter("is_processed", "==", False))\
            .stream()
        results = []
        for doc in docs:
            email = self.get_email(doc.id)
            if email:
                results.append(email)
        return results

    def update_email_classification(self, email_id: str, classification: Dict):
        """Update email with classification."""
        self.db.collection("emails").document(email_id).update({
            'category': classification.get('category', ''),
            'importance': classification.get('importance', ''),
            'is_job_related': classification.get('is_job_related', False),
            'needs_reply': classification.get('needs_reply', False),
            'classification': classification,
            'is_processed': True,
            'processed_at': datetime.utcnow().isoformat()
        })

    def store_job_match(self, email_id: str, match_data: Dict):
        """Store job match."""
        self.db.collection("job_matches").add({
            'email_id': email_id,
            'job_title': match_data.get('job_title', ''),
            'company': match_data.get('company', ''),
            'match_score': match_data.get('overall_match_score', 0),
            'recommendation': match_data.get('recommendation', ''),
            'match_data': match_data,
            'applied': False,
            'created_at': datetime.utcnow().isoformat()
        })

    def get_job_match(self, email_id: str) -> Optional[Dict]:
        """Get job match for email."""
        docs = self.db.collection("job_matches")\
            .where(filter=firestore.FieldFilter("email_id", "==", email_id))\
            .limit(1).stream()
        for doc in docs:
            return doc.to_dict().get('match_data', {})
        return None

    def store_reply_draft(self, email_id: str, reply_data: Dict):
        """Store reply draft."""
        self.db.collection("reply_drafts").add({
            'email_id': email_id,
            'subject': reply_data.get('subject', ''),
            'body': reply_data.get('body', ''),
            'confidence': reply_data.get('confidence', 0),
            'requires_review': reply_data.get('requires_human_review', True),
            'review_reason': reply_data.get('review_reason', ''),
            'is_sent': False,
            'created_at': datetime.utcnow().isoformat()
        })

    def get_reply_draft(self, email_id: str) -> Optional[Dict]:
        """Get pending reply draft."""
        docs = self.db.collection("reply_drafts")\
            .where(filter=firestore.FieldFilter("email_id", "==", email_id))\
            .where(filter=firestore.FieldFilter("is_sent", "==", False))\
            .limit(1).stream()
        for doc in docs:
            data = doc.to_dict()
            return {
                'subject': data.get('subject', ''),
                'body': data.get('body', ''),
                'confidence': data.get('confidence', 0),
                'requires_review': data.get('requires_review', True)
            }
        return None

    def mark_reply_sent(self, email_id: str):
        """Mark reply as sent."""
        docs = self.db.collection("reply_drafts")\
            .where(filter=firestore.FieldFilter("email_id", "==", email_id))\
            .where(filter=firestore.FieldFilter("is_sent", "==", False))\
            .stream()
        for doc in docs:
            doc.reference.update({
                'is_sent': True,
                'sent_at': datetime.utcnow().isoformat()
            })
        self.db.collection("emails").document(email_id).update({
            'is_replied': True
        })

    def store_cover_letter(self, email_id: str, cover_letter: str):
        """Store cover letter."""
        docs = self.db.collection("job_matches")\
            .where(filter=firestore.FieldFilter("email_id", "==", email_id))\
            .limit(1).stream()
        for doc in docs:
            doc.reference.update({'cover_letter': cover_letter})

    def mark_job_applied(self, doc_id: str):
        """Mark job as applied."""
        self.db.collection("job_matches").document(doc_id).update({
            'applied': True
        })

    def get_all_emails(self, limit: int = 50) -> List[Dict]:
        """Get all emails for dashboard."""
        try:
            docs = self.db.collection("emails")\
                .order_by("fetched_at", direction=firestore.Query.DESCENDING)\
                .limit(limit).stream()
            return [doc.to_dict() for doc in docs]
        except Exception as e:
            logger.error(f"Error getting emails: {e}")
            return []

    def get_all_job_matches(self, limit: int = 20) -> List[Dict]:
        """Get all job matches."""
        try:
            docs = self.db.collection("job_matches")\
                .order_by("created_at", direction=firestore.Query.DESCENDING)\
                .limit(limit).stream()
            return [{'id': doc.id, **doc.to_dict()} for doc in docs]
        except Exception as e:
            logger.error(f"Error getting job matches: {e}")
            return []

    def get_all_reply_drafts(self, limit: int = 20) -> List[Dict]:
        """Get pending reply drafts."""
        try:
            docs = self.db.collection("reply_drafts")\
                .where(filter=firestore.FieldFilter("is_sent", "==", False))\
                .order_by("created_at", direction=firestore.Query.DESCENDING)\
                .limit(limit).stream()
            return [{'id': doc.id, **doc.to_dict()} for doc in docs]
        except Exception as e:
            logger.error(f"Error getting reply drafts: {e}")
            return []

    def get_professor_outreach(self, limit: int = 20) -> List[Dict]:
        """Get professor outreach history."""
        try:
            docs = self.db.collection("professor_outreach")\
                .order_by("created_at", direction=firestore.Query.DESCENDING)\
                .limit(limit).stream()
            return [{'id': doc.id, **doc.to_dict()} for doc in docs]
        except Exception as e:
            logger.error(f"Error getting professor outreach: {e}")
            return []

    def get_daily_stats(self) -> Dict[str, Any]:
        """Get statistics."""
        try:
            today = date.today().isoformat()
            all_emails = list(self.db.collection("emails").stream())
            total = sum(1 for e in all_emails
                       if e.to_dict().get('fetched_at', '') >= today)
            job_emails = sum(1 for e in all_emails
                            if e.to_dict().get('fetched_at', '') >= today
                            and e.to_dict().get('is_job_related', False))
            all_replies = list(self.db.collection("reply_drafts").stream())
            replies_pending = sum(1 for r in all_replies
                                 if not r.to_dict().get('is_sent', False))
            replies_sent = sum(1 for r in all_replies
                              if r.to_dict().get('is_sent', False)
                              and r.to_dict().get('sent_at', '') >= today)
            all_jobs = list(self.db.collection("job_matches").stream())
            applications = sum(1 for j in all_jobs
                              if j.to_dict().get('applied', False)
                              and j.to_dict().get('created_at', '') >= today)
            return {
                'total_processed': total,
                'job_emails': job_emails,
                'replies_sent': replies_sent,
                'replies_pending': replies_pending,
                'applications': applications,
                'avg_match_score': 0.0
            }
        except Exception as e:
            logger.error(f"Stats error: {e}")
            return {
                'total_processed': 0, 'job_emails': 0,
                'replies_sent': 0, 'replies_pending': 0,
                'applications': 0, 'avg_match_score': 0.0
            }
