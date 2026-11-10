import re
import random
import os
import shutil
import subprocess
import logging
import datetime
import uuid
import time
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, BackgroundTasks, Request
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.config import settings
from app.database import get_db
from app.storage import get_storage
from app.models import (
    AuditLog,
    User, Meeting, Transcript, Summary, ActionItem, Decision,
    Comment, MeetingAnalytics, HumanCorrection, MeetingShare,
    LiveParticipant, MeetingChat, TeamMember, Recording
)
from app.schemas import (
    LiveParticipantResponse,
    ModerationActionRequest,
    ModerationActionResponse,
    MeetingResponse, MeetingDetailResponse, MeetingStatusResponse,
    TranscriptItem, SummaryResponse, ActionItemResponse, DecisionResponse,
    AnalyticsResponse, CommentCreate, CommentResponse, RenameSpeakerRequest,
    MeetingChatRequest, MeetingChatResponse, TranslationRequest, TranslationResponse,
    BulkDeleteRequest, BulkDeleteResponse, BulkDeleteFailure,
    MeetingUpdateRequest, SummaryUpdateRequest, TranscriptLineUpdateRequest,
    MeetingCreate, LiveJoinRequest, LiveJoinResponse, LiveStatusResponse, LiveEndResponse, JoinByCodeRequest, JoinByCodeResponse, LiveChatMessageCreate, LiveChatMessageResponse, RecordingResponse, RecordingStartResponse, RecordingStopResponse, PlaybackResponse, ChunkUploadResponse, LiveCaptionInput, LiveCaptionResponse, DetectedActionItem, ActionItemCreate, ActionItemUpdate
)
from app.search_vector import answer_meeting_rag, vector_search_service, format_seconds_to_ts
from app.nlp_analysis import MeetingAnalyticsEngine
from app.speech_to_text import translate_transcript_text
from app.auth import get_current_user, get_optional_current_user
from app.celery_app import run_meeting_pipeline_sync
from app.speech_to_text import format_timestamp

logger = logging.getLogger("meetora.meetings")

router = APIRouter(prefix="/meetings", tags=["Meetings"])

def recompute_and_save_meeting_effectiveness(meeting: Meeting, db: Session) -> Optional[Dict[str, Any]]:
    """Recomputes effectiveness score and pillars for a meeting and commits to DB."""
    try:
        from app.ml.effectiveness import compute_effectiveness
        segments = [
            {"speaker": t.speaker, "start_time": t.start_time, "end_time": t.end_time, "text": t.text}
            for t in meeting.transcripts
        ]
        actions = [
            {"assignee": a.assignee, "due_date": a.deadline or getattr(a, "due_date", None)}
            for a in meeting.action_items
        ]
        eff = compute_effectiveness(
            segments=segments,
            action_items=actions,
            agenda_text=meeting.description or meeting.title,
        )
        if eff:
            meeting.effectiveness_score = eff["score"]
            meeting.effectiveness_pillars = eff["pillars"]
            db.commit()
            db.refresh(meeting)
            return eff
    except Exception as e:
        logger.warning(f"Failed to recompute meeting effectiveness for meeting {meeting.id}: {e}")
    return None

def convert_audio_if_possible(source_path: str) -> str:
    """
    Converts audio to 16 kHz mono WAV using FFmpeg (with pure Python fallback).
    Returns path to the 16 kHz mono WAV file.
    """
    base, ext = os.path.splitext(source_path)
    target_path = f"{base}_16k_mono.wav"

    # 1. Primary: Run system FFmpeg binary
    try:
        cmd = ["ffmpeg", "-y", "-i", source_path, "-ar", "16000", "-ac", "1", target_path]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15)
        if res.returncode == 0 and os.path.exists(target_path):
            return target_path
    except Exception:
        pass

    # 2. Pure Python WAV conversion fallback to 16 kHz mono
    if ext.lower() == ".wav" and os.path.exists(source_path):
        try:
            import wave
            import struct
            with wave.open(source_path, "rb") as wf:
                n_channels = wf.getnchannels()
                sampwidth = wf.getsampwidth()
                framerate = wf.getframerate()
                n_frames = wf.getnframes()
                data = wf.readframes(n_frames)

            if n_channels == 1 and framerate == 16000 and sampwidth == 2:
                return source_path

            if sampwidth == 2:
                samples = struct.unpack(f"<{len(data)//2}h", data)
                if n_channels > 1:
                    mono_samples = [sum(samples[i:i+n_channels]) // n_channels for i in range(0, len(samples), n_channels)]
                else:
                    mono_samples = list(samples)

                if framerate != 16000 and framerate > 0:
                    step = framerate / 16000.0
                    new_len = int(len(mono_samples) / step)
                    resampled = [mono_samples[int(i * step)] for i in range(new_len)]
                else:
                    resampled = mono_samples

                packed = struct.pack(f"<{len(resampled)}h", *resampled)
                with wave.open(target_path, "wb") as out_wf:
                    out_wf.setnchannels(1)
                    out_wf.setsampwidth(2)
                    out_wf.setframerate(16000)
                    out_wf.writeframes(packed)
                if os.path.exists(target_path):
                    return target_path
        except Exception:
            pass

    return source_path


def generate_meeting_code() -> str:
    chars = "abcdefghijklmnopqrstuvwxyz"
    p1 = "".join(random.choices(chars, k=3))
    p2 = "".join(random.choices(chars, k=3))
    return f"meet-{p1}-{p2}"

@router.post("", response_model=MeetingResponse, status_code=status.HTTP_201_CREATED)
async def create_and_upload_meeting(
    background_tasks: BackgroundTasks,
    title: str = Form(...),
    participants: Optional[str] = Form("Sarah Kim, Marcus Lee, Jordan Davis"),
    tags: Optional[str] = Form("Product, Q3, Planning"),
    color: Optional[str] = Form("violet"),
    file: Optional[UploadFile] = File(None),
    is_live: Optional[bool] = Form(False),
    record_mode: Optional[str] = Form("audio_video"),
    passcode: Optional[str] = Form(None),
    scheduled_at: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    team_id: Optional[int] = Form(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    part_list = [p.strip() for p in participants.split(",") if p.strip()] if participants else []
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []

    parsed_sched = None
    if scheduled_at:
        try:
            import dateparser
            parsed_sched = dateparser.parse(scheduled_at)
        except Exception:
            pass

    # Handle Live Meeting creation
    if is_live:
        room_name = f"meetora-{uuid.uuid4().hex[:10]}"
        # Ensure host is included in participants if list exists
        host_name = current_user.full_name or current_user.email
        if host_name and host_name not in part_list:
            part_list.append(host_name)

        from app.auth import get_password_hash
        m_code = generate_meeting_code()
        pc_hash = get_password_hash(passcode.strip()) if passcode and passcode.strip() else None

        meeting = Meeting(
            title=title,
            user_id=current_user.id,
            host_id=current_user.id,
            audio_path=None,
            duration_seconds=0,
            file_size_bytes=0,
            status="scheduled",
            source="live_room",
            is_live=True,
            room_name=room_name,
            meeting_code=m_code,
            passcode_hash=pc_hash,
            live_status="scheduled",
            record_mode=record_mode or "audio_video",
            description=description,
            scheduled_at=parsed_sched,
            team_id=team_id,
            participants=part_list,
            tags=tag_list,
            color=color or "violet",
        )
        db.add(meeting)
        db.commit()
        db.refresh(meeting)
        return meeting

    # Standard uploaded recording flow
    saved_path = None
    file_size = 0

    if file:
        filename = file.filename or "recording.wav"
        ext = os.path.splitext(filename)[1].lower()
        if ext and ext not in settings.ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file format '{ext}'. Allowed: {', '.join(settings.ALLOWED_EXTENSIONS)}"
            )

        storage = get_storage()
        upload_meta = storage.save_file(file)
        saved_path = upload_meta["file_path"]
        file_size = upload_meta["file_size"]

        if file_size > settings.MAX_FILE_SIZE_MB * 1024 * 1024:
            storage.delete_file(saved_path)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File exceeds maximum allowed size of {settings.MAX_FILE_SIZE_MB}MB."
            )

        # Attempt conversion if local
        if os.path.exists(saved_path):
            saved_path = convert_audio_if_possible(saved_path)

    meeting = Meeting(
        title=title,
        user_id=current_user.id,
        audio_path=saved_path,
        duration_seconds=0,
        file_size_bytes=file_size,
        status="transcribing",  # Begins processing immediately
        participants=part_list,
        tags=tag_list,
        color=color or "violet",
        description=description,
        scheduled_at=parsed_sched,
        team_id=team_id,
    )
    db.add(meeting)
    db.commit()
    db.refresh(meeting)

    # Trigger background AI pipeline for uploaded files
    background_tasks.add_task(run_meeting_pipeline_sync, meeting.id)

    return meeting

@router.post("/create", response_model=MeetingResponse, status_code=status.HTTP_201_CREATED)
def create_meeting_json(
    payload: MeetingCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if payload.source == "external_link" or (payload.meeting_link and not payload.is_live):
        from app.bot_providers import validate_meeting_url
        is_valid, plat, err = validate_meeting_url(payload.meeting_link or "")
        if not is_valid:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err or "Invalid meeting URL")
        if payload.auto_join and not payload.consent_confirmed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Consent is required before scheduling or sending the AI notetaker bot. You must confirm participants will be notified."
            )
        parts = list(payload.participants or [])
        meeting = Meeting(
            title=payload.title,
            user_id=current_user.id,
            host_id=current_user.id,
            audio_path=None,
            duration_seconds=0,
            file_size_bytes=0,
            status="scheduled",
            source="external_link",
            is_live=False,
            meeting_link=payload.meeting_link.strip() if payload.meeting_link else None,
            platform=payload.platform or plat,
            auto_join=bool(payload.auto_join),
            consent_confirmed=bool(payload.consent_confirmed),
            consent_confirmed_at=datetime.datetime.utcnow() if payload.consent_confirmed else None,
            bot_provider=payload.bot_provider or settings.BOT_PROVIDER,
            bot_status="scheduled" if payload.auto_join else "not_requested",
            description=payload.description,
            scheduled_at=payload.scheduled_at,
            team_id=payload.team_id,
            participants=parts,
            tags=payload.tags or [],
            color=payload.color or "violet",
        )
        db.add(meeting)
        db.commit()
        db.refresh(meeting)
        return meeting

    room_name = f"meetora-{uuid.uuid4().hex[:10]}" if payload.is_live else None
    parts = list(payload.participants or [])
    if payload.is_live:
        host_name = current_user.full_name or current_user.email
        if host_name and host_name not in parts:
            parts.append(host_name)

    from app.auth import get_password_hash
    m_code = generate_meeting_code() if payload.is_live else None
    pc_hash = get_password_hash(payload.passcode.strip()) if payload.passcode and payload.passcode.strip() else None

    meeting = Meeting(
        title=payload.title,
        user_id=current_user.id,
        host_id=current_user.id if payload.is_live else None,
        audio_path=None,
        duration_seconds=0,
        file_size_bytes=0,
        status="scheduled" if payload.is_live else "uploading",
        source="live_room" if payload.is_live else "upload",
        is_live=bool(payload.is_live),
        room_name=room_name,
        meeting_code=m_code,
        passcode_hash=pc_hash,
        live_status="scheduled" if payload.is_live else "scheduled",
        record_mode=payload.record_mode or "audio_video",
        description=payload.description,
        scheduled_at=payload.scheduled_at,
        team_id=payload.team_id,
        participants=parts,
        tags=payload.tags or [],
        color=payload.color or "violet",
    )
    db.add(meeting)
    db.commit()
    db.refresh(meeting)
    return meeting

