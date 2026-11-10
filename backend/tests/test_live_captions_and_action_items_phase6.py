import pytest
import os
import datetime
from fastapi.testclient import TestClient

from app.main import app
from app.database import Base, SessionLocal, engine, ensure_db_schema
from app.models import User, Meeting, ActionItem
from app.auth import get_password_hash, create_access_token

client = TestClient(app)

@pytest.fixture(scope="module")
def db():
    Base.metadata.create_all(bind=engine)
    ensure_db_schema()
    session = SessionLocal()
    yield session
    session.close()

@pytest.fixture
def test_context(db):
    ts = int(datetime.datetime.utcnow().timestamp() * 1000)
    pwd = get_password_hash("password123")
    host = User(
        email=f"host_phase6_{ts}@meetora.ai",
        hashed_password=pwd,
        full_name="Live Host",
        role="user",
        is_active=True,
    )
    db.add(host)
    db.commit()
    db.refresh(host)

    token = create_access_token({"sub": host.email, "id": host.id})

    meeting = Meeting(
        title="Live Captions Test Room",
        user_id=host.id,
        host_id=host.id,
        source="live_room",
        is_live=True,
        room_name=f"meetora-test-{ts}",
        live_status="live",
        status="live"
    )
    db.add(meeting)
    db.commit()
    db.refresh(meeting)

    return {"host": host, "token": token, "meeting": meeting}


def test_live_caption_without_action_item(test_context, db):
    meeting = test_context["meeting"]
    token = test_context["token"]

    res = client.post(
        f"/meetings/{meeting.id}/live/captions",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "text": "Good morning everyone, let's look at the monthly dashboard.",
            "speaker": "Live Host",
            "timestamp": 12.5,
            "is_final": True
        }
    )
    assert res.status_code == 200
    data = res.json()
    assert data["text"] == "Good morning everyone, let's look at the monthly dashboard."
    assert data["speaker"] == "Live Host"
    assert data["detected_action_item"] is None


def test_live_caption_with_action_item_detection(test_context, db):
    meeting = test_context["meeting"]
    token = test_context["token"]

    res = client.post(
        f"/meetings/{meeting.id}/live/captions",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "text": "I will deploy the new API endpoints by Friday.",
            "speaker": "Sarah Kim",
            "timestamp": 35.0,
            "is_final": True
        }
    )
    assert res.status_code == 200
    data = res.json()
    assert data["detected_action_item"] is not None
    detected = data["detected_action_item"]
    assert "deploy the new api endpoints" in detected["title"].lower()
    assert detected["assignee"] == "Sarah Kim"
    assert detected["deadline"] == "Friday"
    assert detected["confidence_score"] >= 0.8
    assert detected["status"] == "suggested"
    assert detected["start_time_sec"] == 35.0

    # Verify action item was persisted in DB with suggested status
    saved_item = db.query(ActionItem).filter(
        ActionItem.meeting_id == meeting.id,
        ActionItem.deadline == "Friday"
    ).first()
    assert saved_item is not None
    assert saved_item.assignee == "Sarah Kim"
    assert saved_item.status == "suggested"
    assert saved_item.start_time_sec == 35.0

    # Main action items list should NOT include suggested items
    res_main = client.get(
        f"/meetings/{meeting.id}/action-items",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res_main.status_code == 200
    main_items = res_main.json()
    assert not any(i["id"] == saved_item.id for i in main_items)

    # Confirm the item
    res_confirm = client.post(
        f"/meetings/{meeting.id}/live/action-items/{saved_item.id}/confirm",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res_confirm.status_code == 200
    assert res_confirm.json()["status"] == "confirmed"

    # Now it SHOULD appear in the main action items list
    res_main_after = client.get(
        f"/meetings/{meeting.id}/action-items",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res_main_after.status_code == 200
    assert any(i["id"] == saved_item.id for i in res_main_after.json())


def test_manual_live_action_item_crud(test_context, db):
    meeting = test_context["meeting"]
    token = test_context["token"]

    # 1. Create action item manually
    res_create = client.post(
        f"/meetings/{meeting.id}/live/action-items",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "title": "Review UX prototype for mobile app",
            "assignee": "Marcus Lee",
            "deadline": "Tomorrow",
            "priority": "high"
        }
    )
    assert res_create.status_code == 200
    item = res_create.json()
    item_id = item["id"]
    assert item["title"] == "Review UX prototype for mobile app"
    assert item["assignee"] == "Marcus Lee"
    assert item["priority"] == "high"

    # 2. Get live action items list
    res_list = client.get(
        f"/meetings/{meeting.id}/live/action-items",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res_list.status_code == 200
    items = res_list.json()
    assert any(it["id"] == item_id for it in items)

    # 3. Update action item (mark completed)
    res_update = client.patch(
        f"/meetings/{meeting.id}/live/action-items/{item_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"status": "completed"}
    )
    assert res_update.status_code == 200
    assert res_update.json()["status"] == "completed"

    # 4. Dismiss action item via dismiss endpoint
    res_dismiss = client.post(
        f"/meetings/{meeting.id}/live/action-items/{item_id}/dismiss",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res_dismiss.status_code == 200
    assert res_dismiss.json()["status"] == "dismissed"

    # 5. Delete action item
    res_delete = client.delete(
        f"/meetings/{meeting.id}/live/action-items/{item_id}",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res_delete.status_code == 200
    assert res_delete.json()["status"] == "deleted"

    # Verify deletion in DB
    deleted_check = db.query(ActionItem).filter(ActionItem.id == item_id).first()
    assert deleted_check is None
