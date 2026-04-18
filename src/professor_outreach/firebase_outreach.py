from datetime import datetime
from typing import List, Dict
from src.utils.firebase_db import init_firebase
from src.utils.logger import get_logger
from firebase_admin import firestore

logger = get_logger(__name__)


class ProfessorOutreachDB:
    """Firebase handler for professor outreach."""

    def __init__(self):
        init_firebase()
        import firebase_admin
        self.db = firestore.client()
        logger.info("Professor outreach Firebase ready ✅")

    def save_outreach(self, data: dict) -> str:
        """Save outreach record. Returns document ID."""
        ref = self.db.collection("professor_outreach").document()
        ref.set({
            **data,
            'status': 'pending',
            'created_at': datetime.utcnow().isoformat()
        })
        return ref.id

    def update_outreach(self, doc_id: str, data: dict):
        """Update record."""
        self.db.collection("professor_outreach").document(doc_id).update(data)

    def update_status(self, doc_id: str, status: str):
        """Update status."""
        update_data = {
            'status': status,
        }
        if status == 'sent':
            update_data['sent_at'] = datetime.utcnow().isoformat()
        self.db.collection("professor_outreach").document(doc_id).update(update_data)

    def get_history(self, limit: int = 10) -> List[Dict]:
        """Get outreach history."""
        try:
            docs = self.db.collection("professor_outreach")\
                .order_by("created_at", direction=firestore.Query.DESCENDING)\
                .limit(limit).stream()
            return [{'id': doc.id, **doc.to_dict()} for doc in docs]
        except Exception as e:
            logger.error(f"Error getting history: {e}")
            return []
