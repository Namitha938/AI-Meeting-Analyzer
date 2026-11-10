import logging
from typing import Dict, Any, Set
from datetime import datetime
from fastapi import APIRouter, Request, HTTPException, status, Depends
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..models import Meeting, LiveParticipant, Recording
from livekit.api import TokenVerifier, WebhookReceiver

router = APIRouter(tags=["LiveKit Webhooks"])
logger = logging.getLogger("meetora.livekit_webhooks")

# Set to track processed webhook event IDs for idempotency
_processed_webhook_event_ids: Set[str] = set()

def reset_processed_webhook_events():
    """Helper for testing idempotency."""
    _processed_webhook_event_ids.clear()

@router.post("/webhooks/livekit", status_code=status.HTTP_200_OK)
async def livekit_webhook_handler(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    LiveKit Server Webhook Receiver:
    - Verifies HMAC-SHA256 signature using LiveKit TokenVerifier
    - Handles participant joined/left and room finished events
    - Ensures idempotent processing so duplicate webhooks do not repeat side effects
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header in webhook request"
        )

    body_bytes = await request.body()
    body_str = body_bytes.decode("utf-8")

    receiver = WebhookReceiver(TokenVerifier(settings.LIVEKIT_API_KEY, settings.LIVEKIT_API_SECRET))
    try:
        event = receiver.receive(body_str, auth_header)
    except Exception as e:
        logger.warning(f"LiveKit webhook signature verification failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Webhook signature verification failed: {str(e)}"
        )

    # Check idempotency using event id or fallback composite key
    event_id = getattr(event, "id", None)
    if not event_id:
        room_name = getattr(getattr(event, "room", None), "name", "")
        p_identity = getattr(getattr(event, "participant", None), "identity", "")
        event_name = getattr(event, "event", "unknown")
        created_at = getattr(event, "created_at", "")
        event_id = f"{event_name}_{room_name}_{p_identity}_{created_at}"

    if event_id in _processed_webhook_event_ids:
        logger.info(f"Duplicate webhook event ignored: {event_id}")
        return {"status": "ok", "message": "Duplicate event ignored", "idempotent": True}

    _processed_webhook_event_ids.add(event_id)
    if len(_processed_webhook_event_ids) > 10000:
        _processed_webhook_event_ids.clear()

    event_type = getattr(event, "event", "")
    room = getattr(event, "room", None)
    room_name = getattr(room, "name", None) if room else None
    participant = getattr(event, "participant", None)

    logger.info(f"Received LiveKit webhook event: {event_type} for room: {room_name}")

    if not room_name:
        return {"status": "ok", "message": "No room associated"}

    meeting = db.query(Meeting).filter(Meeting.room_name == room_name).first()
    if not meeting:
        logger.warning(f"No meeting found with room_name: {room_name}")
        return {"status": "ok", "message": f"Room {room_name} not found in meetings"}

    now = datetime.utcnow()

    if event_type == "participant_joined":
        p_identity = getattr(participant, "identity", "") if participant else ""
        p_name = getattr(participant, "name", "") if participant else p_identity or "Participant"
        
        lp = db.query(LiveParticipant).filter(
            LiveParticipant.meeting_id == meeting.id,
            LiveParticipant.display_name == p_name,
            LiveParticipant.left_at.is_(None)
        ).first()
        if not lp:
            lp = LiveParticipant(
                meeting_id=meeting.id,
                display_name=p_name,
                joined_at=now,
                consent_at=now,
            )
            db.add(lp)
        if meeting.live_status == "scheduled":
            meeting.live_status = "live"
            if not meeting.started_at:
                meeting.started_at = now
        db.commit()

    elif event_type == "participant_left":
        p_name = getattr(participant, "name", "") if participant else ""
        if p_name:
            lp = db.query(LiveParticipant).filter(
                LiveParticipant.meeting_id == meeting.id,
                LiveParticipant.display_name == p_name,
                LiveParticipant.left_at.is_(None)
            ).first()
            if lp:
                lp.left_at = now
                db.commit()

    elif event_type in ("room_finished", "room_ended"):
        if meeting.live_status != "completed":
            meeting.live_status = "ended"
        if not meeting.ended_at:
            meeting.ended_at = now
        db.query(LiveParticipant).filter(
            LiveParticipant.meeting_id == meeting.id,
            LiveParticipant.left_at.is_(None)
        ).update({"left_at": now})
        db.commit()

    elif event_type == "egress_started":
        egress_info = getattr(event, "egress_info", None)
        egress_id = getattr(egress_info, "egress_id", "") if egress_info else ""
        meeting.live_status = "recording"
        rec = db.query(Recording).filter(Recording.egress_id == egress_id).first()
        if not rec:
            rec = Recording(
                meeting_id=meeting.id,
                kind="composite_video" if meeting.record_mode == "audio_video" else "composite_audio",
                status="recording",
                egress_id=egress_id,
                created_at=now
            )
            db.add(rec)
        else:
            rec.status = "recording"
        db.commit()

    elif event_type == "egress_ended":
        egress_info = getattr(event, "egress_info", None)
        egress_id = getattr(egress_info, "egress_id", "") if egress_info else ""
        file_results = getattr(egress_info, "file_results", []) or []
        dur_val = getattr(egress_info, "duration", 0.0) or 0.0
        if not dur_val and file_results:
            dur_val = getattr(file_results[0], "duration", 0.0) or 0.0
        if not dur_val and egress_info:
            started = getattr(egress_info, "started_at", 0) or 0
            ended = getattr(egress_info, "ended_at", 0) or 0
            if ended > started:
                dur_val = ended - started
        dur_sec = float(dur_val) / 1e9 if dur_val > 1000000 else float(dur_val)
        
        storage_key = None
        size_bytes = 0
        if file_results:
            f0 = file_results[0]
            storage_key = getattr(f0, "filename", None) or getattr(f0, "location", "")
            size_bytes = int(getattr(f0, "size", 0) or 0)

        rec = db.query(Recording).filter(Recording.egress_id == egress_id).first()
        if not rec:
            rec = Recording(
                meeting_id=meeting.id,
                kind="composite_video",
                status="ready",
                egress_id=egress_id,
                storage_key=storage_key,
                duration=dur_sec,
                size_bytes=size_bytes,
                created_at=now
            )
            db.add(rec)
        else:
            rec.status = "ready"
            rec.duration = dur_sec
            rec.size_bytes = size_bytes
            if storage_key:
                rec.storage_key = storage_key
        db.commit()

        # Enqueue processing pipeline via shared orchestrator
        from app.pipeline_orchestrator import on_recording_ready
        on_recording_ready(
            meeting_id=meeting.id,
            media_set={
                "composite_path": storage_key,
                "storage_key": storage_key,
                "duration": dur_sec
            },
            idempotency_key=f"egress_{egress_id}_{meeting.id}",
            db=db
        )

    return {"status": "ok", "event": event_type, "room": room_name}

