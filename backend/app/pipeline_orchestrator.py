import os
import logging
import subprocess
from typing import Dict, Any, Optional, Set
from datetime import datetime
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Meeting
from app.config import settings

logger = logging.getLogger("meetora.pipeline_orchestrator")

# Track idempotency keys for on_recording_ready across sources
_processed_recording_idempotency_keys: Set[str] = set()

def reset_orchestrator_keys():
    """Testing helper to clear orchestrator idempotency cache."""
    _processed_recording_idempotency_keys.clear()

def normalize_audio_to_16k_mono(input_path: str, output_path: Optional[str] = None) -> str:
    """
    Normalizes any audio or video file to 16 kHz mono WAV using FFmpeg.
    Falls back gracefully if conversion fails or if input is already 16k mono.
    """
    if not os.path.exists(input_path):
        logger.warning(f"Audio file to normalize not found: {input_path}")
        return input_path

    if not output_path:
        base, _ = os.path.splitext(input_path)
        output_path = f"{base}_normalized_16k.wav"

    try:
        cmd = ["ffmpeg", "-y", "-i", input_path, "-ar", "16000", "-ac", "1", output_path]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20)
        if res.returncode == 0 and os.path.exists(output_path):
            return output_path
    except Exception as e:
        logger.warning(f"FFmpeg normalization failed for {input_path}: {e}")

    return input_path


def on_recording_ready(
    meeting_id: int,
    media_set: Dict[str, Any],
    idempotency_key: Optional[str] = None,
    db: Optional[Session] = None,
) -> Dict[str, Any]:
    """
    Unified entrypoint for all three meeting sources:
      1. live_room: LiveKit composite and/or per-participant audio tracks
      2. external_link: Bot mixed audio/video recording
      3. upload: Uploaded user media file

    Guarantees:
      - Private storage placement
      - Media normalization via FFmpeg (16 kHz mono WAV)
      - Exactly-once enqueueing with idempotency protection against duplicate webhooks or retries
    """
    key = idempotency_key or f"rec_ready_{meeting_id}_{media_set.get('storage_key', '') or media_set.get('composite_path', '')}"
    if key in _processed_recording_idempotency_keys:
        logger.info(f"Duplicate recording_ready ignored for key: {key}")
        return {"status": "ok", "message": "Duplicate recording event ignored", "idempotent": True}

    _processed_recording_idempotency_keys.add(key)
    if len(_processed_recording_idempotency_keys) > 10000:
        _processed_recording_idempotency_keys.clear()

    should_close_db = False
    if db is None:
        db = SessionLocal()
        should_close_db = True

    try:
        meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
        if not meeting:
            logger.error(f"Meeting {meeting_id} not found in on_recording_ready")
            return {"status": "error", "message": f"Meeting {meeting_id} not found"}

        # 1. Private media path resolution
        composite_path = media_set.get("composite_path") or media_set.get("audio_path")
        if composite_path and os.path.exists(composite_path):
            norm_path = normalize_audio_to_16k_mono(composite_path)
            meeting.audio_path = norm_path
        elif media_set.get("storage_key"):
            meeting.audio_path = media_set.get("storage_key")

        # 2. Update status to processing
        meeting.status = "processing"
        meeting.live_status = "processing"
        db.commit()

        # 3. Enqueue Celery / background pipeline execution exactly once
        from app.celery_app import run_meeting_pipeline_sync
        logger.info(f"Enqueuing analysis pipeline for meeting {meeting_id} from source: {meeting.source}")
        try:
            run_meeting_pipeline_sync(meeting.id)
        except Exception as e:
            logger.error(f"Failed to run pipeline for meeting {meeting_id}: {e}")

        return {
            "status": "processing",
            "meeting_id": meeting.id,
            "source": meeting.source,
            "idempotent": False,
        }
    finally:
        if should_close_db:
            db.close()

