import os
import shutil
import subprocess
import logging
import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.config import settings
from app.database import get_db
from app.storage import get_storage
from app.models import (
    User, Meeting, Transcript, Summary, ActionItem, Decision,
    Comment, MeetingAnalytics, HumanCorrection, MeetingShare
)
from app.schemas import (
    MeetingResponse, MeetingDetailResponse, MeetingStatusResponse,
    TranscriptItem, SummaryResponse, ActionItemResponse, DecisionResponse,
    AnalyticsResponse, CommentCreate, CommentResponse, RenameSpeakerRequest,
    MeetingChatRequest, MeetingChatResponse, TranslationRequest, TranslationResponse,
    BulkDeleteRequest, BulkDeleteResponse, BulkDeleteFailure,
    MeetingUpdateRequest, SummaryUpdateRequest, TranscriptLineUpdateRequest
)
from app.search_vector import answer_meeting_rag, vector_search_service, format_seconds_to_ts
from app.nlp_analysis import MeetingAnalyticsEngine
from app.speech_to_text import translate_transcript_text
from app.auth import get_current_user
from app.celery_app import run_meeting_pipeline_sync
from app.speech_to_text import format_timestamp

logger = logging.getLogger("meetora.meetings")

router = APIRouter(prefix="/meetings", tags=["Meetings"])

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

@router.post("", response_model=MeetingResponse, status_code=status.HTTP_201_CREATED)
async def create_and_upload_meeting(
    background_tasks: BackgroundTasks,
    title: str = Form(...),
    participants: Optional[str] = Form("Sarah Kim, Marcus Lee, Jordan Davis"),
    tags: Optional[str] = Form("Product, Q3, Planning"),
    color: Optional[str] = Form("violet"),
    file: Optional[UploadFile] = File(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
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

    part_list = [p.strip() for p in participants.split(",") if p.strip()] if participants else []
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []

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
    )
    db.add(meeting)
    db.commit()
    db.refresh(meeting)

    # Trigger background AI pipeline
    background_tasks.add_task(run_meeting_pipeline_sync, meeting.id)

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
    return meeting.action_items

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


@router.post("/chat", response_model=MeetingChatResponse)
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


@router.post("/{meeting_id}/chat", response_model=MeetingChatResponse)
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
