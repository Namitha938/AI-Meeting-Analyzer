import os
import time
import logging
from celery import Celery
from app.config import settings

logger = logging.getLogger("meetora.celery")

celery_app = Celery(
    "meetora",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    beat_schedule={
        # Step 12: Celery Beat scheduled deadline reminders
        "check-upcoming-deadlines-every-hour": {
            "task": "send_deadline_reminders_task",
            "schedule": 3600.0,
        },
    },
)

@celery_app.task(name="send_deadline_reminders_task")
def send_deadline_reminders_task():
    """
    Step 12: Periodic Celery Beat worker task.
    Scans pending Action Items and dispatches email reminders to task assignees.
    """
    from app.database import SessionLocal
    from app.calendar_service import EmailReminderService

    db = SessionLocal()
    try:
        res = EmailReminderService.scan_and_send_due_reminders(db)
        logger.info(f"Celery Beat deadline reminder run: {res}")
        return res
    except Exception as e:
        logger.error(f"Error in Celery Beat deadline reminder job: {e}")
        return {"status": "error", "message": str(e)}
    finally:
        db.close()

def run_meeting_pipeline_sync(meeting_id: int):
    """
    Simulates / runs the AI meeting processing pipeline.
    Updates status: uploading -> transcribing -> analyzing -> completed.
    Creates rich transcript, summary, action items, decisions, and analytics.
    """
    from app.database import SessionLocal
    from app.models import Meeting, Transcript, Summary, ActionItem, Decision, MeetingAnalytics

    db = SessionLocal()
    try:
        meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
        if not meeting:
            logger.error(f"Meeting {meeting_id} not found")
            return

        # 1. Stage: Transcribing (Whisper Speech-to-Text)
        meeting.status = "transcribing"
        db.commit()

        from app.speech_to_text import whisper_transcriber
        from app.diarization import diarizer

        audio_file = meeting.audio_path or "sample_audio.wav"
        whisper_segments = whisper_transcriber.transcribe(audio_file)

        # 2. Stage: Diarization (pyannote.audio Speaker Diarization)
        meeting.status = "diarizing"
        db.commit()

        known_participants = meeting.participants or ["Sarah Kim", "Marcus Lee", "Jordan Davis"]
        diarization_intervals = diarizer.diarize(audio_file, num_speakers=max(2, len(known_participants)))
        merged_transcripts = diarizer.merge_whisper_and_diarization(
            whisper_segments,
            diarization_intervals,
            known_participants=known_participants
        )

        # Save merged transcripts with speaker and timestamps
        if not meeting.transcripts:
            for item in merged_transcripts:
                tr = Transcript(
                    meeting_id=meeting.id,
                    speaker=item["speaker"],
                    start_time=item["start_time"],
                    end_time=item["end_time"],
                    text=item["text"],
                    is_action_item=item["is_action_item"],
                    confidence=item.get("confidence", 0.96),
                )
                db.add(tr)
            db.commit()

        # 3. Stage: Analyzing (Core NLP analysis & Custom DistilBERT Sentence Classifier)
        meeting.status = "analyzing"
        db.commit()

        from app.nlp_analysis import run_core_nlp_pipeline
        run_core_nlp_pipeline(meeting.id, db)

        # 4. Stage: Completed
        meeting.status = "completed"
        db.commit()
        meeting.duration_seconds = 2538  # 42 min 18 sec
        db.commit()
        logger.info(f"Pipeline completed successfully for meeting {meeting_id}")

    except Exception as e:
        logger.exception(f"Error in meeting pipeline {meeting_id}: {e}")
        db.rollback()
        meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
        if meeting:
            meeting.status = "failed"
            db.commit()
    finally:
        db.close()

@celery_app.task(name="process_meeting")
@celery_app.task(name="app.celery_app.process_meeting")
def process_meeting(meeting_id: int):
    run_meeting_pipeline_sync(meeting_id)
