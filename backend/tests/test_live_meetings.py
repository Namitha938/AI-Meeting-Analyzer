import json
import time
import base64
import hashlib
import jwt
import pytest
from datetime import datetime
from fastapi.testclient import TestClient

from app.main import app
from app.config import settings
from app.database import SessionLocal, Base, engine, ensure_db_schema
from app.models import User, Meeting, LiveParticipant, Team, TeamMember, MeetingShare
from app.auth import get_password_hash, create_access_token
from app.routers.meetings import reset_join_rate_limiter
from app.routers.livekit_webhooks import reset_processed_webhook_events

# Set local dev credentials for test execution
settings.LIVEKIT_URL = "ws://localhost:7880"
settings.LIVEKIT_API_KEY = "devkey"
settings.LIVEKIT_API_SECRET = "secret"

client = TestClient(app)

@pytest.fixture(scope="module")
def db():
    Base.metadata.create_all(bind=engine)
    ensure_db_schema()
    session = SessionLocal()
    yield session
    session.close()

def make_user(db, prefix: str, role: str = "user") -> tuple[User, str]:
    ts = int(datetime.utcnow().timestamp() * 1000)
    email = f"{prefix}_{ts}@meetora.ai"
    u = User(
        email=email,
        hashed_password=get_password_hash("SecretPass123!"),
        full_name=f"User {prefix.title()}",
        role=role,
        is_active=True,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    token = create_access_token(data={"sub": u.email, "role": u.role, "user_id": u.id})
    return u, token

def sign_webhook_payload(payload_str: str) -> str:
    """Signs a webhook payload with LiveKit HMAC-SHA256 according to official LiveKit webhook spec."""
    body_hash = hashlib.sha256(payload_str.encode("utf-8")).digest()
    claims = {
        "iss": settings.LIVEKIT_API_KEY,
        "exp": int(time.time()) + 3600,
        "sha256": base64.b64encode(body_hash).decode("utf-8"),
    }
    return jwt.encode(claims, settings.LIVEKIT_API_SECRET, algorithm="HS256")


def test_live_meeting_creation(db):
    """Test creating a Live Meeting with record mode, room generation, and scheduled status."""
    host, token = make_user(db, "live_host")
    headers = {"Authorization": f"Bearer {token}"}

    res = client.post(
        "/meetings",
        headers=headers,
        data={
            "title": "Design System Live Review",
            "is_live": "true",
            "record_mode": "audio_video",
            "participants": "Alex, Jordan",
            "tags": "Design, Review",
        }
    )
    assert res.status_code == 201
    data = res.json()
    assert data["title"] == "Design System Live Review"
    assert data["is_live"] is True
    assert data["live_status"] == "scheduled"
    assert data["record_mode"] == "audio_video"
    assert data["room_name"].startswith("meetora-")
    assert data["host_id"] == host.id


def test_live_meeting_token_creation_and_join(db):
    """Test joining a live meeting returns a valid LiveKit token, updates status to live, and saves consent."""
    host, token = make_user(db, "token_host")
    headers = {"Authorization": f"Bearer {token}"}

    create_res = client.post(
        "/meetings/create",
        headers=headers,
        json={
            "title": "Sprint Planning Live",
            "is_live": True,
            "record_mode": "audio_video",
            "participants": [host.email],
        }
    )
    assert create_res.status_code == 201
    m_data = create_res.json()
    meeting_id = m_data["id"]

    # Join with required consent
    join_res = client.post(
        f"/meetings/{meeting_id}/live/join",
        headers=headers,
        json={"display_name": "Host Jordan", "consent": True}
    )
    assert join_res.status_code == 200
    join_data = join_res.json()
    assert "token" in join_data
    assert len(join_data["token"]) > 20
    assert join_data["livekit_url"] == settings.LIVEKIT_URL
    assert join_data["room_name"] == m_data["room_name"]
    assert join_data["is_host"] is True

    # Verify participant consent recorded in DB
    lp = db.query(LiveParticipant).filter(
        LiveParticipant.meeting_id == meeting_id,
        LiveParticipant.user_id == host.id
    ).first()
    assert lp is not None
    assert lp.consent_at is not None
    assert lp.display_name == "Host Jordan"

    # Verify status changed to live
    status_res = client.get(f"/meetings/{meeting_id}/live/status", headers=headers)
    assert status_res.status_code == 200
    s_data = status_res.json()
    assert s_data["live_status"] == "live"
    assert s_data["active_participants_count"] >= 1
    assert s_data["can_join"] is True
    assert s_data["is_host"] is True


def test_live_meeting_consent_required(db):
    """Test that joining is strictly rejected if user has not checked consent."""
    host, token = make_user(db, "consent_host")
    headers = {"Authorization": f"Bearer {token}"}

    create_res = client.post(
        "/meetings/create",
        headers=headers,
        json={"title": "Consent Test Sync", "is_live": True}
    )
    meeting_id = create_res.json()["id"]

    join_res = client.post(
        f"/meetings/{meeting_id}/live/join",
        headers=headers,
        json={"display_name": "No Consent User", "consent": False}
    )
    assert join_res.status_code == 400
    assert "Consent to recording and analysis is required" in join_res.json()["detail"]


def test_live_meeting_permissions(db):
    """Test permission gating: Host, invited users, and editors can join; viewers and strangers are blocked."""
    host, host_token = make_user(db, "perm_host")
    invited, inv_token = make_user(db, "perm_invited")
    stranger, str_token = make_user(db, "perm_stranger")
    viewer, view_token = make_user(db, "perm_viewer")

    # Team setup with editor vs viewer
    team = Team(name=f"Live Team {int(time.time())}", owner_id=host.id)
    db.add(team)
    db.commit()
    db.refresh(team)

    # Add viewer to team
    db.add(TeamMember(team_id=team.id, user_id=viewer.id, role="viewer"))
    db.commit()

    # Create meeting with team and invited list
    create_res = client.post(
        "/meetings/create",
        headers={"Authorization": f"Bearer {host_token}"},
        json={
            "title": "Team Gated Live Meeting",
            "is_live": True,
            "team_id": team.id,
            "participants": [invited.email],
        }
    )
    meeting_id = create_res.json()["id"]

    # 1. Host can join
    r_host = client.post(
        f"/meetings/{meeting_id}/live/join",
        headers={"Authorization": f"Bearer {host_token}"},
        json={"display_name": "Host", "consent": True}
    )
    assert r_host.status_code == 200

    # 2. Explicitly invited participant can join
    r_inv = client.post(
        f"/meetings/{meeting_id}/live/join",
        headers={"Authorization": f"Bearer {inv_token}"},
        json={"display_name": "Invited User", "consent": True}
    )
    assert r_inv.status_code == 200

    # 3. Team viewer is rejected (403)
    r_view = client.post(
        f"/meetings/{meeting_id}/live/join",
        headers={"Authorization": f"Bearer {view_token}"},
        json={"display_name": "Viewer User", "consent": True}
    )
    assert r_view.status_code == 403
    assert "Viewers do not have permission" in r_view.json()["detail"]

    # 4. Uninvited stranger is rejected (403)
    r_str = client.post(
        f"/meetings/{meeting_id}/live/join",
        headers={"Authorization": f"Bearer {str_token}"},
        json={"display_name": "Stranger", "consent": True}
    )
    assert r_str.status_code == 403
    assert "You do not have permission" in r_str.json()["detail"]


def test_live_meeting_max_participants(db):
    """Test max participant capacity enforcement."""
    host, host_token = make_user(db, "maxp_host")
    create_res = client.post(
        "/meetings/create",
        headers={"Authorization": f"Bearer {host_token}"},
        json={"title": "Capacity Live Meeting", "is_live": True}
    )
    meeting_id = create_res.json()["id"]

    # Seed 8 active participants
    max_cap = settings.LIVEKIT_MAX_PARTICIPANTS
    for i in range(max_cap):
        db.add(LiveParticipant(
            meeting_id=meeting_id,
            display_name=f"Participant {i+1}",
            joined_at=datetime.utcnow(),
            consent_at=datetime.utcnow(),
        ))
    db.commit()

    # Attempt to join as 9th participant
    r_join = client.post(
        f"/meetings/{meeting_id}/live/join",
        headers={"Authorization": f"Bearer {host_token}"},
        json={"display_name": "Excess User", "consent": True}
    )
    assert r_join.status_code == 400
    assert "maximum capacity" in r_join.json()["detail"]


def test_live_meeting_rate_limiting(db):
    """Test rate limiting of rapid join requests."""
    reset_join_rate_limiter()
    host, host_token = make_user(db, "rate_host")
    create_res = client.post(
        "/meetings/create",
        headers={"Authorization": f"Bearer {host_token}"},
        json={"title": "Rate Limit Live Meeting", "is_live": True}
    )
    meeting_id = create_res.json()["id"]

    limit = settings.LIVEKIT_JOIN_RATE_LIMIT_PER_MINUTE
    got_429 = False
    for i in range(limit + 5):
        r = client.post(
            f"/meetings/{meeting_id}/live/join",
            headers={"Authorization": f"Bearer {host_token}"},
            json={"display_name": f"Rate Test {i}", "consent": True}
        )
        if r.status_code == 429:
            got_429 = True
            break
    assert got_429 is True
    reset_join_rate_limiter()


def test_live_meeting_end_host_only(db):
    """Test that only host/admin can end a meeting."""
    host, host_token = make_user(db, "end_host")
    other, other_token = make_user(db, "end_other")

    create_res = client.post(
        "/meetings/create",
        headers={"Authorization": f"Bearer {host_token}"},
        json={"title": "End Meeting Test", "is_live": True, "participants": [other.email]}
    )
    meeting_id = create_res.json()["id"]

    # Non-host cannot end
    r_bad = client.post(
        f"/meetings/{meeting_id}/live/end",
        headers={"Authorization": f"Bearer {other_token}"}
    )
    assert r_bad.status_code == 403

    # Host ends meeting
    r_end = client.post(
        f"/meetings/{meeting_id}/live/end",
        headers={"Authorization": f"Bearer {host_token}"}
    )
    assert r_end.status_code == 200
    end_data = r_end.json()
    assert end_data["status"] == "ended"

    # Verify DB status
    m = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    assert m.live_status == "ended"
    assert m.ended_at is not None


def test_livekit_webhook_signature_rejection():
    """Test rejection of unsigned or forged LiveKit webhooks."""
    # 1. Missing Authorization header
    r_missing = client.post("/webhooks/livekit", content=b"{}")
    assert r_missing.status_code == 401

    # 2. Tampered signature / wrong key
    forged_token = jwt.encode({"iss": "fake_key", "exp": int(time.time()) + 300}, "wrong_secret", algorithm="HS256")
    r_forged = client.post(
        "/webhooks/livekit",
        headers={"Authorization": forged_token},
        content=b'{"event": "room_finished"}'
    )
    assert r_forged.status_code == 401


def test_livekit_webhook_events_and_idempotency(db):
    """Test processing valid LiveKit webhooks and verifying duplicate events are idempotent."""
    reset_processed_webhook_events()
    host, host_token = make_user(db, "wh_host")
    create_res = client.post(
        "/meetings/create",
        headers={"Authorization": f"Bearer {host_token}"},
        json={"title": "Webhook Sync", "is_live": True}
    )
    m_data = create_res.json()
    room_name = m_data["room_name"]

    # 1. participant_joined webhook
    payload1 = json.dumps({
        "event": "participant_joined",
        "id": f"evt_join_{int(time.time())}",
        "room": {"name": room_name},
        "participant": {"identity": "user_p1", "name": "Elena Rostova"},
        "createdAt": str(int(time.time())),
    })
    token1 = sign_webhook_payload(payload1)
    res1 = client.post(
        "/webhooks/livekit",
        headers={"Authorization": token1},
        content=payload1.encode("utf-8")
    )
    assert res1.status_code == 200
    assert res1.json()["status"] == "ok"

    # Verify participant added in DB
    p = db.query(LiveParticipant).filter(
        LiveParticipant.display_name == "Elena Rostova"
    ).first()
    assert p is not None

    # 2. Duplicate webhook test (idempotency)
    res_dup = client.post(
        "/webhooks/livekit",
        headers={"Authorization": token1},
        content=payload1.encode("utf-8")
    )
    assert res_dup.status_code == 200
    assert res_dup.json().get("idempotent") is True

    # 3. room_finished webhook
    payload_end = json.dumps({
        "event": "room_finished",
        "id": f"evt_end_{int(time.time())}",
        "room": {"name": room_name},
        "createdAt": str(int(time.time())),
    })
    token_end = sign_webhook_payload(payload_end)
    res_end = client.post(
        "/webhooks/livekit",
        headers={"Authorization": token_end},
        content=payload_end.encode("utf-8")
    )
    assert res_end.status_code == 200

    # Verify meeting status in DB transitioned to ended
    m = db.query(Meeting).filter(Meeting.room_name == room_name).first()
    assert m.live_status == "ended"



def test_live_meeting_passcode_and_locked(db):
    """Test joining a password-protected meeting and locked meeting handling."""
    host, host_token = make_user(db, "passcode_host")
    joiner, joiner_token = make_user(db, "passcode_joiner")
    
    # 1. Create meeting with passcode
    create_res = client.post(
        "/meetings/create",
        headers={"Authorization": f"Bearer {host_token}"},
        json={
            "title": "Confidential Security Review",
            "is_live": True,
            "passcode": "Secret999",
            "participants": [joiner.email]
        }
    )
    assert create_res.status_code == 201
    m_data = create_res.json()
    meeting_id = m_data["id"]
    code = m_data["meeting_code"]
    assert code is not None

    # 2. Join without passcode fails 401
    fail_res = client.post(
        f"/meetings/{meeting_id}/live/join",
        headers={"Authorization": f"Bearer {joiner_token}"},
        json={"display_name": "Joiner", "consent": True}
    )
    assert fail_res.status_code == 401

    # 3. Join with wrong passcode fails 401
    fail_res2 = client.post(
        f"/meetings/{meeting_id}/live/join",
        headers={"Authorization": f"Bearer {joiner_token}"},
        json={"display_name": "Joiner", "consent": True, "passcode": "WrongPass"}
    )
    assert fail_res2.status_code == 401

    # 4. Join with correct passcode succeeds 200
    ok_res = client.post(
        f"/meetings/{meeting_id}/live/join",
        headers={"Authorization": f"Bearer {joiner_token}"},
        json={"display_name": "Joiner", "consent": True, "passcode": "Secret999"}
    )
    assert ok_res.status_code == 200
    assert "token" in ok_res.json()

    # 5. Lock meeting and verify joining is blocked (403)
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    meeting.locked = True
    db.commit()

    locked_res = client.post(
        f"/meetings/{meeting_id}/live/join",
        headers={"Authorization": f"Bearer {joiner_token}"},
        json={"display_name": "Joiner", "consent": True, "passcode": "Secret999"}
    )
    assert locked_res.status_code == 403


def test_join_meeting_by_code(db):
    """Test lookup and joining by human-friendly meeting code."""
    host, host_token = make_user(db, "code_host")
    user, user_token = make_user(db, "code_user")

    create_res = client.post(
        "/meetings/create",
        headers={"Authorization": f"Bearer {host_token}"},
        json={
            "title": "Townhall Live",
            "is_live": True,
            "passcode": "TownPass",
            "participants": [user.email]
        }
    )
    assert create_res.status_code == 201
    m_data = create_res.json()
    code = m_data["meeting_code"]

    # 1. Join by code with correct passcode
    res = client.post(
        "/meetings/join-by-code",
        headers={"Authorization": f"Bearer {user_token}"},
        json={"meeting_code": code, "passcode": "TownPass"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["meeting_id"] == m_data["id"]
    assert data["title"] == "Townhall Live"
    assert data["requires_passcode"] is True

    # 2. Join by non-existent code fails 404
    bad_res = client.post(
        "/meetings/join-by-code",
        headers={"Authorization": f"Bearer {user_token}"},
        json={"meeting_code": "meet-xxx-yyy"}
    )
    assert bad_res.status_code == 404


def test_meeting_chats_persistence_and_privacy(db):
    """Test sending and reading public vs private chats in live meetings."""
    host, host_token = make_user(db, "chat_host")
    user1, user1_token = make_user(db, "chat_u1")
    user2, user2_token = make_user(db, "chat_u2")

    create_res = client.post(
        "/meetings/create",
        headers={"Authorization": f"Bearer {host_token}"},
        json={"title": "Team Chat Room", "is_live": True, "participants": [user1.email, user2.email]}
    )
    meeting_id = create_res.json()["id"]

    # 1. User 1 sends a public chat
    chat1 = client.post(
        f"/meetings/{meeting_id}/chats",
        headers={"Authorization": f"Bearer {user1_token}"},
        json={"message": "Hello everyone!", "is_private": False}
    )
    assert chat1.status_code == 201

    # 2. User 1 sends a private chat to User 2
    chat_priv = client.post(
        f"/meetings/{meeting_id}/chats",
        headers={"Authorization": f"Bearer {user1_token}"},
        json={"message": "Hey User2, private question", "is_private": True, "recipient_id": user2.id}
    )
    assert chat_priv.status_code == 201

    # 3. User 2 reads chats: should see public chat and private chat
    res_u2 = client.get(
        f"/meetings/{meeting_id}/chats",
        headers={"Authorization": f"Bearer {user2_token}"}
    )
    assert res_u2.status_code == 200
    msgs_u2 = [m["message"] for m in res_u2.json()]
    assert "Hello everyone!" in msgs_u2
    assert "Hey User2, private question" in msgs_u2

    # 4. Host reads chats: should see public chat but NOT the private chat between User 1 and User 2
    res_host = client.get(
        f"/meetings/{meeting_id}/chats",
        headers={"Authorization": f"Bearer {host_token}"}
    )
    assert res_host.status_code == 200
    msgs_host = [m["message"] for m in res_host.json()]
    assert "Hello everyone!" in msgs_host
    assert "Hey User2, private question" not in msgs_host

def test_missing_livekit_credentials_returns_503(db, monkeypatch):
    """When LIVEKIT credentials are missing or unconfigured, join returns 503 Service Unavailable."""
    host, host_token = make_user(db, "unconfig_host")
    create_res = client.post(
        "/meetings/create",
        headers={"Authorization": f"Bearer {host_token}"},
        json={"title": "Unconfigured LiveKit Test", "is_live": True}
    )
    meeting_id = create_res.json()["id"]

    # Temporarily clear LiveKit settings
    monkeypatch.setattr(settings, "LIVEKIT_API_KEY", "")

    join_res = client.post(
        f"/meetings/{meeting_id}/live/join",
        headers={"Authorization": f"Bearer {host_token}"},
        json={"display_name": "Host", "consent": True}
    )
    assert join_res.status_code == 503
    assert "Live meetings are not configured" in join_res.json()["detail"]
