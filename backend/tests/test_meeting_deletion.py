import os
import pytest
from datetime import datetime
from fastapi.testclient import TestClient

from app.main import app
from app.database import SessionLocal, Base, engine, ensure_db_schema
from app.models import (
    User, Meeting, Transcript, Summary, ActionItem, Decision,
    Comment, MeetingAnalytics, HumanCorrection
)
from app.auth import get_password_hash, create_access_token
from app.search_vector import vector_search_service, answer_meeting_rag

client = TestClient(app)

@pytest.fixture(scope="module")
def db():
    Base.metadata.create_all(bind=engine)
    ensure_db_schema()
    session = SessionLocal()
    yield session
    session.close()

def create_test_user(db, email_prefix: str, role: str = "user") -> tuple[User, str]:
    ts = int(datetime.now().timestamp() * 1000)
    email = f"{email_prefix}_{ts}@meetora.ai"
    user = User(
        email=email,
        hashed_password=get_password_hash("Password123!"),
        full_name=f"Test {email_prefix.title()}",
        role=role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_access_token(data={"sub": user.email, "role": user.role, "user_id": user.id})
    return user, token

def test_owner_can_delete_meeting_and_detach_corrections(db):
    """
    Test that a meeting owner can delete their meeting:
    - Returns 204 No Content
    - Cascade deletes transcripts, action items, decisions, summary, comments, analytics
    - Detaches human corrections (keeps retraining dataset records intact with meeting_id/action_item_id = None)
    - Purges vector entries so meeting never appears in semantic search or RAG Q&A
    """
    owner, owner_token = create_test_user(db, "owner")
    
    # Create meeting with audio file simulation
    meeting = Meeting(
        title="Architecture Review for Mobile Sync",
        user_id=owner.id,
        status="completed",
        duration_seconds=300,
        audio_path="temp_test_audio.wav"
    )
    db.add(meeting)
    db.commit()
    db.refresh(meeting)
    m_id = meeting.id

    # Add child relations
    tr1 = Transcript(meeting_id=m_id, speaker="Jordan", text="Let's optimize the SQLite database queries", start_time=5.0, end_time=10.0)
    tr2 = Transcript(meeting_id=m_id, speaker="Sarah", text="I will finish the mobile review by Friday", start_time=12.0, end_time=20.0, is_action_item=True)
    db.add_all([tr1, tr2])

    ai1 = ActionItem(meeting_id=m_id, title="Finish mobile review", assignee="Sarah", deadline="Friday", status="pending")
    db.add(ai1)
    db.commit()
    db.refresh(ai1)

    dec1 = Decision(meeting_id=m_id, decision_text="Use SQLite with WAL mode")
    sum1 = Summary(meeting_id=m_id, overview="Discussed mobile architecture", key_takeaways=["SQLite WAL"])
    com1 = Comment(meeting_id=m_id, user_id=owner.id, text="Great discussion")
    ana1 = MeetingAnalytics(meeting_id=m_id, sentiment_score=0.9, talk_to_listen_ratio=1.0)
    db.add_all([dec1, sum1, com1, ana1])

    # Add human correction linked to this meeting and action item
    correction = HumanCorrection(
        user_id=owner.id,
        meeting_id=m_id,
        action_item_id=ai1.id,
        original_text="Finish review",
        corrected_text="Finish mobile architecture review",
        original_assignee="Sarah",
        corrected_assignee="Sarah Kim",
        original_deadline="Fri",
        corrected_deadline="Friday",
        correction_type="human_edit",
        model_version="distilbert-v2.4"
    )
    db.add(correction)
    db.commit()
    db.refresh(correction)
    corr_id = correction.id

    # Verify RAG can find the meeting before deletion
    rag_before = answer_meeting_rag(query="optimize SQLite", meeting_id=m_id, user_id=owner.id, db=db)
    assert len(rag_before["citations"]) > 0

    # Owner deletes the meeting
    res = client.delete(f"/meetings/{m_id}", headers={"Authorization": f"Bearer {owner_token}"})
    assert res.status_code == 204

    # 1. Meeting must be gone
    assert db.query(Meeting).filter(Meeting.id == m_id).first() is None

    # 2. Child tables must be empty for this meeting
    assert db.query(Transcript).filter(Transcript.meeting_id == m_id).count() == 0
    assert db.query(ActionItem).filter(ActionItem.meeting_id == m_id).count() == 0
    assert db.query(Decision).filter(Decision.meeting_id == m_id).count() == 0
    assert db.query(Summary).filter(Summary.meeting_id == m_id).first() is None
    assert db.query(Comment).filter(Comment.meeting_id == m_id).count() == 0
    assert db.query(MeetingAnalytics).filter(MeetingAnalytics.meeting_id == m_id).first() is None

    # 3. Human correction must be KEPT but DETACHED
    db.expire_all()
    retained_corr = db.query(HumanCorrection).filter(HumanCorrection.id == corr_id).first()
    assert retained_corr is not None
    assert retained_corr.meeting_id is None
    assert retained_corr.action_item_id is None
    assert retained_corr.corrected_text == "Finish mobile architecture review"

    # 4. RAG / Vector search must return no citations for deleted meeting
    rag_after = answer_meeting_rag(query="optimize SQLite", meeting_id=m_id, user_id=owner.id, db=db)
    assert len(rag_after["citations"]) == 0

def test_unauthorized_user_cannot_delete_meeting(db):
    """A non-owner non-admin user must get 403 Forbidden."""
    owner, _ = create_test_user(db, "owner2")
    other_user, other_token = create_test_user(db, "other")

    meeting = Meeting(title="Secret Q4 Strategy", user_id=owner.id, status="completed", duration_seconds=180)
    db.add(meeting)
    db.commit()
    db.refresh(meeting)

    # Other user attempts delete
    res = client.delete(f"/meetings/{meeting.id}", headers={"Authorization": f"Bearer {other_token}"})
    assert res.status_code == 403

    # Meeting must still exist
    assert db.query(Meeting).filter(Meeting.id == meeting.id).first() is not None

def test_admin_can_delete_any_meeting(db):
    """An admin user can delete meetings belonging to any user."""
    owner, _ = create_test_user(db, "owner3")
    admin_user, admin_token = create_test_user(db, "admin_user", role="admin")

    meeting = Meeting(title="Customer Discovery Acme", user_id=owner.id, status="completed", duration_seconds=240)
    db.add(meeting)
    db.commit()
    db.refresh(meeting)

    # Admin deletes the meeting
    res = client.delete(f"/meetings/{meeting.id}", headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 204
    assert db.query(Meeting).filter(Meeting.id == meeting.id).first() is None

def test_delete_missing_meeting_returns_404(db):
    """Deleting a non-existent meeting ID must return 404."""
    user, token = create_test_user(db, "regular")
    res = client.delete("/meetings/99999999", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 404

def test_bulk_delete_meetings(db):
    """
    Test POST /meetings/bulk-delete:
    - Deletes owned meetings
    - Reports 403 for unauthorized meetings
    - Reports 404 for missing meetings
    """
    user1, token1 = create_test_user(db, "bulk_user1")
    user2, _ = create_test_user(db, "bulk_user2")

    m1 = Meeting(title="User1 Sync A", user_id=user1.id, status="completed")
    m2 = Meeting(title="User2 Private Notes", user_id=user2.id, status="completed")
    m3 = Meeting(title="User1 Sync B", user_id=user1.id, status="completed")
    db.add_all([m1, m2, m3])
    db.commit()
    db.refresh(m1)
    db.refresh(m2)
    db.refresh(m3)

    # User 1 attempts to bulk-delete m1, m2 (forbidden), and 999888 (missing)
    payload = {"meeting_ids": [m1.id, m2.id, 999888]}
    res = client.post("/meetings/bulk-delete", json=payload, headers={"Authorization": f"Bearer {token1}"})
    assert res.status_code == 200
    data = res.json()
    assert m1.id in data["deleted"]
    assert db.query(Meeting).filter(Meeting.id == m1.id).first() is None

    failed_ids = [f["id"] for f in data["failed"]]
    assert m2.id in failed_ids
    assert 999888 in failed_ids
    # m2 was not deleted
    assert db.query(Meeting).filter(Meeting.id == m2.id).first() is not None
