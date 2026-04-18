import firebase_admin
from firebase_admin import firestore, credentials
from datetime import datetime
from src.utils.logger import get_logger

logger = get_logger(__name__)


class ProfessorOutreachDB:
    """Firebase handler for professor outreach data."""

    def __init__(self):
        if not firebase_admin._apps:
            cred = credentials.Certificate("config/firebase_key.json")
            firebase_admin.initialize_app(cred)
        self.db = firestore.client()
        logger.info("Professor outreach Firebase ready ✅")

    def save_outreach(self, data: dict) -> str:
        """Save professor outreach record. Returns document ID."""
        ref = self.db.collection("professor_outreach").document()
        ref.set({
            **data,
            'status': 'pending',
            'created_at': datetime.utcnow().isoformat()
        })
        logger.info(f"Saved outreach: {data.get('professor_name')} - ID: {ref.id}")
        return ref.id

    def update_outreach(self, doc_id: str, data: dict):
        """Update an outreach record."""
        self.db.collection("professor_outreach").document(doc_id).update(data)

    def update_status(self, doc_id: str, status: str):
        """Update outreach status."""
        self.db.collection("professor_outreach").document(doc_id).update({
            'status': status,
            'sent_at': datetime.utcnow().isoformat() if status == 'sent' else None
        })

    def get_history(self, limit: int = 10) -> list:
        """Get professor outreach history."""
        try:
            docs = self.db.collection("professor_outreach")\
                .order_by("created_at", direction=firestore.Query.DESCENDING)\
                .limit(limit).stream()
            return [{'id': doc.id, **doc.to_dict()} for doc in docs]
        except Exception as e:
            logger.error(f"Error getting history: {e}")
            return []
