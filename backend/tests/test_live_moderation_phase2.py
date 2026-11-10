import pytest
import os
import datetime
from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal, Base, engine, ensure_db_schema
from app.models import User, Meeting, LiveParticipant, Recording, AuditLog
from app.auth import get_password_hash, create_access_token
from app.config import settings

client = TestClient(app)


@pytest.fixture(scope="module")
def db():
    Base.metadata.create_all(bind=engine)
    ensure_db_schema()
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def test_users(db):
    ts = int(datetime.datetime.utcnow().timestamp() * 1000)
    pwd = get_password_hash("Secret123!")
    host = User(email=f"host_{ts}@meetora.ai", hashed_password=pwd, role="user", is_active=True, full_name="Host User")
    attendee = User(email=f"att_{ts}@meetora.ai", hashed_password=pwd, role="user", is_active=True, full_name="Attendee User")
    viewer = User(email=f"view_{ts}@meetora.ai", hashed_password=pwd, role="user", is_active=True, full_name="Viewer User")
    admin = User(email=f"adm_{ts}@meetora.ai", hashed_password=pwd, role="admin", is_active=True, full_name="Admin User")
    
    db.add_all([host, attendee, viewer, admin])
    db.commit()
    for u in [host, attendee, viewer, admin]:
        db.refresh(u)
    return {"host": host, "attendee": attendee, "viewer": viewer, "admin": admin}


def auth_header(user: User) -> dict:
    token = create_access_token(data={"sub": user.email, "role": user.role})
    return {"Authorization": f"Bearer {token}"}


def test_waiting_room_and_admit_flow(db, test_users):
    """
    Test waiting room: token withheld until admitted.
    Host admits -> token is issued on poll.
    """
    host = test_users["host"]
    attendee = test_users["attendee"]

    meeting = Meeting(
        title="Waiting Room Standup",
        user_id=host.id,
        host_id=host.id,
        is_live=True,
        live_status="live",
        waiting_room_enabled=True,
        participants=[attendee.email]
    )
    db.add(meeting)
    db.commit()
    db.refresh(meeting)

    # 1. Attendee joins: token must be withheld because waiting room is active
    join_res = client.post(
        f"/api/meetings/{meeting.id}/live/join",
        json={"display_name": "Attendee User", "consent": True},
        headers=auth_header(attendee)
    )
    assert join_res.status_code == 200
    join_data = join_res.json()
    assert join_data["status"] == "waiting"
    assert join_data["token"] == ""
    assert "Waiting for host" in join_data["waiting_message"]

    # 2. Host lists participants and sees attendee in waiting status
    part_res = client.get(
        f"/api/meetings/{meeting.id}/live/participants",
        headers=auth_header(host)
    )
    assert part_res.status_code == 200
    parts = part_res.json()
    target_part = next((p for p in parts if p["user_id"] == attendee.id), None)
    assert target_part is not None
    assert target_part["status"] == "waiting"

    # 3. Host admits participant
    admit_res = client.post(
        f"/api/meetings/{meeting.id}/live/moderation/admit",
        json={"participant_id": target_part["id"]},
        headers=auth_header(host)
    )
    assert admit_res.status_code == 200
    assert admit_res.json()["success"] is True

    # 4. Attendee polls waiting-status: now admitted, token is returned
    poll_res = client.get(
        f"/api/meetings/{meeting.id}/live/waiting-status",
        headers=auth_header(attendee)
    )
    assert poll_res.status_code == 200
    poll_data = poll_res.json()
    assert poll_data["status"] == "admitted"
    assert poll_data["token"] != ""


