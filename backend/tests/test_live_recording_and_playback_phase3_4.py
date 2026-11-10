import os
import io
import time
import json
import base64
import hashlib
import jwt
import pytest
from datetime import datetime
from fastapi.testclient import TestClient

from app.main import app
from app.config import settings
from app.database import SessionLocal, Base, engine, ensure_db_schema
from app.models import User, Meeting, Recording, Notification, LiveParticipant
from app.auth import get_password_hash, create_access_token
from app.pipeline_orchestrator import reset_orchestrator_keys
from app.routers.livekit_webhooks import reset_processed_webhook_events

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
    body_hash = hashlib.sha256(payload_str.encode("utf-8")).digest()
    claims = {
        "iss": settings.LIVEKIT_API_KEY,
        "exp": int(time.time()) + 3600,
        "sha256": base64.b64encode(body_hash).decode("utf-8"),
    }
    return jwt.encode(claims, settings.LIVEKIT_API_SECRET, algorithm="HS256")


def test_start_and_stop_recording_permissions(db):
    """Host can start and stop recording; non-host receives 403 Forbidden."""
    host, host_token = make_user(db, "rec_host")
    attendee, att_token = make_user(db, "rec_att")

    # Create live meeting
    m_res = client.post(
        "/meetings/create",
        headers={"Authorization": f"Bearer {host_token}"},
        json={"title": "Sprint Review Recording Test", "is_live": True, "participants": [attendee.email]}
    )
    assert m_res.status_code == 201
    meeting_id = m_res.json()["id"]

    # 1. Non-host tries to start recording -> 403 Forbidden
    non_host_start = client.post(
        f"/meetings/{meeting_id}/live/record/start",
        headers={"Authorization": f"Bearer {att_token}"}
    )
    assert non_host_start.status_code == 403

    # 2. Host starts recording -> 200 OK
    host_start = client.post(
        f"/meetings/{meeting_id}/live/record/start",
        headers={"Authorization": f"Bearer {host_token}"}
    )
    assert host_start.status_code == 200
    start_data = host_start.json()
    assert start_data["recording"] is True
    assert start_data["status"] == "recording"

    # Verify meeting status in DB
    m = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    assert m.live_status == "recording"

    # 3. Non-host tries to stop recording -> 403 Forbidden
    non_host_stop = client.post(
        f"/meetings/{meeting_id}/live/record/stop",
        headers={"Authorization": f"Bearer {att_token}"}
    )
    assert non_host_stop.status_code == 403

    # 4. Host stops recording -> 200 OK
    host_stop = client.post(
        f"/meetings/{meeting_id}/live/record/stop",
        headers={"Authorization": f"Bearer {host_token}"}
    )
    assert host_stop.status_code == 200
    stop_data = host_stop.json()
    assert stop_data["recording"] is False


def test_chunked_recording_upload_and_pipeline(db):
    """In-browser MediaRecorder chunked fallback upload reassembles file and enqueues analysis pipeline."""
    reset_orchestrator_keys()
    host, host_token = make_user(db, "chunk_host")

    m_res = client.post(
        "/meetings/create",
        headers={"Authorization": f"Bearer {host_token}"},
        json={"title": "Quarterly Demo Fallback Recording", "is_live": True}
    )
    meeting_id = m_res.json()["id"]

    # Upload 3 simulated chunks (mock bytes)
    chunk1 = b"RIFF" + b"A" * 1024
    chunk2 = b"B" * 1024
    chunk3 = b"C" * 1024

    # Chunk 0
    res0 = client.post(
        f"/meetings/{meeting_id}/recordings/upload",
        headers={"Authorization": f"Bearer {host_token}"},
        data={"chunk_index": 0, "total_chunks": 3, "kind": "composite_video"},
        files={"chunk": ("chunk0.part", io.BytesIO(chunk1), "application/octet-stream")}
    )
    assert res0.status_code == 200
    assert res0.json()["status"] == "chunk_received"

    # Chunk 1
    res1 = client.post(
        f"/meetings/{meeting_id}/recordings/upload",
        headers={"Authorization": f"Bearer {host_token}"},
        data={"chunk_index": 1, "total_chunks": 3, "kind": "composite_video"},
        files={"chunk": ("chunk1.part", io.BytesIO(chunk2), "application/octet-stream")}
    )
    assert res1.status_code == 200
    assert res1.json()["status"] == "chunk_received"

    # Chunk 2 (Final) -> completes, saves recording, triggers on_recording_ready
    res2 = client.post(
        f"/meetings/{meeting_id}/recordings/upload",
        headers={"Authorization": f"Bearer {host_token}"},
        data={"chunk_index": 2, "total_chunks": 3, "kind": "composite_video"},
        files={"chunk": ("chunk2.part", io.BytesIO(chunk3), "application/octet-stream")}
    )
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["status"] == "completed"
    assert data2["recording_id"] is not None

    # Verify Recording row in database
    rec = db.query(Recording).filter(Recording.id == data2["recording_id"]).first()
    assert rec is not None
    assert rec.status == "ready"
    assert rec.size_bytes > 0
    assert os.path.exists(rec.storage_key)


