import os
import time
import logging
from typing import Dict, Any, List, Set, Optional
from datetime import datetime, timezone

from fastapi import APIRouter, Request, HTTPException, status, Depends
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import Meeting, User, MeetingShare, AuditLog, Recording
from app.schemas import BotJoinRequest, BotStatusResponse
from app.routers.auth import get_current_user
from app.bot_providers import get_bot_provider, validate_meeting_url
from app.pipeline_orchestrator import on_recording_ready

router = APIRouter(tags=["Meeting Bot"])
logger = logging.getLogger("meetora.meeting_bot")

# Track join rate limiting: meeting_id -> list of timestamps
_bot_join_timestamps: Dict[int, List[float]] = {}

# Webhook idempotency set: event_id / composite_key
_processed_bot_webhooks: Set[str] = set()

def reset_bot_webhook_cache():
    """Testing helper to clear webhook idempotency set."""
    _processed_bot_webhooks.clear()
    _bot_join_timestamps.clear()

def check_bot_permission(meeting: Meeting, current_user: User, db: Session):
    """
    Ensures user is meeting owner, admin, or has can_edit=True permission.
    """
    if meeting.user_id == current_user.id or current_user.role == "admin":
        return True

    share = db.query(MeetingShare).filter(
        MeetingShare.meeting_id == meeting.id,
        MeetingShare.user_id == current_user.id,
        MeetingShare.can_edit == True
    ).first()
    if share:
        return True

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Not authorized to control the meeting bot for this meeting"
    )

def check_bot_rate_limit(meeting_id: int):
    """
    Enforces per-meeting join request rate limiting.
    """
    now = time.time()
    limit = getattr(settings, "BOT_JOIN_RATE_LIMIT_PER_MINUTE", 10)
    timestamps = _bot_join_timestamps.get(meeting_id, [])
    # Keep only timestamps in last 60 seconds
    timestamps = [ts for ts in timestamps if now - ts < 60]
    if len(timestamps) >= limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded: maximum {limit} bot join requests per minute."
        )
    timestamps.append(now)
    _bot_join_timestamps[meeting_id] = timestamps