def test_moderation_controls_and_permissions(db, test_users):
    """
    Host mutes, removes, promotes cohost.
    Non-moderator cannot call moderation endpoints.
    Removed participant is blocked from joining.
    """
    host = test_users["host"]
    attendee = test_users["attendee"]
    viewer = test_users["viewer"]

    meeting = Meeting(
        title="Moderation Test Meeting",
        user_id=host.id,
        host_id=host.id,
        is_live=True,
        live_status="live",
        participants=[attendee.email, viewer.email]
    )
    db.add(meeting)
    db.commit()
    db.refresh(meeting)

    # Attendee joins
    client.post(
        f"/api/meetings/{meeting.id}/live/join",
        json={"display_name": "Attendee User", "consent": True},
        headers=auth_header(attendee)
    )

    db.expire_all()
    part = db.query(LiveParticipant).filter(
        LiveParticipant.meeting_id == meeting.id,
        LiveParticipant.user_id == attendee.id
    ).first()
    assert part is not None

    # Viewer (non-host) cannot mute
    unauth_mute = client.post(
        f"/api/meetings/{meeting.id}/live/moderation/mute-participant",
        json={"participant_id": part.id},
        headers=auth_header(viewer)
    )
    assert unauth_mute.status_code == 403

    # Host mutes participant
    mute_res = client.post(
        f"/api/meetings/{meeting.id}/live/moderation/mute-participant",
        json={"participant_id": part.id},
        headers=auth_header(host)
    )
    assert mute_res.status_code == 200
    db.expire_all()
    assert db.query(LiveParticipant).filter(LiveParticipant.id == part.id).first().is_muted is True

    # Host promotes attendee to co-host
    cohost_res = client.post(
        f"/api/meetings/{meeting.id}/live/moderation/make-cohost",
        json={"participant_id": part.id},
        headers=auth_header(host)
    )
    assert cohost_res.status_code == 200
    db.expire_all()
    assert db.query(LiveParticipant).filter(LiveParticipant.id == part.id).first().role == "cohost"

    # Host removes participant
    remove_res = client.post(
        f"/api/meetings/{meeting.id}/live/moderation/remove-participant",
        json={"participant_id": part.id},
        headers=auth_header(host)
    )
    assert remove_res.status_code == 200

    # Removed participant cannot rejoin
    rejoin_res = client.post(
        f"/api/meetings/{meeting.id}/live/join",
        json={"display_name": "Attendee User", "consent": True},
        headers=auth_header(attendee)
    )
    assert rejoin_res.status_code == 403
    assert "removed" in rejoin_res.json()["detail"].lower()


def test_recording_download_and_audit_log(db, test_users, tmp_path):
    """
    Host and admin can download recording media.
    Regular viewer is denied with 403.
    Download and views generate AuditLog entries.
    """
    host = test_users["host"]
    viewer = test_users["viewer"]
    admin = test_users["admin"]

    meeting = Meeting(
        title="Download Permissions Meeting",
        user_id=host.id,
        host_id=host.id,
        is_live=True,
        participants=[viewer.email]
    )
    db.add(meeting)
    db.commit()
    db.refresh(meeting)

    # Create dummy recording file on disk
    rec_file = tmp_path / "test_session.mp4"
    rec_file.write_bytes(b"TEST_VIDEO_BYTES_123456789")

    rec = Recording(
        meeting_id=meeting.id,
        kind="composite_video",
        storage_key=str(rec_file),
        status="ready",
        duration=42.0,
        size_bytes=len(b"TEST_VIDEO_BYTES_123456789")
    )
    db.add(rec)
    db.commit()

    # Viewer requests playback: allowed, writes RECORDING_VIEW audit log
    pb_res = client.get(
        f"/api/meetings/{meeting.id}/recordings/playback",
        headers=auth_header(viewer)
    )
    assert pb_res.status_code == 200
    db.expire_all()
    view_log = db.query(AuditLog).filter(
        AuditLog.action == "RECORDING_VIEW",
        AuditLog.user_id == viewer.id
    ).first()
    assert view_log is not None

    # Viewer attempts download: 403 Forbidden
    viewer_dl = client.get(
        f"/api/meetings/{meeting.id}/recordings/download",
        headers=auth_header(viewer)
    )
    assert viewer_dl.status_code == 403

    # Host downloads: 200 OK
    host_dl = client.get(
        f"/api/meetings/{meeting.id}/recordings/download",
        headers=auth_header(host)
    )
    assert host_dl.status_code == 200
    assert host_dl.content == b"TEST_VIDEO_BYTES_123456789"

    # Admin downloads: 200 OK
    admin_dl = client.get(
        f"/api/meetings/{meeting.id}/recordings/download",
        headers=auth_header(admin)
    )
    assert admin_dl.status_code == 200

    db.expire_all()
    dl_log = db.query(AuditLog).filter(
        AuditLog.action == "RECORDING_DOWNLOAD",
        AuditLog.user_id == host.id
    ).first()
    assert dl_log is not None


def test_retention_auto_cleanup_task(db, tmp_path):
    """
    Retention cleanup task deletes media files older than retention days,
    updates recording status to expired, but keeps meeting and transcripts.
    """
    from app.celery_app import cleanup_expired_recordings_task

    m = Meeting(title="Old Meeting", user_id=1, status="completed")
    db.add(m)
    db.commit()
    db.refresh(m)

    old_file = tmp_path / "old_video.mp4"
    old_file.write_bytes(b"OLD_MEDIA")

    # Recording created 45 days ago
    old_date = datetime.datetime.utcnow() - datetime.timedelta(days=45)
    rec = Recording(
        meeting_id=m.id,
        kind="composite_video",
        storage_key=str(old_file),
        status="ready",
        created_at=old_date
    )
    db.add(rec)
    db.commit()

    result = cleanup_expired_recordings_task(retention_days=30)
    assert result["purged_count"] >= 1
    assert not os.path.exists(str(old_file))

    db.expire_all()
    updated_rec = db.query(Recording).filter(Recording.id == rec.id).first()
    assert updated_rec.status == "expired"
