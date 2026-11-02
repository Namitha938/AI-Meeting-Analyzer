import os
import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient

from app.main import app
from app.database import SessionLocal, Base, engine, ensure_db_schema
from app.models import (
    User, Meeting, Transcript, Summary, ActionItem, Decision,
    Comment, MeetingAnalytics, HumanCorrection, MeetingShare
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

def test_owner_can_edit_meeting_details(db):
    """Owner can update title, tag, description, and scheduled date."""
    owner, token = create_test_user(db, "edit_owner")
    meeting = Meeting(
        title="Initial Roadmap Discussion",
        user_id=owner.id,
        duration_seconds=1800,
        status="completed",
        tags=["Product"],
        color="violet",
    )
    db.add(meeting)
    db.commit()
    db.refresh(meeting)

    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "title": "Updated Q4 AI Strategy",
        "tag": "Planning",
        "description": "Comprehensive review of Q4 AI architecture and deliverables.",
    }

    res = client.patch(f"/meetings/{meeting.id}", json=payload, headers=headers)
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["title"] == "Updated Q4 AI Strategy"
    assert "Planning" in data["tags"]
    assert data["description"] == "Comprehensive review of Q4 AI architecture and deliverables."
    assert "updated_at" in data

def test_unauthorized_user_gets_403(db):
    """Non-owner without edit permissions receives 403 Forbidden."""
    owner, _ = create_test_user(db, "perm_owner")
    other_user, other_token = create_test_user(db, "unauth_user")

    meeting = Meeting(
        title="Confidential Strategy Sync",
        user_id=owner.id,
        duration_seconds=900,
        status="completed",
        tags=["Product"],
    )
    db.add(meeting)
    db.commit()
    db.refresh(meeting)

    headers = {"Authorization": f"Bearer {other_token}"}
    res = client.patch(f"/meetings/{meeting.id}", json={"title": "Hacked Title"}, headers=headers)
    assert res.status_code == 403

def test_shared_editor_succeeds_and_viewer_gets_403(db):
    """Shared collaborator with can_edit=True succeeds; viewer with can_edit=False gets 403."""
    owner, _ = create_test_user(db, "share_owner")
    editor, editor_token = create_test_user(db, "shared_editor")
    viewer, viewer_token = create_test_user(db, "shared_viewer")

    meeting = Meeting(
        title="Cross-Team Collaboration Review",
        user_id=owner.id,
        status="completed",
        tags=["General"],
    )
    db.add(meeting)
    db.commit()
    db.refresh(meeting)

    # Add share permissions
    share_editor = MeetingShare(meeting_id=meeting.id, user_id=editor.id, can_edit=True)
    share_viewer = MeetingShare(meeting_id=meeting.id, user_id=viewer.id, can_edit=False)
    db.add_all([share_editor, share_viewer])
    db.commit()

    # Viewer attempts edit -> 403 Forbidden
    res_viewer = client.patch(
        f"/meetings/{meeting.id}",
        json={"title": "Viewer Edit Attempt"},
        headers={"Authorization": f"Bearer {viewer_token}"}
    )
    assert res_viewer.status_code == 403

    # Editor attempts edit -> 200 OK
    res_editor = client.patch(
        f"/meetings/{meeting.id}",
        json={"title": "Approved Collaboration Title"},
        headers={"Authorization": f"Bearer {editor_token}"}
    )
    assert res_editor.status_code == 200
    assert res_editor.json()["title"] == "Approved Collaboration Title"

def test_invalid_title_and_tag_get_422(db):
    """Invalid title (empty or >200 chars) or invalid tag triggers 422 Unprocessable Entity."""
    owner, token = create_test_user(db, "validation_user")
    meeting = Meeting(title="Validation Meeting", user_id=owner.id, status="completed")
    db.add(meeting)
    db.commit()
    db.refresh(meeting)

    headers = {"Authorization": f"Bearer {token}"}

    # Empty title
    res1 = client.patch(f"/meetings/{meeting.id}", json={"title": ""}, headers=headers)
    assert res1.status_code == 422

    # Title exceeds 200 characters
    res2 = client.patch(f"/meetings/{meeting.id}", json={"title": "A" * 205}, headers=headers)
    assert res2.status_code == 422

    # Invalid tag
    res3 = client.patch(f"/meetings/{meeting.id}", json={"tag": "NonExistentTagXYZ"}, headers=headers)
    assert res3.status_code == 422

def test_stale_updated_at_gets_409_concurrency(db):
    """Providing a stale updated_at timestamp returns 409 Conflict."""
    owner, token = create_test_user(db, "concurrency_user")
    meeting = Meeting(
        title="Concurrent Editing Meeting",
        user_id=owner.id,
        status="completed",
        updated_at=datetime.utcnow()
    )
    db.add(meeting)
    db.commit()
    db.refresh(meeting)

    headers = {"Authorization": f"Bearer {token}"}

    # Stale timestamp from 1 hour ago
    stale_ts = (datetime.utcnow() - timedelta(hours=1)).isoformat()
    res = client.patch(
        f"/meetings/{meeting.id}",
        json={"title": "Overwrite Attempt", "updated_at": stale_ts},
        headers=headers
    )
    assert res.status_code == 409
    assert "changed by someone else" in res.json()["detail"].lower()

