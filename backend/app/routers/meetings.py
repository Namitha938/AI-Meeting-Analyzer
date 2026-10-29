import os
import shutil
import subprocess
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, BackgroundTasks
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.storage import get_storage
from app.models import User, Meeting, Transcript, Summary, ActionItem, Decision, Comment, MeetingAnalytics
from app.schemas import (
    MeetingResponse, MeetingDetailResponse, MeetingStatusResponse,
    TranscriptItem, SummaryResponse, ActionItemResponse, DecisionResponse,
    AnalyticsResponse, CommentCreate, CommentResponse, RenameSpeakerRequest,
    MeetingChatRequest, MeetingChatResponse, TranslationRequest, TranslationResponse
)
from app.search_vector import answer_meeting_rag
from app.nlp_analysis import MeetingAnalyticsEngine
from app.speech_to_text import translate_transcript_text
from app.auth import get_current_user
from app.celery_app import run_meeting_pipeline_sync
from app.speech_to_text import format_timestamp

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

    if meeting.audio_path:
        storage = get_storage()
        storage.delete_file(meeting.audio_path)

    db.delete(meeting)
    db.commit()
    return None

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
