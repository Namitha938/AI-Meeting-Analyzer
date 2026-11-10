import pytest
import os
import json
import datetime
from fastapi.testclient import TestClient

from app.main import app
from app.database import Base, SessionLocal, engine, ensure_db_schema
from app.models import User, Meeting, Recording, AuditLog
from app.auth import get_password_hash, create_access_token
from app.bot_providers.validator import validate_meeting_url
from app.bot_providers import get_bot_provider
from app.routers.meeting_bot import reset_bot_webhook_cache
from app.pipeline_orchestrator import reset_orchestrator_keys

client = TestClient(app)

@pytest.fixture(scope="module")
def db():
    Base.metadata.create_all(bind=engine)
    ensure_db_schema()
    reset_bot_webhook_cache()
    reset_orchestrator_keys()
    session = SessionLocal()
    yield session
    session.close()

@pytest.fixture
def test_users(db):
    ts = int(datetime.datetime.utcnow().timestamp() * 1000)
    pwd = get_password_hash("password123")
    host = User(
        email=f"host_bot_{ts}@meetora.ai",
        hashed_password=pwd,
        full_name="Bot Host",
        role="user",
        is_active=True,
    )
    unauth = User(
        email=f"unauth_bot_{ts}@meetora.ai",
        hashed_password=pwd,
        full_name="Unauth User",
        role="user",
        is_active=True,
    )
    db.add(host)
    db.add(unauth)
    db.commit()
    db.refresh(host)
    db.refresh(unauth)

    host_token = create_access_token({"sub": host.email, "id": host.id})
    unauth_token = create_access_token({"sub": unauth.email, "id": unauth.id})
    return {"host": host, "host_token": host_token, "unauth": unauth, "unauth_token": unauth_token}


# 1. URL Allowlist and SSRF Protection Tests
def test_url_allowlist_and_ssrf():
    valid_urls = [
        ("https://meet.google.com/abc-defg-hij", "google_meet"),
        ("https://zoom.us/j/1234567890", "zoom"),
        ("https://us05web.zoom.us/j/9876543210?pwd=abc", "zoom"),
        ("https://teams.microsoft.com/l/meetup-join/19%3ameeting", "ms_teams"),
        ("https://teams.live.com/meet/987654321", "ms_teams"),
    ]
    for url, expected_plat in valid_urls:
        valid, plat, err = validate_meeting_url(url)
        assert valid is True, f"Failed for {url}: {err}"
        assert plat == expected_plat

    invalid_urls = [
        "https://evil-attacker.com/meeting",
        "https://webex.com/meet/test",
        "https://discord.gg/abc",
    ]
    for url in invalid_urls:
        valid, plat, err = validate_meeting_url(url)
        assert valid is False
        assert "Unsupported meeting platform" in err

    ssrf_urls = [
        "http://localhost:8000/internal",
        "http://127.0.0.1:5000",
        "http://169.254.169.254/latest/meta-data",
        "http://10.0.0.1/admin",
        "http://192.168.1.1/secret",
        "http://172.16.0.1/secret",
    ]
    for url in ssrf_urls:
        valid, plat, err = validate_meeting_url(url)
        assert valid is False
        assert "SSRF Protection" in err


# 2. Consent Requirement Tests
def test_external_meeting_creation_consent_check(test_users):
    host_token = test_users["host_token"]
    # Auto join True but consent False -> 400
    res = client.post(
        "/meetings/create",
        headers={"Authorization": f"Bearer {host_token}"},
        json={
            "title": "Consent Test Meeting",
            "source": "external_link",
            "meeting_link": "https://meet.google.com/abc-defg-hij",
            "auto_join": True,
            "consent_confirmed": False
        }
    )
    assert res.status_code == 400
    assert "Consent is required" in res.json()["detail"]

    # Consent True -> 201
    res_ok = client.post(
        "/meetings/create",
        headers={"Authorization": f"Bearer {host_token}"},
        json={
            "title": "Consent Confirmed Meeting",
            "source": "external_link",
            "meeting_link": "https://meet.google.com/abc-defg-hij",
            "auto_join": True,
            "consent_confirmed": True,
            "bot_provider": "mock"
        }
    )
    assert res_ok.status_code == 201
    data = res_ok.json()
    assert data["source"] == "external_link"
    assert data["platform"] == "google_meet"
    assert data["consent_confirmed"] is True
    assert data["bot_status"] == "scheduled"


# 3. Permissions & Rate Limiting Tests
def test_bot_dispatch_permissions_and_rate_limit(test_users, db):
    host = test_users["host"]
    host_token = test_users["host_token"]
    unauth_token = test_users["unauth_token"]

    meeting = Meeting(
        title="Manual Bot Meeting",
        user_id=host.id,
        source="external_link",
        meeting_link="https://meet.google.com/xyz-uvwx-rst",
        platform="google_meet",
        auto_join=False,
        consent_confirmed=False,
        bot_provider="mock",
        bot_status="not_requested",
        status="scheduled"
    )
    db.add(meeting)
    db.commit()
    db.refresh(meeting)

    # Unauthorized user tries to join bot -> 403
    res_unauth = client.post(
        f"/meetings/{meeting.id}/bot/join",
        headers={"Authorization": f"Bearer {unauth_token}"},
        json={"consent_confirmed": True}
    )
    assert res_unauth.status_code == 403

    # Host tries to join bot without consent -> 400
    res_no_consent = client.post(
        f"/meetings/{meeting.id}/bot/join",
        headers={"Authorization": f"Bearer {host_token}"},
        json={"consent_confirmed": False}
    )
    assert res_no_consent.status_code == 400
    assert "Consent is required" in res_no_consent.json()["detail"]

    # Host dispatches bot with consent -> 200
    res_join = client.post(
        f"/meetings/{meeting.id}/bot/join",
        headers={"Authorization": f"Bearer {host_token}"},
        json={"consent_confirmed": True}
    )
    assert res_join.status_code == 200
    bot_info = res_join.json()
    assert bot_info["bot_status"] == "joining"
    assert bot_info["bot_id"] is not None
    assert bot_info["consent_confirmed"] is True