def test_summary_edit_and_regeneration_preservation(db):
    """
    Editing summary sets edited_by_user=True, logs HumanCorrection, and
    regeneration resets edited_by_user=False.
    """
    owner, token = create_test_user(db, "summary_owner")
    meeting = Meeting(title="Sprint Summary Review", user_id=owner.id, status="completed")
    db.add(meeting)
    db.commit()
    db.refresh(meeting)

    summary = Summary(
        meeting_id=meeting.id,
        overview="AI generated original overview.",
        key_takeaways=["Original takeaway 1"],
        next_steps="Original next steps",
        edited_by_user=False
    )
    db.add(summary)
    db.commit()

    headers = {"Authorization": f"Bearer {token}"}
    patch_res = client.patch(
        f"/meetings/{meeting.id}/summary",
        json={
            "overview": "Human-refined executive overview: Q4 targets locked.",
            "key_takeaways": ["Locked release date", "Approved budget"]
        },
        headers=headers
    )
    assert patch_res.status_code == 200
    s_data = patch_res.json()
    assert s_data["overview"] == "Human-refined executive overview: Q4 targets locked."
    assert s_data["edited_by_user"] is True
    assert s_data["updated_by"] is not None

    # Verify correction was logged to HumanCorrection retraining dataset
    db.expire_all()
    corr = db.query(HumanCorrection).filter(
        HumanCorrection.meeting_id == meeting.id,
        HumanCorrection.correction_type == "summary"
    ).first()
    assert corr is not None
    assert "Human-refined executive overview" in corr.corrected_text

    # Verify explicit AI regeneration resets edited_by_user to False
    regen_res = client.post(f"/meetings/{meeting.id}/summary/regenerate", headers=headers)
    assert regen_res.status_code == 200
    assert regen_res.json()["edited_by_user"] is False

def test_transcript_line_edit_updates_vector_index_and_logs_correction(db):
    """
    Correcting a transcript line updates text & speaker, re-embeds for vector search / RAG,
    preserves timestamps, and logs to HumanCorrection.
    """
    owner, token = create_test_user(db, "transcript_owner")
    meeting = Meeting(title="Transcript Accuracy Test", user_id=owner.id, status="completed")
    db.add(meeting)
    db.commit()
    db.refresh(meeting)

    line = Transcript(
        meeting_id=meeting.id,
        speaker="Speaker 1",
        start_time=12.5,
        end_time=16.0,
        text="The server deployment failed on Staging.",
    )
    db.add(line)
    db.commit()
    db.refresh(line)

    headers = {"Authorization": f"Bearer {token}"}
    patch_res = client.patch(
        f"/meetings/{meeting.id}/transcript/{line.id}",
        json={
            "text": "The server deployment succeeded on Kubernetes production cluster.",
            "speaker": "Lead DevOps Engineer",
            # Attempting to edit timestamp should be ignored/disallowed
            "start_time": 999.0
        },
        headers=headers
    )
    assert patch_res.status_code == 200
    t_data = patch_res.json()
    assert t_data["text"] == "The server deployment succeeded on Kubernetes production cluster."
    assert t_data["speaker"] == "Lead DevOps Engineer"
    # Timestamp is preserved (not 999.0)
    assert t_data["start_time"] == 12.5

    # Expire test session cache so fresh row is queried from DB
    db.expire_all()

    # Verify RAG / semantic search now retrieves the corrected text
    rag_result = answer_meeting_rag(
        query="Kubernetes production cluster deployment status",
        meeting_id=meeting.id,
        user_id=owner.id,
        db=db
    )
    assert "succeeded" in rag_result["answer"].lower() or any(
        "kubernetes" in c.get("text", "").lower() for c in rag_result.get("citations", [])
    )

    # Verify correction logged
    db.expire_all()
    corr = db.query(HumanCorrection).filter(
        HumanCorrection.meeting_id == meeting.id,
        HumanCorrection.correction_type == "transcript_edit"
    ).first()
    assert corr is not None
    assert "Kubernetes production cluster" in corr.corrected_text
    assert corr.corrected_assignee == "Lead DevOps Engineer"

def test_edits_blocked_while_meeting_is_processing(db):
    """Attempts to edit details, summary, or transcript while meeting is processing are blocked."""
    owner, token = create_test_user(db, "processing_user")
    meeting = Meeting(
        title="Live Ingestion In Progress",
        user_id=owner.id,
        status="transcribing",  # actively processing
    )
    db.add(meeting)
    db.commit()
    db.refresh(meeting)

    headers = {"Authorization": f"Bearer {token}"}
    res = client.patch(
        f"/meetings/{meeting.id}",
        json={"title": "Should Not Edit"},
        headers=headers
    )
    assert res.status_code == 400
    assert "currently processing" in res.json()["detail"].lower()
