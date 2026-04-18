from datetime import datetime, date
from typing import Dict, Any, List, Optional
import json

from sqlalchemy import create_engine, Column, String, Text, DateTime, Float, Boolean, Integer
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker

from config.settings import settings

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

    # Classification
    category = Column(String)
    importance = Column(String)
    is_job_related = Column(Boolean, default=False)
    needs_reply = Column(Boolean, default=False)
    classification_json = Column(Text)

    # Processing status
    is_processed = Column(Boolean, default=False)
    is_replied = Column(Boolean, default=False)
    is_applied = Column(Boolean, default=False)

    # Timestamps
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


class Database:
    def __init__(self):
        self.engine = create_engine(settings.DATABASE_URL)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

    def store_emails(self, emails: List[Dict[str, Any]]):
        session = self.Session()
        try:
            for email in emails:
                existing = session.query(EmailRecord).filter_by(
                    id=email['id']
                ).first()

                if not existing:
                    record = EmailRecord(
                        id=email['id'],
                        thread_id=email.get('thread_id', ''),
                        from_address=email.get('from', ''),
                        to_address=email.get('to', ''),
                        subject=email.get('subject', ''),
                        body_text=email.get('body_text', ''),
                        snippet=email.get('snippet', ''),
                        date_received=email.get('date', ''),
                    )
                    session.add(record)

            session.commit()
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    def get_email(self, email_id: str) -> Optional[Dict[str, Any]]:
        session = self.Session()
        try:
            record = session.query(EmailRecord).filter_by(id=email_id).first()
            if record:
                result = {
                    'id': record.id,
                    'thread_id': record.thread_id,
                    'from': record.from_address,
                    'to': record.to_address,
                    'subject': record.subject,
                    'body_text': record.body_text,
                    'snippet': record.snippet,
                    'date': record.date_received,
                }
                if record.classification_json:
                    result['classification'] = json.loads(record.classification_json)
                return result
            return None
        finally:
            session.close()

    def get_unclassified_emails(self) -> List[Dict[str, Any]]:
        session = self.Session()
        try:
            records = session.query(EmailRecord).filter_by(
                is_processed=False
            ).all()
            results = []
            for r in records:
                email = self.get_email(r.id)
                if email:
                    results.append(email)
            return results
        finally:
            session.close()

    def update_email_classification(self, email_id: str, classification: Dict):
        session = self.Session()
        try:
            record = session.query(EmailRecord).filter_by(id=email_id).first()
            if record:
                record.category = classification.get('category', '')
                record.importance = classification.get('importance', '')
                record.is_job_related = classification.get('is_job_related', False)
                record.needs_reply = classification.get('needs_reply', False)
                record.classification_json = json.dumps(classification)
                record.is_processed = True
                record.processed_at = datetime.utcnow()
                session.commit()
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    def store_job_match(self, email_id: str, match_data: Dict):
        session = self.Session()
        try:
            record = JobMatch(
                email_id=email_id,
                job_title=match_data.get('job_title', ''),
                company=match_data.get('company', ''),
                match_score=match_data.get('overall_match_score', 0),
                recommendation=match_data.get('recommendation', ''),
                match_json=json.dumps(match_data)
            )
            session.add(record)
            session.commit()
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    def get_job_match(self, email_id: str) -> Optional[Dict]:
        session = self.Session()
        try:
            record = session.query(JobMatch).filter_by(
                email_id=email_id
            ).order_by(JobMatch.created_at.desc()).first()
            if record and record.match_json:
                return json.loads(record.match_json)
            return None
        finally:
            session.close()

    def store_reply_draft(self, email_id: str, reply_data: Dict):
        session = self.Session()
        try:
            record = ReplyDraft(
                email_id=email_id,
                subject=reply_data.get('subject', ''),
                body=reply_data.get('body', ''),
                confidence=reply_data.get('confidence', 0),
                requires_review=reply_data.get('requires_human_review', True)
            )
            session.add(record)
            session.commit()
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    def get_reply_draft(self, email_id: str) -> Optional[Dict]:
        session = self.Session()
        try:
            record = session.query(ReplyDraft).filter_by(
                email_id=email_id,
                is_sent=False
            ).order_by(ReplyDraft.created_at.desc()).first()
            if record:
                return {
                    'subject': record.subject,
                    'body': record.body,
                    'confidence': record.confidence,
                    'requires_review': record.requires_review
                }
            return None
        finally:
            session.close()

    def mark_reply_sent(self, email_id: str):
        session = self.Session()
        try:
            record = session.query(ReplyDraft).filter_by(
                email_id=email_id,
                is_sent=False
            ).first()
            if record:
                record.is_sent = True
                record.sent_at = datetime.utcnow()
                session.commit()

            email_record = session.query(EmailRecord).filter_by(
                id=email_id
            ).first()
            if email_record:
                email_record.is_replied = True
                session.commit()
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    def store_cover_letter(self, email_id: str, cover_letter: str):
        session = self.Session()
        try:
            record = session.query(JobMatch).filter_by(
                email_id=email_id
            ).order_by(JobMatch.created_at.desc()).first()
            if record:
                record.cover_letter = cover_letter
                session.commit()
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    def get_daily_stats(self) -> Dict[str, Any]:
        session = self.Session()
        try:
            today = date.today()
            today_start = datetime.combine(today, datetime.min.time())

            total = session.query(EmailRecord).filter(
                EmailRecord.fetched_at >= today_start
            ).count()

            job_emails = session.query(EmailRecord).filter(
                EmailRecord.fetched_at >= today_start,
                EmailRecord.is_job_related == True
            ).count()

            replies_sent = session.query(ReplyDraft).filter(
                ReplyDraft.sent_at >= today_start,
                ReplyDraft.is_sent == True
            ).count()

            replies_pending = session.query(ReplyDraft).filter(
                ReplyDraft.is_sent == False
            ).count()

            from sqlalchemy import func
            avg_score = session.query(
                func.avg(JobMatch.match_score)
            ).filter(
                JobMatch.created_at >= today_start
            ).scalar() or 0

            applications = session.query(JobMatch).filter(
                JobMatch.created_at >= today_start,
                JobMatch.applied == True
            ).count()

            return {
                'total_processed': total,
                'job_emails': job_emails,
                'replies_sent': replies_sent,
                'replies_pending': replies_pending,
                'applications': applications,
                'avg_match_score': float(avg_score)
            }
        finally:
            session.close()


# Run this to add missing column to existing database
def migrate_database():
    """Add missing columns to existing database."""
    import sqlite3
    db_path = "data/assistant.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Add review_reason column if missing
    try:
        cursor.execute("ALTER TABLE reply_drafts ADD COLUMN review_reason TEXT DEFAULT ''")
        print("Added review_reason column ✅")
    except Exception as e:
        print(f"Column may already exist: {e}")
    
    conn.commit()
    conn.close()