def test_playback_signed_url_and_streaming(db):
    """Tests generating signed short-lived URL and streaming media with range request check."""
    host, host_token = make_user(db, "stream_host")
    stranger, stranger_token = make_user(db, "stream_stranger")

    m_res = client.post(
        "/meetings/create",
        headers={"Authorization": f"Bearer {host_token}"},
        json={"title": "Private Stream Test", "is_live": True}
    )
    meeting_id = m_res.json()["id"]

    # Create a ready recording
    dummy_file = os.path.join(settings.UPLOAD_DIR, f"test_stream_{meeting_id}.webm")
    with open(dummy_file, "wb") as f:
        f.write(b"SAMPLE_VIDEO_DATA_HEADER_" + b"0" * 4096)

    rec = Recording(
        meeting_id=meeting_id,
        kind="composite_video",
        status="ready",
        storage_key=dummy_file,
        duration=120.0,
        size_bytes=os.path.getsize(dummy_file),
        created_at=datetime.utcnow()
    )
    db.add(rec)
    db.commit()

    # 1. Stranger cannot get playback URL (403)
    bad_res = client.get(
        f"/meetings/{meeting_id}/recordings/playback",
        headers={"Authorization": f"Bearer {stranger_token}"}
    )
    assert bad_res.status_code == 403

    # 2. Host gets signed playback URL
    good_res = client.get(
        f"/meetings/{meeting_id}/recordings/playback",
        headers={"Authorization": f"Bearer {host_token}"}
    )
    assert good_res.status_code == 200
    playback_data = good_res.json()
    stream_url = playback_data["playback_url"]
    assert "token=" in stream_url
    token = stream_url.split("token=")[1]

    # 3. Stream with valid token
    stream_res = client.get(
        f"/meetings/{meeting_id}/recordings/stream?token={token}"
    )
    assert stream_res.status_code in (200, 206)
    assert len(stream_res.content) > 0

    # 4. Stream with Range header (HTTP 206 Partial Content)
    range_res = client.get(
        f"/meetings/{meeting_id}/recordings/stream?token={token}",
        headers={"Range": "bytes=0-100"}
    )
    assert range_res.status_code == 206
    assert "Content-Range" in range_res.headers

    # 5. Invalid / forged token fails 401
    fail_stream = client.get(
        f"/meetings/{meeting_id}/recordings/stream?token=invalid.jwt.token"
    )
    assert fail_stream.status_code == 401


def test_livekit_egress_webhook_events(db):
    """Test LiveKit Egress started and ended webhooks updating recording and triggering orchestrator."""
    reset_processed_webhook_events()
    reset_orchestrator_keys()
    host, host_token = make_user(db, "egress_wh_host")

    m_res = client.post(
        "/meetings/create",
        headers={"Authorization": f"Bearer {host_token}"},
        json={"title": "Egress Webhook Validation", "is_live": True}
    )
    m_data = m_res.json()
    meeting_id = m_data["id"]
    room_name = m_data["room_name"]
    egress_id = f"egress_test_{int(time.time())}"

    # 1. Egress started event
    start_payload = json.dumps({
        "event": "egress_started",
        "id": f"evt_eg_start_{int(time.time())}",
        "room": {"name": room_name},
        "egress_info": {
            "egress_id": egress_id,
            "room_name": room_name,
            "status": "EGRESS_ACTIVE"
        },
        "createdAt": str(int(time.time()))
    })
    token_start = sign_webhook_payload(start_payload)
    res_start = client.post(
        "/webhooks/livekit",
        headers={"Authorization": token_start},
        content=start_payload.encode("utf-8")
    )
    assert res_start.status_code == 200

    # Verify recording record created with status recording
    rec = db.query(Recording).filter(Recording.egress_id == egress_id).first()
    assert rec is not None
    assert rec.status == "recording"

    # 2. Egress ended event
    end_payload = json.dumps({
        "event": "egress_ended",
        "id": f"evt_eg_end_{int(time.time())}",
        "room": {"name": room_name},
        "egress_info": {
            "egress_id": egress_id,
            "room_name": room_name,
            "status": "EGRESS_COMPLETE",
            "duration": 45000000000,  # 45s in nanoseconds
            "file_results": [
                {
                    "filename": f"recordings/{room_name}/composite.mp4",
                    "size": 5242880,
                    "duration": 45000000000
                }
            ]
        },
        "createdAt": str(int(time.time()))
    })
    token_end = sign_webhook_payload(end_payload)
    res_end = client.post(
        "/webhooks/livekit",
        headers={"Authorization": token_end},
        content=end_payload.encode("utf-8")
    )
    assert res_end.status_code == 200

    # Verify recording updated to ready
    db.expire_all()
    rec_done = db.query(Recording).filter(Recording.egress_id == egress_id).first()
    assert rec_done.status == "ready"
    assert rec_done.size_bytes == 5242880
    assert rec_done.duration == 45.0