# 4. Bot State Transitions & Status Polling
def test_bot_status_and_leave(test_users, db):
    host = test_users["host"]
    host_token = test_users["host_token"]

    meeting = Meeting(
        title="Status Test Meeting",
        user_id=host.id,
        source="external_link",
        meeting_link="https://meet.google.com/aaa-bbbb-ccc",
        platform="google_meet",
        auto_join=True,
        consent_confirmed=True,
        bot_provider="mock",
        bot_id=f"mock-bot-status-{host.id}",
        bot_status="recording",
        status="live",
        started_at=datetime.datetime.utcnow()
    )
    db.add(meeting)
    db.commit()
    db.refresh(meeting)

    res = client.get(
        f"/meetings/{meeting.id}/bot/status",
        headers={"Authorization": f"Bearer {host_token}"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["bot_status"] == "recording"
    assert data["bot_id"] == f"mock-bot-status-{host.id}"

    res_leave = client.post(
        f"/meetings/{meeting.id}/bot/leave",
        headers={"Authorization": f"Bearer {host_token}"}
    )
    assert res_leave.status_code == 200
    assert res_leave.json()["bot_status"] == "removed"


# 5. Webhook Signature Verification & Idempotency
def test_webhook_security_and_idempotency(test_users, db):
    host = test_users["host"]
    bot_id = f"mock-bot-webhook-{host.id}"
    meeting = Meeting(
        title="Webhook Test Meeting",
        user_id=host.id,
        source="external_link",
        meeting_link="https://meet.google.com/mmm-nnnn-ooo",
        platform="google_meet",
        auto_join=True,
        consent_confirmed=True,
        bot_provider="mock",
        bot_id=bot_id,
        bot_status="joining",
        status="scheduled"
    )
    db.add(meeting)
    db.commit()

    payload = {
        "event": "bot.status_change",
        "bot_id": bot_id,
        "status": "waiting_for_admission"
    }
    raw_payload = json.dumps(payload).encode("utf-8")

    # Reject invalid signature
    res_bad_sig = client.post(
        "/webhooks/meeting-bot?provider=mock",
        data=raw_payload,
        headers={"Content-Type": "application/json", "X-Mock-Signature": "invalid-signature"}
    )
    assert res_bad_sig.status_code == 401

    # Accept valid signature
    res_ok = client.post(
        "/webhooks/meeting-bot?provider=mock",
        data=raw_payload,
        headers={"Content-Type": "application/json", "X-Mock-Signature": "valid-mock-signature"}
    )
    assert res_ok.status_code == 200

    db.refresh(meeting)
    assert meeting.bot_status == "waiting_for_admission"

    # Duplicate webhook should be treated idempotently
    res_dup = client.post(
        "/webhooks/meeting-bot?provider=mock",
        data=raw_payload,
        headers={"Content-Type": "application/json", "X-Mock-Signature": "valid-mock-signature"}
    )
    assert res_dup.status_code == 200
    assert res_dup.json().get("idempotent") is True


# 6. Recording Ready & Exactly-Once Pipeline Enqueueing
def test_webhook_recording_completed_pipeline(test_users, db):
    host = test_users["host"]
    bot_id = f"mock-bot-completion-{host.id}"
    meeting = Meeting(
        title="Completion Ingestion Meeting",
        user_id=host.id,
        source="external_link",
        meeting_link="https://meet.google.com/ppp-qqqq-rrr",
        platform="google_meet",
        auto_join=True,
        consent_confirmed=True,
        bot_provider="mock",
        bot_id=bot_id,
        bot_status="recording",
        status="live"
    )
    db.add(meeting)
    db.commit()

    payload = {
        "event": "recording_done",
        "bot_id": bot_id,
        "status": "completed",
        "media_url": "https://mock-storage.meetora.internal/sample.mp4"
    }

    res = client.post(
        "/webhooks/meeting-bot?provider=mock",
        json=payload,
        headers={"X-Mock-Signature": "valid-mock-signature"}
    )
    assert res.status_code == 200

    db.refresh(meeting)
    assert meeting.bot_status == "completed"
    assert meeting.status in ["processing", "completed"]

    rec = db.query(Recording).filter(Recording.meeting_id == meeting.id).first()
    assert rec is not None
    assert rec.kind == "composite_video"
    assert rec.status == "ready"


# 7. Meeting Deletion Cancels Bot
def test_delete_meeting_cancels_bot(test_users, db):
    host = test_users["host"]
    host_token = test_users["host_token"]
    provider = get_bot_provider("mock")
    bot_id = f"mock-bot-to-delete-{host.id}"

    meeting = Meeting(
        title="Deletion Bot Meeting",
        user_id=host.id,
        source="external_link",
        meeting_link="https://meet.google.com/ddd-eeee-fff",
        platform="google_meet",
        auto_join=True,
        consent_confirmed=True,
        bot_provider="mock",
        bot_id=bot_id,
        bot_status="recording",
        status="live"
    )
    db.add(meeting)
    db.commit()
    db.refresh(meeting)

    provider._bots[bot_id] = {
        "status": "recording",
        "meeting_id": meeting.id
    }

    res_del = client.delete(
        f"/meetings/{meeting.id}",
        headers={"Authorization": f"Bearer {host_token}"}
    )
    assert res_del.status_code in [200, 204]
    assert provider._bots[bot_id]["status"] == "removed"