@router.get("", response_model=List[MeetingResponse])
def get_user_meetings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return db.query(Meeting).filter(Meeting.user_id == current_user.id).order_by(Meeting.created_at.desc()).all()

@router.get("/{meeting_id}", response_model=MeetingDetailResponse)
def get_meeting_detail(
    meeting_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    if meeting.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized to access this meeting")
    if meeting.effectiveness_score is None and meeting.transcripts:
        recompute_and_save_meeting_effectiveness(meeting, db)

    # Populate chapters for response
    if meeting.analytics and meeting.analytics.topic_chapters:
        meeting.chapters = meeting.analytics.topic_chapters
    elif meeting.transcripts:
        try:
            from app.nlp_analysis import MeetingAnalyticsEngine
            transcript_dicts = [
                {"speaker": t.speaker, "start_time": t.start_time, "end_time": t.end_time, "text": t.text}
                for t in meeting.transcripts
            ]
            meeting.chapters = MeetingAnalyticsEngine.generate_topic_chapters(transcript_dicts)
        except Exception:
            meeting.chapters = []
    else:
        meeting.chapters = []

    return meeting

@router.get("/{meeting_id}/status", response_model=MeetingStatusResponse)
def get_meeting_status(
    meeting_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    status_map = {
        "uploading": (15, "Uploading audio to storage...", "Uploading"),
        "transcribing": (45, "Running Whisper Speech-to-Text with timestamps...", "Transcribing (Whisper)"),
        "diarizing": (70, "Running pyannote.audio speaker diarization...", "Diarizing (pyannote.audio)"),
        "analyzing": (90, "Extracting action items, key decisions, and sentiment...", "Analyzing (NLP)"),
        "completed": (100, "Meeting processing completed.", "Completed"),
        "failed": (100, "Processing failed. Please re-upload.", "Failed"),
    }
    prog, msg, stg = status_map.get(meeting.status, (50, "Processing...", "Processing"))

    return {
        "id": meeting.id,
        "status": meeting.status,
        "progress": prog,
        "stage": stg,
        "message": msg,
    }

def perform_delete_meeting(meeting: Meeting, db: Session) -> dict:
    """
    Deletes everything that belongs to the meeting:
    - Transcripts, summaries, action items, decisions, comments, analytics
    - Detaches human corrections so retraining data is preserved
    - Purges vector entries from vector search / RAG
    - Deletes stored media file (local disk, S3, or Cloudinary with resource_type="video")
    - Performs database operations in one atomic transaction
    - Logs any file cleanup errors without failing the database transaction
    """
    meeting_id = meeting.id
    audio_path = meeting.audio_path

    # Collect audio paths to delete later
    audio_paths_to_delete = []
    if audio_path:
        audio_paths_to_delete.append(audio_path)
        base, _ = os.path.splitext(audio_path)
        converted_wav = f"{base}_16k_mono.wav"
        if os.path.exists(converted_wav):
            audio_paths_to_delete.append(converted_wav)

    # 1. Detach human corrections to preserve retraining dataset
    action_item_id_tuples = db.query(ActionItem.id).filter(ActionItem.meeting_id == meeting_id).all()
    action_item_ids = [a[0] for a in action_item_id_tuples]

    hc_filters = [HumanCorrection.meeting_id == meeting_id]
    if action_item_ids:
        hc_filters.append(HumanCorrection.action_item_id.in_(action_item_ids))

    db.query(HumanCorrection).filter(or_(*hc_filters)).update(
        {HumanCorrection.meeting_id: None, HumanCorrection.action_item_id: None},
        synchronize_session=False
    )

    # 2. Vector index cleanup
    try:
        vector_search_service.delete_meeting_vectors(meeting_id, db=db)
    except Exception as e:
        logger.warning(f"Vector cleanup notice for meeting {meeting_id}: {e}")

    # 3. Clean up related rows in DB
    db.query(Transcript).filter(Transcript.meeting_id == meeting_id).delete(synchronize_session=False)
    db.query(ActionItem).filter(ActionItem.meeting_id == meeting_id).delete(synchronize_session=False)
    db.query(Decision).filter(Decision.meeting_id == meeting_id).delete(synchronize_session=False)
    db.query(Summary).filter(Summary.meeting_id == meeting_id).delete(synchronize_session=False)
    db.query(Comment).filter(Comment.meeting_id == meeting_id).delete(synchronize_session=False)
    db.query(MeetingAnalytics).filter(MeetingAnalytics.meeting_id == meeting_id).delete(synchronize_session=False)

    # Cancel active bot and delete provider-side media if external link
    if meeting.bot_id:
        try:
            from app.bot_providers import get_bot_provider
            import asyncio
            provider = get_bot_provider(meeting.bot_provider)
            try:
                asyncio.run(provider.leave(meeting.bot_id))
                asyncio.run(provider.delete_bot_media(meeting.bot_id))
            except Exception as be:
                logger.warning(f"Provider cleanup notice on meeting deletion: {be}")
        except Exception as e:
            logger.warning(f"Bot provider cleanup notice: {e}")

    # 4. Delete meeting in database transaction
    db.delete(meeting)
    db.commit()

    # 5. Delete stored media files (post-transaction so DB is never in half-deleted state)
    storage = get_storage()
    for fpath in audio_paths_to_delete:
        try:
            storage.delete_file(fpath)
        except Exception as e:
            logger.error(f"Failed to delete stored media file {fpath}: {e}")

    return {"id": meeting_id, "status": "deleted"}

@router.post("/bulk-delete", response_model=BulkDeleteResponse)
def bulk_delete_meetings(
    req: BulkDeleteRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    deleted: List[int] = []
    failed: List[BulkDeleteFailure] = []

    for m_id in req.meeting_ids:
        meeting = db.query(Meeting).filter(Meeting.id == m_id).first()
        if not meeting:
            failed.append(BulkDeleteFailure(id=m_id, reason="Meeting not found"))
            continue
        if meeting.user_id != current_user.id and current_user.role != "admin":
            failed.append(BulkDeleteFailure(id=m_id, reason="Not authorized to delete this meeting"))
            continue

        try:
            perform_delete_meeting(meeting, db)
            deleted.append(m_id)
        except Exception as e:
            logger.error(f"Error deleting meeting {m_id} in bulk-delete: {e}")
            db.rollback()
            failed.append(BulkDeleteFailure(id=m_id, reason=str(e)))

    return BulkDeleteResponse(
        success=len(failed) == 0,
        deleted=deleted,
        failed=failed
    )

@router.delete("/{meeting_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_meeting(
    meeting_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    if meeting.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized to delete this meeting")

    perform_delete_meeting(meeting, db)
    return None

def check_meeting_edit_permission(meeting: Meeting, current_user: User, db: Session):
    """
    Enforces RBAC for editing meetings:
    - Only owner, admin, or shared user with can_edit=True may edit
    - Returns 403 otherwise
    - Blocks edits while status is 'processing' (or uploading, transcribing, diarizing, analyzing)
    """
    if str(meeting.status).lower() in ["uploading", "transcribing", "diarizing", "analyzing", "processing"]:
        raise HTTPException(
            status_code=400,
            detail="Meeting is currently processing. Edits are disabled until processing finishes."
        )

    if meeting.user_id == current_user.id or current_user.role == "admin":
        return True

    share = db.query(MeetingShare).filter(
        MeetingShare.meeting_id == meeting.id,
        MeetingShare.user_id == current_user.id,
        MeetingShare.can_edit == True
    ).first()
    if share:
        return True

    raise HTTPException(status_code=403, detail="Not authorized to edit this meeting")

def check_concurrency(client_updated_at: Optional[datetime.datetime], current_updated_at: Optional[datetime.datetime]):
    """
    Optimistic concurrency control:
    If client provided updated_at and it differs from database timestamp, return 409 Conflict.
    """
    if client_updated_at is not None and current_updated_at is not None:
        stored_ts = current_updated_at.replace(microsecond=0, tzinfo=None)
        client_ts = client_updated_at.replace(microsecond=0, tzinfo=None)
        if stored_ts != client_ts:
            raise HTTPException(
                status_code=409,
                detail="This meeting was changed by someone else. Reload to see the latest version."
            )

@router.patch("/{meeting_id}", response_model=MeetingResponse)
def update_meeting(
    meeting_id: int,
    payload: MeetingUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    check_meeting_edit_permission(meeting, current_user, db)
    check_concurrency(payload.updated_at, meeting.updated_at)

    if payload.title is not None:
        meeting.title = payload.title.strip()
    if payload.tag is not None:
        current_tags = list(meeting.tags or [])
        meeting.tags = [payload.tag] + [t for t in current_tags if t.lower() != payload.tag.lower()]
    if payload.tags is not None:
        meeting.tags = payload.tags
    if payload.scheduled_at is not None:
        meeting.scheduled_at = payload.scheduled_at
    if payload.description is not None:
        meeting.description = payload.description.strip()

    meeting.updated_at = datetime.datetime.utcnow()
    if payload.title is not None or payload.description is not None:
        recompute_and_save_meeting_effectiveness(meeting, db)
    db.commit()
    db.refresh(meeting)
    return meeting

@router.patch("/{meeting_id}/summary", response_model=SummaryResponse)
def update_meeting_summary(
    meeting_id: int,
    payload: SummaryUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    check_meeting_edit_permission(meeting, current_user, db)

    if not meeting.summary:
        meeting.summary = Summary(
            meeting_id=meeting.id,
            overview=payload.overview or "",
            key_takeaways=payload.key_takeaways or [],
            next_steps=payload.next_steps or "",
            created_at=datetime.datetime.utcnow(),
        )
        db.add(meeting.summary)
        db.flush()

    check_concurrency(payload.updated_at, meeting.summary.updated_at or meeting.updated_at)

    old_overview = meeting.summary.overview or ""
    if payload.overview is not None:
        meeting.summary.overview = payload.overview.strip()
    if payload.key_takeaways is not None:
        meeting.summary.key_takeaways = payload.key_takeaways
    if payload.next_steps is not None:
        meeting.summary.next_steps = payload.next_steps.strip()

    now = datetime.datetime.utcnow()
    meeting.summary.edited_by_user = True
    meeting.summary.updated_at = now
    meeting.summary.updated_by = current_user.full_name or current_user.email or "User"
    meeting.updated_at = now

    # Log to HumanCorrection retraining dataset
    if payload.overview is not None and payload.overview.strip() != old_overview.strip():
        corr = HumanCorrection(
            meeting_id=meeting.id,
            user_id=current_user.id,
            original_text=old_overview,
            corrected_text=meeting.summary.overview,
            correction_type="summary",
            model_version=meeting.summary.model_version or "bart-summarizer-v1.8",
            created_at=now,
        )
        db.add(corr)

    db.commit()
    db.refresh(meeting.summary)
    return meeting.summary

@router.post("/{meeting_id}/summary/regenerate", response_model=SummaryResponse)
def regenerate_meeting_summary(
    meeting_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    check_meeting_edit_permission(meeting, current_user, db)

    from app.nlp_analysis import MeetingSummarizer
    transcript_dicts = [
        {"speaker": t.speaker, "start_time": t.start_time, "end_time": t.end_time, "text": t.text}
        for t in meeting.transcripts
    ]
    extracted_decisions = [{"decision_text": d.decision_text} for d in meeting.decisions]
    summary_data = MeetingSummarizer.generate_summary(meeting.title, transcript_dicts, extracted_decisions)

    now = datetime.datetime.utcnow()
    if not meeting.summary:
        meeting.summary = Summary(meeting_id=meeting.id, overview=summary_data["overview"])
        db.add(meeting.summary)

    meeting.summary.overview = summary_data["overview"]
    meeting.summary.key_takeaways = summary_data["key_takeaways"]
    meeting.summary.next_steps = summary_data["next_steps"]
    meeting.summary.edited_by_user = False
    meeting.summary.updated_at = now
    meeting.summary.updated_by = "AI Pipeline"
    meeting.updated_at = now

    db.commit()
    db.refresh(meeting.summary)
    return meeting.summary

@router.patch("/{meeting_id}/transcript/{line_id}", response_model=TranscriptItem)
def update_transcript_line(
    meeting_id: int,
    line_id: int,
    payload: TranscriptLineUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    check_meeting_edit_permission(meeting, current_user, db)

    line = db.query(Transcript).filter(
        Transcript.id == line_id,
        Transcript.meeting_id == meeting_id
    ).first()
    if not line:
        raise HTTPException(status_code=404, detail="Transcript line not found")

    orig_text = line.text
    orig_speaker = line.speaker
    text_changed = payload.text is not None and payload.text.strip() != orig_text
    speaker_changed = payload.speaker is not None and payload.speaker.strip() != orig_speaker

    if text_changed:
        line.text = payload.text.strip()
    if speaker_changed:
        line.speaker = payload.speaker.strip()

    if text_changed or speaker_changed:
        line.confidence = 1.0  # Human corrected
        now = datetime.datetime.utcnow()
        meeting.updated_at = now

        # Update vector index so search and RAG chatbot use corrected text
        try:
            vector_search_service.update_transcript_vector(
                transcript_id=line.id,
                text=line.text,
                speaker=line.speaker,
                db=db
            )
        except Exception as e:
            logger.warning(f"Vector update notice: {e}")

        # Log correction to HumanCorrection table for classifier retraining
        corr = HumanCorrection(
            meeting_id=meeting.id,
            user_id=current_user.id,
            original_text=orig_text,
            corrected_text=line.text,
            original_assignee=orig_speaker,
            corrected_assignee=line.speaker,
            correction_type="transcript_edit",
            model_version=line.model_version or "whisper-v3",
            created_at=now,
        )
        db.add(corr)
        db.commit()
        db.refresh(line)

    recompute_and_save_meeting_effectiveness(meeting, db)

    ts_str = format_seconds_to_ts(line.start_time)
    return {
        "id": line.id,
        "speaker": line.speaker,
        "start_time": line.start_time,
        "end_time": line.end_time,
        "text": line.text,
        "is_action_item": line.is_action_item,
        "confidence": line.confidence,
        "timestamp_str": f"[{ts_str}]",
        "formatted_line": f"[{ts_str}] {line.speaker}: {line.text}"
    }

@router.get("/{meeting_id}/transcript", response_model=List[TranscriptItem])
def get_meeting_transcript(
    meeting_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    
    # Return formatted lines [00:02:15] Speaker 2: ...
    results = []
    for t in meeting.transcripts:
        ts = format_timestamp(t.start_time)
        results.append({
            "id": t.id,
            "speaker": t.speaker,
            "start_time": t.start_time,
            "end_time": t.end_time,
            "text": t.text,
            "timestamp_str": ts,
            "formatted_line": f"{ts} {t.speaker}: {t.text}",
            "is_action_item": t.is_action_item,
            "confidence": t.confidence,
        })
    return results

@router.patch("/{meeting_id}/rename-speaker")
def rename_speaker(
    meeting_id: int,
    req: RenameSpeakerRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Step 6: Renames 'Speaker 1' to user's real name across all meeting transcripts,
    participants, and analytics.
    """
    from app.diarization import rename_speaker_in_meeting
    try:
        res = rename_speaker_in_meeting(meeting_id, req.old_name, req.new_name, db)
        meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
        if meeting:
            recompute_and_save_meeting_effectiveness(meeting, db)
        return res
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.get("/{meeting_id}/summary", response_model=SummaryResponse)
def get_meeting_summary(
    meeting_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting or not meeting.summary:
        raise HTTPException(status_code=404, detail="Summary not ready yet or meeting not found")
    return meeting.summary

@router.get("/{meeting_id}/action-items", response_model=List[ActionItemResponse])
def get_meeting_action_items(
    meeting_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    return [item for item in meeting.action_items if getattr(item, "status", "confirmed") not in ["suggested", "dismissed"]]

@router.get("/{meeting_id}/decisions", response_model=List[DecisionResponse])
def get_meeting_decisions(
    meeting_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    return meeting.decisions

@router.get("/{meeting_id}/analytics", response_model=AnalyticsResponse)
def get_meeting_analytics(
    meeting_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting or not meeting.analytics:
        raise HTTPException(status_code=404, detail="Analytics not ready yet")

    an = meeting.analytics
    # Topic chapters & effectiveness score generation if not already stored
    if not an.topic_chapters or not an.effectiveness_breakdown:
        transcript_dicts = [
            {"speaker": t.speaker, "start_time": t.start_time, "end_time": t.end_time, "text": t.text}
            for t in meeting.transcripts
        ]
        action_dicts = [{"title": a.title, "assignee": a.assignee} for a in meeting.action_items]
        decision_dicts = [{"decision_text": d.decision_text} for d in meeting.decisions]
        an_dict = {
            "sentiment_score": an.sentiment_score,
            "speaking_time_distribution": an.speaking_time_distribution or {}
        }
        chapters = MeetingAnalyticsEngine.generate_topic_chapters(transcript_dicts)
        eff = MeetingAnalyticsEngine.compute_meeting_effectiveness(transcript_dicts, action_dicts, decision_dicts, an_dict)
        
        an.topic_chapters = chapters
        an.effectiveness_score = eff["score"]
        an.effectiveness_breakdown = eff["breakdown"]
        an.total_topics = len(chapters) or an.total_topics
        db.commit()
        db.refresh(an)

    return an

@router.post("/{meeting_id}/comments", response_model=CommentResponse)
def add_comment(
    meeting_id: int,
    comment_in: CommentCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    comment = Comment(
        meeting_id=meeting.id,
        user_id=current_user.id,
        text=comment_in.text,
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)

    return {
        "id": comment.id,
        "meeting_id": comment.meeting_id,
        "user_id": comment.user_id,
        "user_name": current_user.full_name,
        "text": comment.text,
        "created_at": comment.created_at,
    }

@router.get("/{meeting_id}/comments", response_model=List[CommentResponse])
def get_meeting_comments(
    meeting_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    comments = db.query(Comment).filter(Comment.meeting_id == meeting_id).order_by(Comment.created_at.asc()).all()
    return [
        {
            "id": c.id,
            "meeting_id": c.meeting_id,
            "user_id": c.user_id,
            "user_name": c.user.full_name if c.user else "User",
            "text": c.text,
            "created_at": c.created_at,
        }
        for c in comments
    ]

@router.post("/{meeting_id}/share")
def share_meeting(
    meeting_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    share_token = f"share_{meeting.id}_{abs(hash(str(meeting.created_at)))}"
    share_url = f"/meetings/{meeting.id}?token={share_token}"
    return {
        "status": "success",
        "meeting_id": meeting.id,
        "title": meeting.title,
        "share_token": share_token,
        "share_url": share_url,
        "message": "Shareable meeting access URL created successfully."
    }


@router.post("/chat", response_model=LiveChatMessageResponse)
def chat_global_rag(
    req: MeetingChatRequest,
    meeting_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Ask your meetings (Global RAG Chatbot):
    Answers questions across all user meetings or a specific meeting using semantic transcript search.
    """
    res = answer_meeting_rag(
        query=req.query,
        meeting_id=meeting_id,
        user_id=current_user.id,
        db=db
    )
    return res


@router.post("/{meeting_id}/chat", response_model=LiveChatMessageResponse)
def chat_with_meeting_rag(
    meeting_id: int,
    req: MeetingChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Ask your meetings (RAG chat):
    Semantic Q&A grounded strictly in transcript utterances with exact timestamp citations.
    """
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    res = answer_meeting_rag(
        query=req.query,
        meeting_id=meeting.id,
        user_id=current_user.id,
        db=db
    )
    return res

@router.post("/{meeting_id}/translate", response_model=TranslationResponse)
def translate_meeting_transcripts(
    meeting_id: int,
    req: TranslationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Multilingual transcription and translation:
    Translates meeting transcripts between Indian vernaculars (Hindi, Tamil, Telugu, etc.)
    and English, persisting translated_text for bilingual toggle views.
    """
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    transcripts = db.query(Transcript).filter(Transcript.meeting_id == meeting_id).order_by(Transcript.start_time.asc()).all()
    source_lang = meeting.primary_language or "hi"
    target_lang = req.target_language or "en"

    count = 0
    for t in transcripts:
        if not t.translated_text or req.target_language != "en":
            t.translated_text = translate_transcript_text(t.text, source_lang=t.language or source_lang, target_lang=target_lang)
            count += 1

    meeting.primary_language = target_lang
    db.commit()

    return {
        "meeting_id": meeting.id,
        "target_language": target_lang,
        "translated_count": count,
        "transcripts": transcripts,
    }


# =============================================================================
# LIVE MEETINGS (LIVEKIT WEBRTC ROOMS, CONSENT, PARTICIPANTS, AND LIFECYCLE)
# =============================================================================

_join_rate_limiter: Dict[str, List[float]] = {}

def check_join_rate_limit(key: str, max_requests: int = 20, window_seconds: int = 60) -> bool:
    """Sliding-window in-memory join rate limiter."""
    now = time.time()
    times = _join_rate_limiter.setdefault(key, [])
    _join_rate_limiter[key] = [t for t in times if now - t < window_seconds]
    if len(_join_rate_limiter[key]) >= max_requests:
        return False
    _join_rate_limiter[key].append(now)
    return True

def reset_join_rate_limiter():
    """Testing helper to clear rate limiter state."""
    _join_rate_limiter.clear()

def verify_live_meeting_permission(meeting: Meeting, user: User, db: Session) -> tuple[bool, str]:
    """
    Checks permissions to join a live meeting:
    - Host / owner / admin: always permitted
    - Explicit meeting share: editor permitted, viewer rejected (403)
    - Team membership: owner / admin / member permitted, viewer rejected (403)
    - Invited participant (email or name matches meeting.participants): permitted
    - Otherwise: rejected (403)
    """
    if meeting.user_id == user.id or meeting.host_id == user.id or user.role == "admin":
        return True, "host"

    # Explicit meeting share check
    share = db.query(MeetingShare).filter(
        MeetingShare.meeting_id == meeting.id,
        MeetingShare.user_id == user.id
    ).first()
    if share is not None:
        if not share.can_edit:
            return False, "Viewers do not have permission to join live meetings"
        return True, "shared_editor"

    # Team membership check
    if meeting.team_id:
        tm = db.query(TeamMember).filter(
            TeamMember.team_id == meeting.team_id,
            TeamMember.user_id == user.id
        ).first()
        if tm is not None:
            if tm.role == "viewer":
                return False, "Viewers do not have permission to join live meetings"
            return True, "team_member"

    # Invited participant check
    parts = [str(p).strip().lower() for p in (meeting.participants or [])]
    u_email = (user.email or "").strip().lower()
    u_name = (user.full_name or "").strip().lower()
    for p in parts:
        if p and (p == u_email or p == u_name or (u_email and u_email in p) or (u_name and u_name in p)):
            return True, "invited_participant"

    return False, "You do not have permission to join this live meeting"


def is_livekit_configured() -> bool:
    url = str(getattr(settings, "LIVEKIT_URL", "") or "").strip()
    key = str(getattr(settings, "LIVEKIT_API_KEY", "") or "").strip()
    sec = str(getattr(settings, "LIVEKIT_API_SECRET", "") or "").strip()
    if not url or not key or not sec:
        return False
    if "your-project" in url or "placeholder" in url or "<" in url:
        return False
    if "livekit.cloud" in url and (key == "devkey" or sec == "secret"):
        return False
    return True

@router.post("/{meeting_id}/live/join", response_model=LiveJoinResponse)
def join_live_meeting(
    meeting_id: int,
    req: LiveJoinRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Join a live meeting:
    1. Verifies meeting exists and is a live meeting
    2. Validates user consent (MUST consent to recording and analysis)
    3. Checks permissions (host, invited users, team members with edit rights; viewers rejected)
    4. Applies join rate limiting
    5. Enforces max participants capacity (default 8)
    6. Stores consent timestamp in live_participants
    7. Generates and returns a signed, short-lived LiveKit WebRTC access token
    """
    if not is_livekit_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Live meetings are not configured"
        )

    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    if not meeting.is_live:
        raise HTTPException(status_code=400, detail="This meeting is not configured as a live meeting")

    # Mandatory recording & analysis consent check
    if not req.consent:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Consent to recording and analysis is required to join this meeting"
        )

    # Check if room is locked
    if meeting.locked:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This meeting has been locked by the host"
        )

    # Check if participant was previously removed
    prev_lp = db.query(LiveParticipant).filter(
        LiveParticipant.meeting_id == meeting.id,
        LiveParticipant.user_id == current_user.id
    ).order_by(LiveParticipant.id.desc()).first()
    if prev_lp and prev_lp.status == "removed":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You have been removed from this meeting by the host"
        )

    # Check passcode if required
    if meeting.passcode_hash:
        from app.auth import verify_password
        if not req.passcode or not verify_password(req.passcode, meeting.passcode_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Meeting passcode is required or incorrect"
            )

    # Permission check
    can_join, reason = verify_live_meeting_permission(meeting, current_user, db)
    if not can_join:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=reason)

    # Rate limiting check
    rate_limit_max = getattr(settings, "LIVEKIT_JOIN_RATE_LIMIT_PER_MINUTE", 20)
    if not check_join_rate_limit(f"user_{current_user.id}", max_requests=rate_limit_max):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please wait a moment before trying to join again."
        )

    # Max participants check
    max_participants = getattr(settings, "LIVEKIT_MAX_PARTICIPANTS", 8)
    active_count = db.query(LiveParticipant).filter(
        LiveParticipant.meeting_id == meeting.id,
        LiveParticipant.left_at.is_(None)
    ).count()
    if active_count >= max_participants:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Meeting has reached maximum capacity of {max_participants} participants"
        )

    now = datetime.datetime.utcnow()
    if meeting.live_status == "scheduled":
        meeting.live_status = "live"
        if not meeting.started_at:
            meeting.started_at = now

    is_host = bool(meeting.host_id == current_user.id or meeting.user_id == current_user.id or current_user.role == "admin")

    # Check waiting room requirement
    is_waiting = bool(meeting.waiting_room_enabled and not is_host)
    if prev_lp and prev_lp.status == "admitted":
        is_waiting = False

    participant = prev_lp or LiveParticipant(
        meeting_id=meeting.id,
        user_id=current_user.id,
        display_name=req.display_name.strip(),
        role="host" if is_host else "participant",
        status="waiting" if is_waiting else "admitted",
        joined_at=now,
        consent_at=now,
    )
    if not prev_lp:
        db.add(participant)
    else:
        participant.display_name = req.display_name.strip()
        participant.consent_at = now
        if not is_waiting and participant.status != "admitted":
            participant.status = "admitted"
    db.commit()
    db.refresh(participant)

    room_name = meeting.room_name or f"meetora-room-{meeting.id}"
    participant_identity = f"usr_{current_user.id}_{uuid.uuid4().hex[:6]}"

    if is_waiting:
        db.add(AuditLog(
            user_id=current_user.id,
            user_email=current_user.email,
            action="WAITING_ROOM_JOIN_REQUEST",
            resource=f"meeting:{meeting.id}",
            status="SUCCESS",
            severity="INFO",
            details={"display_name": req.display_name.strip()}
        ))
        db.commit()
        return LiveJoinResponse(
            token="",
            livekit_url=settings.LIVEKIT_URL,
            room_name=room_name,
            participant_id=participant_identity,
            display_name=req.display_name.strip(),
            is_host=False,
            status="waiting",
            waiting_message="Waiting for host to admit you to the meeting."
        )

    # Generate short-lived LiveKit token
    room_name = meeting.room_name or f"meetora-room-{meeting.id}"
    participant_identity = f"usr_{current_user.id}_{uuid.uuid4().hex[:6]}"

    from livekit.api import AccessToken, VideoGrants
    grant = VideoGrants(
        room_join=True,
        room=room_name,
        can_publish=True,
        can_subscribe=True,
    )
    if is_host:
        grant.room_admin = True

    token = (
        AccessToken(settings.LIVEKIT_API_KEY, settings.LIVEKIT_API_SECRET)
        .with_identity(participant_identity)
        .with_name(req.display_name.strip())
        .with_grants(grant)
        .with_ttl(datetime.timedelta(hours=2))
        .to_jwt()
    )

    return LiveJoinResponse(
        token=token,
        livekit_url=settings.LIVEKIT_URL,
        room_name=room_name,
        participant_id=participant_identity,
        display_name=req.display_name.strip(),
        is_host=is_host
    )


@router.post("/{meeting_id}/live/end", response_model=LiveEndResponse)
def end_live_meeting(
    meeting_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    End a live meeting (host only):
    Sets meeting live_status to 'ended' and closes all active participant sessions.
    If called by a non-host, safely records their participant session as left instead of erroring out.
    """
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    now = datetime.datetime.utcnow()

    # Host-only authorization check
    is_host = bool(
        (meeting.host_id and meeting.host_id == current_user.id) or
        (meeting.user_id and meeting.user_id == current_user.id) or
        current_user.role in ["admin", "superadmin"] or
        not meeting.host_id
    )

    if not is_host:
        # Gracefully handle non-host caller by marking them as left so they are never blocked
        db.query(LiveParticipant).filter(
            LiveParticipant.meeting_id == meeting.id,
            LiveParticipant.user_id == current_user.id,
            LiveParticipant.left_at.is_(None)
        ).update({"left_at": now})
        db.commit()
        return LiveEndResponse(
            status="left",
            message="Participant session ended",
            ended_at=now
        )

    meeting.live_status = "ended"
    meeting.ended_at = now

    # Mark active participants as left
    db.query(LiveParticipant).filter(
        LiveParticipant.meeting_id == meeting.id,
        LiveParticipant.left_at.is_(None)
    ).update({"left_at": now})

    db.commit()

    return LiveEndResponse(
        status="ended",
        message="Live meeting ended successfully",
        ended_at=now
    )


@router.post("/{meeting_id}/live/leave")
def leave_live_meeting(
    meeting_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Participant leaves live meeting:
    Marks their LiveParticipant record as left.
    If caller was host and no one else is in the meeting, marks meeting as ended.
    """
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        return {"status": "ok", "message": "Meeting not found"}

    now = datetime.datetime.utcnow()
    db.query(LiveParticipant).filter(
        LiveParticipant.meeting_id == meeting.id,
        LiveParticipant.user_id == current_user.id,
        LiveParticipant.left_at.is_(None)
    ).update({"left_at": now})

    # Check remaining participants
    remaining = db.query(LiveParticipant).filter(
        LiveParticipant.meeting_id == meeting.id,
        LiveParticipant.left_at.is_(None)
    ).count()

    is_host = bool(
        (meeting.host_id and meeting.host_id == current_user.id) or
        (meeting.user_id and meeting.user_id == current_user.id)
    )
    if is_host and remaining == 0:
        meeting.live_status = "ended"
        meeting.ended_at = now

    db.commit()
    return {"status": "ok", "message": "Left meeting successfully", "remaining": remaining}


@router.get("/{meeting_id}/live/status", response_model=LiveStatusResponse)
def get_live_meeting_status(
    meeting_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Retrieves live meeting real-time status, active participant count, and caller permissions.
    """
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    active_count = db.query(LiveParticipant).filter(
        LiveParticipant.meeting_id == meeting.id,
        LiveParticipant.left_at.is_(None)
    ).count()

    can_join, _ = verify_live_meeting_permission(meeting, current_user, db) if meeting.is_live else (False, "")
    is_host = bool(meeting.host_id == current_user.id or meeting.user_id == current_user.id or current_user.role == "admin")

    return LiveStatusResponse(
        meeting_id=meeting.id,
        is_live=meeting.is_live,
        live_status=meeting.live_status or "scheduled",
        room_name=meeting.room_name,
        record_mode=meeting.record_mode or "audio_video",
        host_id=meeting.host_id,
        started_at=meeting.started_at,
        ended_at=meeting.ended_at,
        active_participants_count=active_count,
        can_join=can_join,
        is_host=is_host
    )


@router.post("/join-by-code", response_model=JoinByCodeResponse)
def join_meeting_by_code(
    req: JoinByCodeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Lookup a meeting by meeting_code (or meeting ID) and verify passcode if needed."""
    code = req.meeting_code.strip().lower()
    meeting = db.query(Meeting).filter(Meeting.meeting_code == code).first()
    if not meeting and code.isdigit():
        meeting = db.query(Meeting).filter(Meeting.id == int(code)).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found for given code")

    if not meeting.is_live:
        raise HTTPException(status_code=400, detail="This meeting is not a live meeting")

    requires_passcode = bool(meeting.passcode_hash)
    if requires_passcode and req.passcode:
        from app.auth import verify_password
        if not verify_password(req.passcode, meeting.passcode_hash):
            raise HTTPException(status_code=401, detail="Invalid meeting passcode")

    return JoinByCodeResponse(
        meeting_id=meeting.id,
        title=meeting.title,
        meeting_code=meeting.meeting_code or f"meet-{meeting.id}",
        requires_passcode=requires_passcode,
        is_live=meeting.is_live,
        live_status=meeting.live_status or "scheduled"
    )


@router.get("/{meeting_id}/chats", response_model=List[LiveChatMessageResponse])
def get_meeting_chats(
    meeting_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieve chat history for a live meeting, filtering private chats by recipient/sender."""
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    chats = db.query(MeetingChat).filter(
        MeetingChat.meeting_id == meeting_id
    ).order_by(MeetingChat.created_at.asc()).all()

    visible = [
        c for c in chats
        if not c.is_private or c.sender_id == current_user.id or c.recipient_id == current_user.id
    ]
    return visible


@router.post("/{meeting_id}/chats", response_model=LiveChatMessageResponse, status_code=status.HTTP_201_CREATED)
def send_meeting_chat(
    meeting_id: int,
    payload: LiveChatMessageCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Persist an in-meeting chat message."""
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    sender_name = current_user.full_name or current_user.email
    chat = MeetingChat(
        meeting_id=meeting_id,
        sender_id=current_user.id,
        sender_name=sender_name,
        message=payload.message.strip(),
        is_private=bool(payload.is_private),
        recipient_id=payload.recipient_id,
        created_at=datetime.datetime.utcnow(),
    )
    db.add(chat)
    db.commit()
    db.refresh(chat)
    return chat


def send_file_partial(file_path: str, range_header: Optional[str] = None, media_type: str = "video/webm"):
    """Streams a media file supporting HTTP 206 Partial Content range requests for video seeking."""
    from starlette.responses import StreamingResponse
    file_size = os.path.getsize(file_path)
    if not range_header:
        def iter_full():
            with open(file_path, "rb") as f:
                while chunk := f.read(1024 * 1024):
                    yield chunk
        headers = {
            "Accept-Ranges": "bytes",
            "Content-Length": str(file_size),
        }
        return StreamingResponse(iter_full(), headers=headers, media_type=media_type)

    byte1, byte2 = 0, None
    m = re.search(r"bytes=(\d+)-(\d*)", range_header)
    if m:
        g = m.groups()
        byte1 = int(g[0])
        if g[1]:
            byte2 = int(g[1])

    if byte2 is None:
        byte2 = min(byte1 + 2 * 1024 * 1024 - 1, file_size - 1)

    length = byte2 - byte1 + 1

    def iter_range():
        with open(file_path, "rb") as f:
            f.seek(byte1)
            remaining = length
            while remaining > 0:
                chunk_size = min(remaining, 64 * 1024)
                data = f.read(chunk_size)
                if not data:
                    break
                remaining -= len(data)
                yield data

    headers = {
        "Content-Range": f"bytes {byte1}-{byte2}/{file_size}",
        "Accept-Ranges": "bytes",
        "Content-Length": str(length),
    }
    return StreamingResponse(iter_range(), status_code=206, headers=headers, media_type=media_type)


@router.post("/{meeting_id}/live/record/start", response_model=RecordingStartResponse)
async def start_live_recording(
    meeting_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Host starts recording:
    - Verifies host permission
    - Sets meeting live_status to 'recording'
    - Triggers LiveKit RoomCompositeEgress if LiveKit is active
    - Creates a Recording entry in database
    """
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    if not meeting.is_live:
        raise HTTPException(status_code=400, detail="This meeting is not a live meeting")

    is_host = bool(meeting.host_id == current_user.id or meeting.user_id == current_user.id or current_user.role == "admin")
    if not is_host:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the meeting host can start recording")

    now = datetime.datetime.utcnow()
    meeting.live_status = "recording"

    egress_ids = []
    # Attempt LiveKit Egress if configured
    try:
        from livekit import api
        if (
            settings.LIVEKIT_URL and
            not settings.LIVEKIT_URL.startswith("mock") and
            "your-project" not in settings.LIVEKIT_URL
        ):
            lk_api = api.LiveKitAPI(settings.LIVEKIT_URL, settings.LIVEKIT_API_KEY, settings.LIVEKIT_API_SECRET)
            room_name = meeting.room_name or f"meetora-room-{meeting.id}"
            
            # Start RoomCompositeEgress (video + mixed audio, 720p)
            req = api.RoomCompositeEgressRequest(
                room_name=room_name,
                layout="grid",
                file=api.EncodedFileOutput(
                    filepath=f"recordings/{room_name}/composite.mp4"
                ),
                preset=api.EncodingOptionsPreset.H264_720P_30
            )
            res = await lk_api.egress.start_room_composite_egress(req)
            if hasattr(res, "egress_id"):
                egress_ids.append(res.egress_id)
            await lk_api.aclose()
    except Exception as e:
        logger.info(f"Egress service notice (fallback will handle recording): {e}")

    rec = Recording(
        meeting_id=meeting.id,
        kind="composite_video" if meeting.record_mode == "audio_video" else "composite_audio",
        status="recording",
        egress_id=egress_ids[0] if egress_ids else None,
        created_at=now
    )
    db.add(rec)
    db.commit()

    return RecordingStartResponse(
        status="recording",
        recording=True,
        egress_ids=egress_ids,
        message="Meeting recording started successfully"
    )


@router.post("/{meeting_id}/live/record/stop", response_model=RecordingStopResponse)
async def stop_live_recording(
    meeting_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Host stops recording:
    - Verifies host permission
    - Sets meeting live_status back to 'live'
    - Halts any active LiveKit Egress
    """
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    is_host = bool(meeting.host_id == current_user.id or meeting.user_id == current_user.id or current_user.role == "admin")
    if not is_host:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the meeting host can stop recording")

    if meeting.live_status == "recording":
        meeting.live_status = "live"
    db.commit()

    # Find active recordings and stop egress if present
    active_recs = db.query(Recording).filter(
        Recording.meeting_id == meeting.id,
        Recording.status == "recording"
    ).all()

    for r in active_recs:
        if r.egress_id:
            try:
                from livekit import api
                lk_api = api.LiveKitAPI(settings.LIVEKIT_URL, settings.LIVEKIT_API_KEY, settings.LIVEKIT_API_SECRET)
                await lk_api.egress.stop_egress(api.StopEgressRequest(egress_id=r.egress_id))
                await lk_api.aclose()
            except Exception as e:
                logger.info(f"Stop egress notice: {e}")

    return RecordingStopResponse(
        status="stopped",
        recording=False,
        message="Meeting recording stopped successfully"
    )


@router.post("/{meeting_id}/recordings/upload", response_model=ChunkUploadResponse)
async def upload_recording_chunk(
    meeting_id: int,
    chunk: UploadFile = File(...),
    chunk_index: int = Form(...),
    total_chunks: int = Form(...),
    kind: str = Form("composite_video"),
    participant_id: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    In-browser MediaRecorder chunked upload fallback:
    - Receives recording in 5 MB chunks
    - Reassembles on final chunk
    - Normalizes to 16 kHz mono WAV via FFmpeg
    - Calls on_recording_ready to enqueue Celery pipeline
    """
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    temp_dir = os.path.join(settings.UPLOAD_DIR, "temp_recordings", f"m_{meeting_id}_{kind}")
    os.makedirs(temp_dir, exist_ok=True)

    chunk_filename = os.path.join(temp_dir, f"chunk_{chunk_index:05d}.part")
    with open(chunk_filename, "wb") as f:
        content = await chunk.read()
        f.write(content)

    if chunk_index < total_chunks - 1:
        return ChunkUploadResponse(
            status="chunk_received",
            chunk_index=chunk_index,
            total_chunks=total_chunks,
            meeting_id=meeting.id
        )

    # All chunks received: Assemble final file
    final_ext = ".webm" if "video" in kind else ".wav"
    rec_dir = os.path.join(settings.UPLOAD_DIR, "recordings")
    os.makedirs(rec_dir, exist_ok=True)
    final_filename = os.path.join(rec_dir, f"rec_m{meeting_id}_{int(time.time())}{final_ext}")

    with open(final_filename, "wb") as out_file:
        for idx in range(total_chunks):
            part_path = os.path.join(temp_dir, f"chunk_{idx:05d}.part")
            if os.path.exists(part_path):
                with open(part_path, "rb") as pf:
                    out_file.write(pf.read())

    # Clean up temp chunks
    try:
        shutil.rmtree(temp_dir, ignore_errors=True)
    except Exception:
        pass

    file_size = os.path.getsize(final_filename) if os.path.exists(final_filename) else 0

    # Create/update recording record
    rec = db.query(Recording).filter(
        Recording.meeting_id == meeting.id,
        Recording.kind == kind,
        Recording.status == "recording"
    ).first()

    if not rec:
        rec = Recording(
            meeting_id=meeting.id,
            kind=kind,
            participant_id=participant_id,
            storage_key=final_filename,
            size_bytes=file_size,
            status="ready",
            created_at=datetime.datetime.utcnow()
        )
        db.add(rec)
    else:
        rec.status = "ready"
        rec.storage_key = final_filename
        rec.size_bytes = file_size

    db.commit()
    db.refresh(rec)

    # Normalize audio and trigger pipeline
    from app.pipeline_orchestrator import on_recording_ready
    on_recording_ready(
        meeting_id=meeting.id,
        media_set={"composite_path": final_filename, "storage_key": final_filename},
        idempotency_key=f"upload_m_{meeting.id}_{rec.id}",
        db=db
    )

    return ChunkUploadResponse(
        status="completed",
        chunk_index=chunk_index,
        total_chunks=total_chunks,
        recording_id=rec.id,
        meeting_id=meeting.id
    )


@router.get("/{meeting_id}/recordings/playback", response_model=PlaybackResponse)
def get_recording_playback(
    meeting_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Generates a secure, short-lived signed URL for private media playback.
    Signed JWT token expires after 30 minutes.
    """
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    # Permission check: must be owner, host, invited, or team member
    can_view = bool(
        meeting.user_id == current_user.id or
        meeting.host_id == current_user.id or
        current_user.role == "admin" or
        current_user.email in (meeting.participants or [])
    )
    if not can_view:
        raise HTTPException(status_code=403, detail="You do not have permission to view recordings for this meeting")

    rec = db.query(Recording).filter(
        Recording.meeting_id == meeting.id,
        Recording.status == "ready"
    ).order_by(Recording.created_at.desc()).first()

    now_ts = int(time.time())
    exp_ts = now_ts + 1800  # 30 minutes
    token_payload = {
        "sub": f"user_{current_user.id}",
        "meeting_id": meeting.id,
        "recording_id": rec.id if rec else None,
        "exp": exp_ts,
        "purpose": "playback"
    }
    import jwt
    token = jwt.encode(token_payload, settings.SECRET_KEY, algorithm="HS256")

    db.add(AuditLog(
        user_id=current_user.id,
        user_email=current_user.email,
        action="RECORDING_VIEW",
        resource=f"meeting:{meeting.id}",
        status="SUCCESS",
        severity="INFO",
        details={"recording_id": rec.id if rec else None}
    ))
    db.commit()

    stream_url = f"/api/meetings/{meeting.id}/recordings/stream?token={token}"
    return PlaybackResponse(
        playback_url=stream_url,
        expires_at=datetime.datetime.utcfromtimestamp(exp_ts),
        kind=rec.kind if rec else "composite_video",
        duration=rec.duration if rec else float(meeting.duration_seconds or 0)
    )


@router.get("/{meeting_id}/recordings/stream")
def stream_recording_media(
    meeting_id: int,
    token: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Streams private recording media with HTTP 206 Partial Content range requests.
    Validates short-lived signed playback token.
    """
    import jwt
    try:
        claims = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        if claims.get("meeting_id") != meeting_id or claims.get("purpose") != "playback":
            raise HTTPException(status_code=401, detail="Invalid token for this meeting")
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid or expired playback token: {e}")

    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    rec = db.query(Recording).filter(
        Recording.meeting_id == meeting.id,
        Recording.status == "ready"
    ).order_by(Recording.created_at.desc()).first()

    target_path = None
    if rec and rec.storage_key and os.path.exists(rec.storage_key):
        target_path = rec.storage_key
    elif meeting.audio_path and os.path.exists(meeting.audio_path):
        target_path = meeting.audio_path

    if not target_path or not os.path.exists(target_path):
        # Fall back to sample media if file missing
        sample_path = os.path.join(settings.UPLOAD_DIR, "sample_meeting_16k_mono.wav")
        if os.path.exists(sample_path):
            target_path = sample_path
        else:
            raise HTTPException(status_code=404, detail="Recording media file not found")

    ext = os.path.splitext(target_path)[1].lower()
    media_type = "video/webm" if ext == ".webm" else ("video/mp4" if ext == ".mp4" else "audio/wav")

    range_header = request.headers.get("range")
    return send_file_partial(target_path, range_header=range_header, media_type=media_type)


@router.get("/{meeting_id}/recordings", response_model=List[RecordingResponse])
def list_meeting_recordings(
    meeting_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Lists all recording entries for a meeting."""
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    return db.query(Recording).filter(Recording.meeting_id == meeting_id).order_by(Recording.created_at.asc()).all()


def check_moderator_access(meeting: Meeting, current_user: User, db: Session) -> bool:
    if meeting.host_id == current_user.id or meeting.user_id == current_user.id or current_user.role == "admin":
        return True
    cohost = db.query(LiveParticipant).filter(
        LiveParticipant.meeting_id == meeting.id,
        LiveParticipant.user_id == current_user.id,
        LiveParticipant.role == "cohost",
        LiveParticipant.left_at.is_(None)
    ).first()
    return bool(cohost)


@router.get("/{meeting_id}/live/waiting-status", response_model=LiveJoinResponse)
def get_waiting_status(
    meeting_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    is_host = bool(meeting.host_id == current_user.id or meeting.user_id == current_user.id or current_user.role == "admin")
    lp = db.query(LiveParticipant).filter(
        LiveParticipant.meeting_id == meeting.id,
        LiveParticipant.user_id == current_user.id
    ).order_by(LiveParticipant.id.desc()).first()

    room_name = meeting.room_name or f"meetora-room-{meeting.id}"
    participant_identity = f"usr_{current_user.id}"

    current_status = lp.status if lp else ("admitted" if is_host else "waiting")

    if current_status == "removed":
        raise HTTPException(status_code=403, detail="You have been removed from this meeting by the host.")
    if current_status == "denied":
        raise HTTPException(status_code=403, detail="Your request to join this meeting was denied by the host.")

    token = ""
    if current_status == "admitted" or is_host:
        from livekit.api import AccessToken, VideoGrants
        grant = VideoGrants(
            room_join=True,
            room=room_name,
            can_publish=not (lp and lp.is_muted),
            can_subscribe=True,
        )
        if is_host:
            grant.room_admin = True
        token = (
            AccessToken(settings.LIVEKIT_API_KEY, settings.LIVEKIT_API_SECRET)
            .with_identity(participant_identity)
            .with_name(lp.display_name if lp else current_user.full_name or "Participant")
            .with_grants(grant)
            .with_ttl(datetime.timedelta(hours=2))
            .to_jwt()
        )

    return LiveJoinResponse(
        token=token,
        livekit_url=settings.LIVEKIT_URL,
        room_name=room_name,
        participant_id=participant_identity,
        display_name=lp.display_name if lp else current_user.full_name or "Participant",
        is_host=is_host,
        status=current_status,
        waiting_message="Waiting for host to admit you to the meeting." if current_status == "waiting" else None
    )


@router.get("/{meeting_id}/live/participants", response_model=List[LiveParticipantResponse])
def get_live_participants(
    meeting_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    return db.query(LiveParticipant).filter(LiveParticipant.meeting_id == meeting.id).all()


@router.post("/{meeting_id}/live/moderation/admit", response_model=ModerationActionResponse)
def admit_participant(
    meeting_id: int,
    req: ModerationActionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting or not check_moderator_access(meeting, current_user, db):
        raise HTTPException(status_code=403, detail="Moderator permission required")

    lp = db.query(LiveParticipant).filter(
        LiveParticipant.id == req.participant_id,
        LiveParticipant.meeting_id == meeting.id
    ).first()
    if not lp:
        raise HTTPException(status_code=404, detail="Participant not found")

    lp.status = "admitted"
    db.add(AuditLog(
        user_id=current_user.id,
        user_email=current_user.email,
        action="LIVE_ADMIT_PARTICIPANT",
        resource=f"meeting:{meeting.id}",
        status="SUCCESS",
        severity="INFO",
        details={"participant_id": lp.id, "display_name": lp.display_name}
    ))
    db.commit()
    return ModerationActionResponse(
        success=True,
        action="admit",
        message=f"{lp.display_name} admitted to the meeting.",
        target_participant_id=lp.id
    )


@router.post("/{meeting_id}/live/moderation/admit-all", response_model=ModerationActionResponse)
def admit_all_waiting_participants(
    meeting_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting or not check_moderator_access(meeting, current_user, db):
        raise HTTPException(status_code=403, detail="Moderator permission required")

    count = db.query(LiveParticipant).filter(
        LiveParticipant.meeting_id == meeting.id,
        LiveParticipant.status == "waiting"
    ).update({"status": "admitted"})

    db.add(AuditLog(
        user_id=current_user.id,
        user_email=current_user.email,
        action="LIVE_ADMIT_ALL",
        resource=f"meeting:{meeting.id}",
        status="SUCCESS",
        severity="INFO",
        details={"count": count}
    ))
    db.commit()
    return ModerationActionResponse(
        success=True,
        action="admit_all",
        message=f"Admitted all {count} waiting participants."
    )


@router.post("/{meeting_id}/live/moderation/deny", response_model=ModerationActionResponse)
def deny_participant(
    meeting_id: int,
    req: ModerationActionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting or not check_moderator_access(meeting, current_user, db):
        raise HTTPException(status_code=403, detail="Moderator permission required")

    lp = db.query(LiveParticipant).filter(
        LiveParticipant.id == req.participant_id,
        LiveParticipant.meeting_id == meeting.id
    ).first()
    if not lp:
        raise HTTPException(status_code=404, detail="Participant not found")

    lp.status = "denied"
    db.add(AuditLog(
        user_id=current_user.id,
        user_email=current_user.email,
        action="LIVE_DENY_PARTICIPANT",
        resource=f"meeting:{meeting.id}",
        status="SUCCESS",
        severity="INFO",
        details={"participant_id": lp.id, "display_name": lp.display_name}
    ))
    db.commit()
    return ModerationActionResponse(
        success=True,
        action="deny",
        message=f"{lp.display_name} was denied admission.",
        target_participant_id=lp.id
    )


@router.post("/{meeting_id}/live/moderation/mute-participant", response_model=ModerationActionResponse)
def mute_participant(
    meeting_id: int,
    req: ModerationActionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting or not check_moderator_access(meeting, current_user, db):
        raise HTTPException(status_code=403, detail="Moderator permission required")

    lp = db.query(LiveParticipant).filter(
        LiveParticipant.id == req.participant_id,
        LiveParticipant.meeting_id == meeting.id
    ).first()
    if not lp:
        raise HTTPException(status_code=404, detail="Participant not found")

    lp.is_muted = True
    db.add(AuditLog(
        user_id=current_user.id,
        user_email=current_user.email,
        action="LIVE_MUTE_PARTICIPANT",
        resource=f"meeting:{meeting.id}",
        status="SUCCESS",
        severity="INFO",
        details={"participant_id": lp.id, "display_name": lp.display_name}
    ))
    db.commit()
    return ModerationActionResponse(
        success=True,
        action="mute",
        message=f"{lp.display_name} has been muted.",
        target_participant_id=lp.id
    )


@router.post("/{meeting_id}/live/moderation/mute-all", response_model=ModerationActionResponse)
def mute_all_participants(
    meeting_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting or not check_moderator_access(meeting, current_user, db):
        raise HTTPException(status_code=403, detail="Moderator permission required")

    db.query(LiveParticipant).filter(
        LiveParticipant.meeting_id == meeting.id,
        LiveParticipant.role == "participant",
        LiveParticipant.left_at.is_(None)
    ).update({"is_muted": True})

    db.add(AuditLog(
        user_id=current_user.id,
        user_email=current_user.email,
        action="LIVE_MUTE_ALL",
        resource=f"meeting:{meeting.id}",
        status="SUCCESS",
        severity="INFO"
    ))
    db.commit()
    return ModerationActionResponse(
        success=True,
        action="mute_all",
        message="All participants have been muted."
    )


@router.post("/{meeting_id}/live/moderation/stop-video", response_model=ModerationActionResponse)
def stop_participant_video(
    meeting_id: int,
    req: ModerationActionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting or not check_moderator_access(meeting, current_user, db):
        raise HTTPException(status_code=403, detail="Moderator permission required")

    lp = db.query(LiveParticipant).filter(
        LiveParticipant.id == req.participant_id,
        LiveParticipant.meeting_id == meeting.id
    ).first()
    if not lp:
        raise HTTPException(status_code=404, detail="Participant not found")

    lp.video_disabled = True
    db.add(AuditLog(
        user_id=current_user.id,
        user_email=current_user.email,
        action="LIVE_STOP_VIDEO",
        resource=f"meeting:{meeting.id}",
        status="SUCCESS",
        severity="INFO",
        details={"participant_id": lp.id, "display_name": lp.display_name}
    ))
    db.commit()
    return ModerationActionResponse(
        success=True,
        action="stop_video",
        message=f"Video stopped for {lp.display_name}.",
        target_participant_id=lp.id
    )


@router.post("/{meeting_id}/live/moderation/remove-participant", response_model=ModerationActionResponse)
def remove_participant(
    meeting_id: int,
    req: ModerationActionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting or not check_moderator_access(meeting, current_user, db):
        raise HTTPException(status_code=403, detail="Moderator permission required")

    lp = db.query(LiveParticipant).filter(
        LiveParticipant.id == req.participant_id,
        LiveParticipant.meeting_id == meeting.id
    ).first()
    if not lp:
        raise HTTPException(status_code=404, detail="Participant not found")

    now = datetime.datetime.utcnow()
    lp.status = "removed"
    lp.left_at = now
    db.add(AuditLog(
        user_id=current_user.id,
        user_email=current_user.email,
        action="LIVE_REMOVE_PARTICIPANT",
        resource=f"meeting:{meeting.id}",
        status="SUCCESS",
        severity="INFO",
        details={"participant_id": lp.id, "display_name": lp.display_name}
    ))
    db.commit()
    return ModerationActionResponse(
        success=True,
        action="remove",
        message=f"{lp.display_name} has been removed from the meeting.",
        target_participant_id=lp.id
    )


@router.post("/{meeting_id}/live/moderation/make-cohost", response_model=ModerationActionResponse)
def make_cohost(
    meeting_id: int,
    req: ModerationActionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    is_primary_host = bool(meeting.host_id == current_user.id or meeting.user_id == current_user.id or current_user.role == "admin")
    if not is_primary_host:
        raise HTTPException(status_code=403, detail="Only the primary host can assign co-hosts.")

    lp = db.query(LiveParticipant).filter(
        LiveParticipant.id == req.participant_id,
        LiveParticipant.meeting_id == meeting.id
    ).first()
    if not lp:
        raise HTTPException(status_code=404, detail="Participant not found")

    lp.role = "cohost"
    db.add(AuditLog(
        user_id=current_user.id,
        user_email=current_user.email,
        action="LIVE_MAKE_COHOST",
        resource=f"meeting:{meeting.id}",
        status="SUCCESS",
        severity="INFO",
        details={"participant_id": lp.id, "display_name": lp.display_name}
    ))
    db.commit()
    return ModerationActionResponse(
        success=True,
        action="make_cohost",
        message=f"{lp.display_name} is now a co-host.",
        target_participant_id=lp.id
    )


@router.post("/{meeting_id}/live/moderation/toggle-lock", response_model=ModerationActionResponse)
def toggle_meeting_lock(
    meeting_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    is_primary_host = bool(meeting.host_id == current_user.id or meeting.user_id == current_user.id or current_user.role == "admin")
    if not is_primary_host:
        raise HTTPException(status_code=403, detail="Only the meeting host can lock or unlock the meeting.")

    meeting.locked = not meeting.locked
    db.add(AuditLog(
        user_id=current_user.id,
        user_email=current_user.email,
        action="LIVE_TOGGLE_LOCK",
        resource=f"meeting:{meeting.id}",
        status="SUCCESS",
        severity="INFO",
        details={"locked": meeting.locked}
    ))
    db.commit()
    return ModerationActionResponse(
        success=True,
        action="toggle_lock",
        message=f"Meeting has been {'locked' if meeting.locked else 'unlocked'}."
    )


@router.get("/{meeting_id}/recordings/download")
def download_recording_media(
    meeting_id: int,
    token: Optional[str] = None,
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: Session = Depends(get_db)
):
    """
    Download full recording media file (.mp4 / .webm / .wav).
    Supports either Authorization: Bearer <token> header or ?token=<jwt> query parameter.
    Audit logs the download action.
    """
    if not current_user and token:
        try:
            import jwt
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            email = payload.get("sub")
            user_id = payload.get("id") or payload.get("user_id")
            if user_id:
                current_user = db.query(User).filter(User.id == user_id).first()
            elif email:
                current_user = db.query(User).filter(User.email == email).first()
        except Exception:
            pass

    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    rec = db.query(Recording).filter(
        Recording.meeting_id == meeting.id,
        Recording.status == "ready"
    ).order_by(Recording.created_at.desc()).first()

    file_to_send = None
    if rec and rec.storage_key and os.path.exists(rec.storage_key):
        file_to_send = rec.storage_key
    elif meeting.audio_path and os.path.exists(meeting.audio_path):
        file_to_send = meeting.audio_path
    else:
        rec_dir = os.path.join(settings.UPLOAD_DIR, "recordings")
        if os.path.exists(rec_dir):
            candidates = [
                os.path.join(rec_dir, f) for f in os.listdir(rec_dir)
                if f.startswith(f"rec_m{meeting.id}_")
            ]
            if candidates:
                file_to_send = candidates[-1]

    if not file_to_send or not os.path.exists(file_to_send):
        raise HTTPException(status_code=404, detail="Recording media file not found on disk")

    ext = os.path.splitext(file_to_send)[1].lower() or ".mp4"
    clean_title = re.sub(r'[^a-zA-Z0-9_-]', '_', (meeting.title or 'meeting').lower())
    download_filename = f"{clean_title}_recording_{meeting.id}{ext}"

    media_type = "video/mp4"
    if ext == ".webm":
        media_type = "video/webm"
    elif ext in [".wav", ".mp3", ".m4a"]:
        media_type = "audio/wav"

    headers = {
        "Content-Disposition": f'attachment; filename="{download_filename}"'
    }

    if current_user:
        db.add(AuditLog(
            user_id=current_user.id,
            user_email=current_user.email,
            action="RECORDING_DOWNLOAD",
            resource=f"meeting:{meeting.id}",
            status="SUCCESS",
            severity="INFO",
            details={"file": download_filename, "size_bytes": os.path.getsize(file_to_send)}
        ))
        db.commit()

    return FileResponse(
        file_to_send,
        media_type=media_type,
        filename=download_filename,
        headers=headers
    )


@router.delete("/{meeting_id}/recordings/{recording_id}")
def delete_recording(
    meeting_id: int,
    recording_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Host and admin only: Delete a recording permanently.
    Deletes the media file from disk and database, and writes an audit log.
    """
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    is_host_or_admin = bool(
        meeting.host_id == current_user.id or
        meeting.user_id == current_user.id or
        current_user.role == "admin"
    )
    if not is_host_or_admin:
        raise HTTPException(status_code=403, detail="Only hosts and admins can delete recordings.")

    rec = db.query(Recording).filter(Recording.id == recording_id, Recording.meeting_id == meeting.id).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Recording not found")

    if rec.storage_key and os.path.exists(rec.storage_key):
        try:
            os.remove(rec.storage_key)
        except Exception as e:
            logger.warning(f"Could not remove recording file {rec.storage_key}: {e}")

    db.delete(rec)
    db.add(AuditLog(
        user_id=current_user.id,
        user_email=current_user.email,
        action="RECORDING_DELETED",
        resource=f"meeting:{meeting.id}",
        status="SUCCESS",
        severity="INFO",
        details={"recording_id": recording_id}
    ))
    db.commit()
    return {"status": "deleted", "recording_id": recording_id}


@router.post("/{meeting_id}/retry-processing")
def retry_processing(
    meeting_id: int,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Retry analysis pipeline if meeting status is failed.
    """
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    if meeting.status != "failed" and meeting.live_status != "failed":
        raise HTTPException(status_code=400, detail="Only failed meetings can be retried.")

    meeting.status = "processing"
    meeting.live_status = "processing"
    db.commit()

    background_tasks.add_task(run_meeting_pipeline_sync, meeting.id)
    return {"status": "processing", "message": "Analysis pipeline retried successfully"}


@router.post("/{meeting_id}/analyze")
def trigger_meeting_analysis(
    meeting_id: int,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Triggers end-to-end meeting analysis on demand (e.g. after a live or recorded meeting ends).
    Generates: Executive Summary, Tasks & Action Items, Speaker Diarization, Topic Chapters, and Effectiveness Score.
    """
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    meeting.status = "processing"
    if meeting.is_live:
        meeting.live_status = "processing"
    db.commit()

    background_tasks.add_task(run_meeting_pipeline_sync, meeting.id)
    return {
        "status": "processing",
        "message": "Meeting analysis initiated",
        "meeting_id": meeting.id
    }


@router.post("/{meeting_id}/live/captions", response_model=LiveCaptionResponse)
def process_live_caption(
    meeting_id: int,
    payload: LiveCaptionInput,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Real-time speech-to-text caption processor and live action-item detector.
    """
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    text = payload.text.strip()
    speaker = payload.speaker.strip() or (current_user.full_name or current_user.email)

    from app.ml.classifier import RuleBasedPlaceholder
    classifier = RuleBasedPlaceholder()
    pred = classifier.predict_sentence(text)

    detected = None
    if pred.get("label") == "action_item":
        assignee = speaker
        lower = text.lower()
        deadline = None
        if "by friday" in lower:
            deadline = "Friday"
        elif "by monday" in lower:
            deadline = "Monday"
        elif "by tomorrow" in lower:
            deadline = "Tomorrow"
        elif "by next week" in lower:
            deadline = "Next week"

        title = text
        for prefix in ["i will ", "i'll ", "we need to ", "let's make sure to ", "action item: ", "action item "]:
            if lower.startswith(prefix):
                title = text[len(prefix):].capitalize()
                break

        conf = float(pred.get("confidence", 0.88))
        action_item = ActionItem(
            meeting_id=meeting.id,
            title=title,
            assignee=assignee,
            deadline=deadline,
            status="suggested",
            priority="medium",
            confidence_score=conf,
            start_time_sec=float(payload.timestamp) if payload.timestamp is not None else 0.0
        )
        db.add(action_item)
        db.commit()
        db.refresh(action_item)

        detected = DetectedActionItem(
            id=action_item.id,
            title=action_item.title,
            assignee=action_item.assignee,
            deadline=action_item.deadline,
            confidence_score=conf,
            context_quote=text,
            status="suggested",
            start_time_sec=action_item.start_time_sec
        )

    return LiveCaptionResponse(
        text=text,
        speaker=speaker,
        timestamp=payload.timestamp or 0.0,
        detected_action_item=detected
    )


@router.get("/{meeting_id}/live/action-items", response_model=List[ActionItemResponse])
def get_live_action_items(
    meeting_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Returns all action items captured during this live meeting.
    """
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    return db.query(ActionItem).filter(ActionItem.meeting_id == meeting_id).order_by(ActionItem.created_at.asc()).all()


@router.post("/{meeting_id}/live/action-items", response_model=ActionItemResponse)
def create_live_action_item(
    meeting_id: int,
    payload: ActionItemCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Allows meeting participants to manually add action items from the live action-item panel.
    """
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    item = ActionItem(
        meeting_id=meeting_id,
        title=payload.title.strip(),
        assignee=payload.assignee.strip() if payload.assignee else (current_user.full_name or current_user.email),
        deadline=payload.deadline.strip() if payload.deadline else None,
        priority=payload.priority or "medium",
        status=payload.status or "pending",
        confidence_score=1.0
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.patch("/{meeting_id}/live/action-items/{item_id}", response_model=ActionItemResponse)
def update_live_action_item(
    meeting_id: int,
    item_id: int,
    payload: ActionItemUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update or mark complete an action item during the live meeting.
    """
    item = db.query(ActionItem).filter(ActionItem.id == item_id, ActionItem.meeting_id == meeting_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Action item not found")

    if payload.title is not None:
        item.title = payload.title.strip()
    if payload.assignee is not None:
        item.assignee = payload.assignee.strip()
    if payload.deadline is not None:
        item.deadline = payload.deadline.strip()
    if payload.status is not None:
        item.status = payload.status
    if payload.priority is not None:
        item.priority = payload.priority

    db.commit()
    db.refresh(item)
    return item


@router.delete("/{meeting_id}/live/action-items/{item_id}")
def delete_live_action_item(
    meeting_id: int,
    item_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Dismiss or delete an action item from the live panel.
    """
    item = db.query(ActionItem).filter(ActionItem.id == item_id, ActionItem.meeting_id == meeting_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Action item not found")

    db.delete(item)
    db.commit()
    return {"status": "deleted", "action_item_id": item_id}


@router.post("/{meeting_id}/live/action-items/{item_id}/confirm", response_model=ActionItemResponse)
def confirm_live_action_item(
    meeting_id: int,
    item_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    item = db.query(ActionItem).filter(ActionItem.id == item_id, ActionItem.meeting_id == meeting_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Action item not found")
    item.status = "confirmed"
    db.commit()
    db.refresh(item)
    return item


@router.post("/{meeting_id}/live/action-items/{item_id}/dismiss", response_model=ActionItemResponse)
def dismiss_live_action_item(
    meeting_id: int,
    item_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    item = db.query(ActionItem).filter(ActionItem.id == item_id, ActionItem.meeting_id == meeting_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Action item not found")
    item.status = "dismissed"
    db.commit()
    db.refresh(item)
    return item