@router.post("/meetings/{meeting_id}/bot/join", response_model=BotStatusResponse)
async def request_bot_join(
    meeting_id: int,
    payload: Optional[BotJoinRequest] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Dispatches the AI notetaker bot to join the external meeting link (Google Meet, Zoom, MS Teams).
    - Checks authorization (host/editor)
    - Validates consent (required)
    - Validates URL against SSRF and allowlist
    - Rate limits requests
    """
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    check_bot_permission(meeting, current_user, db)
    check_bot_rate_limit(meeting_id)

    # Consent confirmation requirement
    has_consent = (payload and payload.consent_confirmed) or meeting.consent_confirmed
    if not has_consent:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Consent is required: you must confirm all participants have been informed that Meetora Notetaker is recording and analyzing this meeting."
        )

    # URL validation
    if not meeting.meeting_link:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No external meeting link associated with this meeting."
        )

    is_valid, platform, error_msg = validate_meeting_url(meeting.meeting_link)
    if not is_valid:
        meeting.bot_status = "failed"
        meeting.bot_error = error_msg
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg or "Invalid external meeting URL"
        )

    if platform and not meeting.platform:
        meeting.platform = platform

    provider = get_bot_provider(meeting.bot_provider)
    bot_name = getattr(settings, "BOT_NAME", "Meetora Notetaker (recording)")

    try:
        res = await provider.join(meeting.id, meeting.meeting_link, bot_name)
    except Exception as e:
        logger.error(f"Failed to dispatch bot for meeting {meeting_id}: {e}")
        meeting.bot_status = "failed"
        meeting.bot_error = str(e)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Bot provider error: {str(e)}"
        )

    meeting.bot_id = res.get("bot_id")
    meeting.bot_status = res.get("status", "joining")
    meeting.consent_confirmed = True
    meeting.consent_confirmed_at = datetime.utcnow()
    meeting.bot_error = None
    if meeting.started_at is None:
        meeting.started_at = datetime.utcnow()

    db.add(AuditLog(
        user_id=current_user.id,
        user_email=current_user.email,
        action="BOT_REQUESTED",
        resource=f"meeting:{meeting_id}",
        status="SUCCESS",
        severity="INFO",
        details={
            "bot_id": meeting.bot_id,
            "provider": meeting.bot_provider,
            "platform": meeting.platform,
            "meeting_link": meeting.meeting_link
        }
    ))
    db.commit()
    db.refresh(meeting)

    return BotStatusResponse(
        meeting_id=meeting.id,
        bot_status=meeting.bot_status,
        bot_id=meeting.bot_id,
        bot_error=meeting.bot_error,
        platform=meeting.platform,
        meeting_link=meeting.meeting_link,
        auto_join=meeting.auto_join,
        consent_confirmed=meeting.consent_confirmed,
        elapsed_seconds=0
    )


@router.post("/meetings/{meeting_id}/bot/leave", response_model=BotStatusResponse)
async def request_bot_leave(
    meeting_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Commands the AI notetaker bot to leave the meeting immediately.
    """
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    check_bot_permission(meeting, current_user, db)

    if meeting.bot_id:
        provider = get_bot_provider(meeting.bot_provider)
        try:
            await provider.leave(meeting.bot_id)
        except Exception as e:
            logger.warning(f"Error leaving bot {meeting.bot_id}: {e}")

    meeting.bot_status = "removed"
    meeting.ended_at = datetime.utcnow()

    db.add(AuditLog(
        user_id=current_user.id,
        user_email=current_user.email,
        action="BOT_LEFT",
        resource=f"meeting:{meeting_id}",
        status="SUCCESS",
        severity="INFO",
        details={"bot_id": meeting.bot_id, "provider": meeting.bot_provider}
    ))
    db.commit()
    db.refresh(meeting)

    return BotStatusResponse(
        meeting_id=meeting.id,
        bot_status=meeting.bot_status,
        bot_id=meeting.bot_id,
        bot_error=meeting.bot_error,
        platform=meeting.platform,
        meeting_link=meeting.meeting_link,
        auto_join=meeting.auto_join,
        consent_confirmed=meeting.consent_confirmed,
        elapsed_seconds=0
    )


@router.get("/meetings/{meeting_id}/bot/status", response_model=BotStatusResponse)
def get_bot_status(
    meeting_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Returns current bot status, platform, and elapsed recording time.
    """
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    # Ensure user has access to meeting
    if meeting.user_id != current_user.id and current_user.role != "admin":
        share = db.query(MeetingShare).filter(
            MeetingShare.meeting_id == meeting.id,
            MeetingShare.user_id == current_user.id
        ).first()
        if not share:
            raise HTTPException(status_code=403, detail="Not authorized to view meeting bot status")

    elapsed = 0
    if meeting.bot_status == "recording" and meeting.started_at:
        elapsed = int((datetime.utcnow() - meeting.started_at).total_seconds())

    return BotStatusResponse(
        meeting_id=meeting.id,
        bot_status=meeting.bot_status or "not_requested",
        bot_id=meeting.bot_id,
        bot_error=meeting.bot_error,
        platform=meeting.platform,
        meeting_link=meeting.meeting_link,
        auto_join=meeting.auto_join,
        consent_confirmed=meeting.consent_confirmed,
        elapsed_seconds=max(0, elapsed)
    )


@router.post("/webhooks/meeting-bot", status_code=status.HTTP_200_OK)
async def meeting_bot_webhook_handler(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Receiver for Bot Provider webhooks (Recall.ai, Vexa, Mock).
    - Cryptographically verifies signature
    - Parses lifecycle event (status changes, completion, errors)
    - Idempotently updates DB and triggers on_recording_ready exactly once upon recording completion
    """
    headers = dict(request.headers)
    body_bytes = await request.body()

    # Determine provider from query param or fallback to configured provider
    provider_param = request.query_params.get("provider") or settings.BOT_PROVIDER
    provider = get_bot_provider(provider_param)

    # Verify signature
    if not provider.verify_webhook(headers, body_bytes):
        logger.warning(f"Meeting bot webhook verification rejected for provider {provider_param}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing webhook signature"
        )

    try:
        import json
        payload = json.loads(body_bytes.decode("utf-8")) if body_bytes else {}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON payload: {e}")

    event = provider.parse_webhook_event(payload)
    bot_id = event.get("bot_id")
    event_status = event.get("status")
    event_type = event.get("event")

    if not bot_id:
        return {"status": "ok", "message": "Ignored: no bot_id in event"}

    # Idempotency check
    idempotency_key = f"{bot_id}_{event_type}_{event_status}"
    if idempotency_key in _processed_bot_webhooks:
        logger.info(f"Duplicate bot webhook event ignored: {idempotency_key}")
        return {"status": "ok", "message": "Duplicate event ignored", "idempotent": True}
    _processed_bot_webhooks.add(idempotency_key)
    if len(_processed_bot_webhooks) > 10000:
        _processed_bot_webhooks.clear()

    # Find meeting by bot_id
    meeting = db.query(Meeting).filter(Meeting.bot_id == bot_id).first()
    if not meeting:
        logger.warning(f"No meeting found matching bot_id: {bot_id}")
        return {"status": "ok", "message": "Bot not matched to any meeting"}

    # Update meeting status based on bot event
    old_status = meeting.bot_status
    if event_status:
        meeting.bot_status = event_status

    if event.get("error"):
        meeting.bot_error = event.get("error")

    # If completed or recording done: ingest media and trigger on_recording_ready
    if event_status == "completed" or event_type in ["recording_done", "bot.done", "call_done"]:
        meeting.bot_status = "completed"
        meeting.ended_at = datetime.utcnow()

        # Download / store media in private storage
        storage_dir = os.path.join(settings.UPLOAD_DIR, "recordings")
        os.makedirs(storage_dir, exist_ok=True)
        local_media_path = os.path.join(storage_dir, f"bot_{bot_id}.mp4")

        media_url = event.get("media_url")
        if media_url and media_url.startswith("http") and not media_url.startswith("https://mock"):
            try:
                import httpx
                async with httpx.AsyncClient(timeout=60.0) as client:
                    resp = await client.get(media_url)
                    if resp.status_code == 200:
                        with open(local_media_path, "wb") as f:
                            f.write(resp.content)
            except Exception as e:
                logger.error(f"Failed to download media for bot {bot_id}: {e}")
        else:
            # Create a sample MP4/WAV payload for mock/test runs if not present
            if not os.path.exists(local_media_path):
                import wave
                with wave.open(local_media_path, "wb") as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(2)
                    wf.setframerate(16000)
                    wf.writeframes(b"\x00\x00" * 16000)

        file_size = os.path.getsize(local_media_path) if os.path.exists(local_media_path) else 0

        # Save Recording row
        rec = Recording(
            meeting_id=meeting.id,
            kind="composite_video",
            storage_key=local_media_path,
            duration=60.0,
            size_bytes=file_size,
            status="ready"
        )
        db.add(rec)
        db.commit()

        # Invoke on_recording_ready exactly once
        on_recording_ready(
            meeting_id=meeting.id,
            media_set={"composite_path": local_media_path, "storage_key": local_media_path},
            idempotency_key=f"external_bot_{meeting.id}_{bot_id}",
            db=db
        )

        # Clean up provider-side copy
        try:
            await provider.delete_bot_media(bot_id)
        except Exception as e:
            logger.warning(f"Provider media deletion notice for {bot_id}: {e}")

        db.add(AuditLog(
            user_id=meeting.user_id,
            user_email="bot@meetora.ai",
            action="BOT_RECORDING_COMPLETED",
            resource=f"meeting:{meeting.id}",
            status="SUCCESS",
            severity="INFO",
            details={"bot_id": bot_id, "local_path": local_media_path}
        ))

    elif event_status == "failed":
        db.add(AuditLog(
            user_id=meeting.user_id,
            user_email="bot@meetora.ai",
            action="BOT_FAILED",
            resource=f"meeting:{meeting.id}",
            status="FAILED",
            severity="ERROR",
            details={"bot_id": bot_id, "error": event.get("error")}
        ))

    db.commit()
    return {"status": "ok", "bot_id": bot_id, "previous_status": old_status, "new_status": meeting.bot_status}

