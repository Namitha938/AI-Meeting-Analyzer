import os
import time
import logging
import datetime
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

# Step 10: Load trained classifier model once at worker process startup
try:
    from celery.signals import worker_process_init

    @worker_process_init.connect
    def on_worker_init(**kwargs):
        """Pre-load saved_model classifier once at Celery worker startup."""
        try:
            from app.ml.classifier import load_model
            load_model()
            logger.info("Step 10: Classifier model successfully initialized on Celery worker startup.")
        except Exception as err:
            logger.warning(f"Error loading classifier on worker startup: {err}")
except Exception:
    pass


@celery_app.task(name="send_deadline_reminders_task")
def send_deadline_reminders_task():
    """
    Periodic Celery Beat worker task.
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
    Step 13: End-to-End AI Meeting Processing Pipeline.
    Calls Steps 8 to 12 in order inside process_meeting:
      - Step 8:  faster-whisper small model speech-to-text
      - Step 9:  pyannote.audio speaker diarization & timestamp-overlap merging
      - Step 10: Trained hybrid sentence classifier
      - Step 11: Action item extraction (spaCy NER owner matching + dateparser deadline)
      - Step 12: Hierarchical summarization, KeyBERT key points, RoBERTa sentiment, talk-time
    Saves all results to the database and marks status as completed.
    Each stage is wrapped in try/except so any failure marks meeting as failed with clear error message.
    """
    from app.database import SessionLocal
    from app.models import Meeting, Transcript, Summary, ActionItem, Decision, MeetingAnalytics

    # Import pipeline stages
    from app.ml.transcribe import transcribe
    from app.ml.diarize import diarize, merge_speaker_turns
    from app.ml.classifier import predict
    from app.ml.extract import extract_actions
    from app.ml.extraction import extract_decisions
    from app.ml.summary import hierarchical_summarize
    from app.ml.sentiment import compute_full_analytics

    db = SessionLocal()
    current_stage = "initializing"

    try:
        meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
        if not meeting:
            raise ValueError(f"Meeting {meeting_id} does not exist in database.")

        audio_path = meeting.audio_path or "uploads/sample_meeting_16k_mono.wav"
        participants = meeting.participants or ["Sarah Kim", "Marcus Lee", "Jordan Davis"]

        # =========================================================================
        # Stage 1 (Step 8): Transcription with faster-whisper small model
        # =========================================================================
        current_stage = "transcribing"
        meeting.status = "transcribing"
        db.commit()
        logger.info(f"[Step 8] Transcribing audio for meeting {meeting_id}: {audio_path}")

        try:
            whisper_segments = transcribe(audio_path, model_size="small")
            if not whisper_segments:
                raise RuntimeError("Transcription returned empty segment list.")
        except Exception as stt_err:
            raise RuntimeError(f"Step 8 Transcription Stage Failed: {stt_err}") from stt_err

        # =========================================================================
        # Stage 2 (Step 9): Speaker Diarization & Timestamp-Overlap Merging
        # =========================================================================
        current_stage = "diarizing"
        meeting.status = "diarizing"
        db.commit()
        logger.info(f"[Step 9] Diarizing audio for meeting {meeting_id}")

        try:
            speaker_turns = diarize(audio_path, num_speakers=len(participants))
            merged_transcripts = merge_speaker_turns(
                transcript=whisper_segments,
                speaker_turns=speaker_turns,
                known_participants=participants,
            )
        except Exception as diarize_err:
            raise RuntimeError(f"Step 9 Diarization Stage Failed: {diarize_err}") from diarize_err

        # =========================================================================
        # Stage 3 (Step 10): Trained Classifier (Sentence Intent Classification)
        # =========================================================================
        current_stage = "classifying"
        meeting.status = "analyzing"
        db.commit()
        logger.info(f"[Step 10] Running sentence intent classifier on {len(merged_transcripts)} lines")

        try:
            sentences = [item["text"] for item in merged_transcripts]
            class_preds = predict(sentences)

            for item, pred in zip(merged_transcripts, class_preds):
                item["top_class"] = pred["label"]
                item["confidence"] = pred["confidence"]
                item["is_action_item"] = (pred["label"] == "action_item")
        except Exception as cls_err:
            raise RuntimeError(f"Step 10 Classifier Stage Failed: {cls_err}") from cls_err

        # Save merged transcripts with speaker, timestamp, and action tags
        db.query(Transcript).filter(Transcript.meeting_id == meeting.id).delete()
        for item in merged_transcripts:
            tr = Transcript(
                meeting_id=meeting.id,
                speaker=item["speaker"],
                start_time=item["start_time"],
                end_time=item["end_time"],
                text=item["text"],
                is_action_item=item.get("is_action_item", False),
                confidence=item.get("confidence", 0.95),
            )
            db.add(tr)
        db.commit()

        # =========================================================================
        # Stage 4 (Step 11): Action Item & Decision Extraction (spaCy NER + dateparser)
        # =========================================================================
        current_stage = "extracting"
        logger.info(f"[Step 11] Extracting action items & decisions for meeting {meeting_id}")

        try:
            actions_data = extract_actions(
                merged_transcripts,
                candidate_speakers=participants,
            )
            decisions_data = extract_decisions(merged_transcripts)

            db.query(ActionItem).filter(ActionItem.meeting_id == meeting.id).delete()
            for act in actions_data:
                ai = ActionItem(
                    meeting_id=meeting.id,
                    title=act["title"],
                    assignee=act["owner"],
                    deadline=act["deadline"],
                    status="pending",
                    priority=act.get("priority", "medium"),
                    confidence_score=act.get("confidence_score", 0.92),
                    needs_review=act.get("confidence_score", 0.92) < 0.80,
                    start_time_sec=act.get("start_time_sec"),
                    source_segment_id=act.get("source_segment_id"),
                )
                db.add(ai)

            db.query(Decision).filter(Decision.meeting_id == meeting.id).delete()
            for dec in decisions_data:
                dc = Decision(
                    meeting_id=meeting.id,
                    decision_text=dec["decision_text"],
                    category=dec.get("category", "General"),
                    rationale=dec.get("rationale", "Meeting consensus outcome"),
                    start_time_sec=dec.get("start_time_sec"),
                    source_segment_id=dec.get("source_segment_id"),
                )
                db.add(dc)
            db.commit()
        except Exception as ext_err:
            raise RuntimeError(f"Step 11 Extraction Stage Failed: {ext_err}") from ext_err

        # =========================================================================
        # Stage 5 (Step 12): Summary, Key Points (KeyBERT), Sentiment & Talk-Time
        # =========================================================================
        current_stage = "summarizing_and_analytics"
        logger.info(f"[Step 12] Generating hierarchical summary & RoBERTa analytics")

        try:
            summary_res = hierarchical_summarize(
                merged_transcripts,
                title=meeting.title,
                decisions=decisions_data,
            )

            existing_summary = db.query(Summary).filter(Summary.meeting_id == meeting.id).first()
            if existing_summary and getattr(existing_summary, "edited_by_user", False):
                logger.info(f"Summary for meeting {meeting.id} has human edits; preserving human edits during pipeline re-run.")
            else:
                db.query(Summary).filter(Summary.meeting_id == meeting.id).delete()
                summary_rec = Summary(
                    meeting_id=meeting.id,
                    overview=summary_res["overview"],
                    key_takeaways=summary_res["key_takeaways"],
                    next_steps=summary_res["next_steps"],
                    model_version=summary_res.get("model_version", "hierarchical-bart-flan-v2"),
                )
                db.add(summary_rec)

            analytics_res = compute_full_analytics(
                transcripts=merged_transcripts,
                actions=actions_data,
                decisions=decisions_data,
                participants=participants,
            )

            db.query(MeetingAnalytics).filter(MeetingAnalytics.meeting_id == meeting.id).delete()
            analytics_rec = MeetingAnalytics(
                meeting_id=meeting.id,
                sentiment_score=analytics_res["sentiment_score"],
                talk_to_listen_ratio=analytics_res["talk_to_listen_ratio"],
                total_topics=analytics_res["total_topics"],
                speaking_time_distribution=analytics_res["speaking_time_distribution"],
                topic_chapters=analytics_res["topic_chapters"],
                effectiveness_score=analytics_res["effectiveness_score"],
                effectiveness_breakdown=analytics_res["effectiveness_breakdown"],
            )
            db.add(analytics_rec)
            db.commit()
        except Exception as sum_err:
            raise RuntimeError(f"Step 12 Summary & Sentiment Stage Failed: {sum_err}") from sum_err

        # =========================================================================
        # Stage 6: Completed & Effectiveness Scoring
        # =========================================================================
        try:
            from app.ml.effectiveness import compute_effectiveness
            eff_result = compute_effectiveness(
                segments=merged_transcripts,
                action_items=actions_data,
                agenda_text=meeting.description or meeting.title,
            )
            if eff_result:
                meeting.effectiveness_score = eff_result["score"]
                meeting.effectiveness_pillars = eff_result["pillars"]
        except Exception as eff_err:
            logger.warning(f"Error computing meeting effectiveness: {eff_err}")

        final_duration = 300  # Default 5-minute meeting length
        if merged_transcripts:
            final_duration = int(max(t["end_time"] for t in merged_transcripts))

        meeting.duration_seconds = final_duration
        meeting.status = "completed"
        if meeting.is_live:
            meeting.live_status = "completed"
        db.commit()

        # Step Phase 2: Send notifications and emails to all attendees upon processing completion
        try:
            from app.models import Notification, LiveParticipant
            attendee_ids = set()
            if meeting.user_id:
                attendee_ids.add(meeting.user_id)
            if meeting.host_id:
                attendee_ids.add(meeting.host_id)
            for part in (meeting.live_participants or []):
                if part.user_id:
                    attendee_ids.add(part.user_id)

            for uid in attendee_ids:
                notif = Notification(
                    user_id=uid,
                    title="Meeting Analysis Ready",
                    message=f"The recording and summary for '{meeting.title}' is now available.",
                    type="meeting",
                    read=False
                )
                db.add(notif)
            db.commit()

            owner = meeting.owner
            if owner and owner.email:
                from app.email_sender import send_smtp_email
                email_body = f"Hello {owner.full_name or 'there'},\n\nYour meeting '{meeting.title}' has been successfully analyzed by Meetora.\nView the full summary, action items, and effectiveness score inside Meetora."
                send_smtp_email([owner.email], f"Meetora Analysis Ready: {meeting.title}", email_body)
        except Exception as notif_err:
            logger.warning(f"Attendee notification warning: {notif_err}")
        logger.info(f"Successfully processed meeting {meeting_id} through all Steps 8-12!")

        return {
            "status": "completed",
            "meeting_id": meeting_id,
            "transcripts_count": len(merged_transcripts),
            "actions_count": len(actions_data),
            "decisions_count": len(decisions_data),
            "duration_seconds": final_duration,
        }

    except Exception as e:
        error_msg = f"Meeting pipeline failed at stage '{current_stage}': {str(e)}"
        logger.error(error_msg, exc_info=True)
        db.rollback()

        meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
        if meeting:
            meeting.status = "failed"
            # Annotate tags with clear failure context
            existing_tags = list(meeting.tags or [])
            meeting.tags = existing_tags + [f"error:{current_stage}"]
            db.commit()

        return {
            "status": "failed",
            "meeting_id": meeting_id,
            "failed_stage": current_stage,
            "error": str(e),
        }
    finally:
        db.close()


@celery_app.task(name="process_meeting")
@celery_app.task(name="app.celery_app.process_meeting")
def process_meeting(meeting_id: int):
    """Celery background worker entry point for process_meeting."""
    return run_meeting_pipeline_sync(meeting_id)


@celery_app.task(name="process_meeting_audio_task")
def process_meeting_audio_task(meeting_id: int, audio_path: str = None):
    """Celery worker task invoked when recording is ready."""
    return run_meeting_pipeline_sync(meeting_id)



@celery_app.task(name="cleanup_expired_recordings_task")
def cleanup_expired_recordings_task(retention_days: int = None):
    """
    Retention: auto-delete video/audio recording media files older than RECORDING_RETENTION_DAYS (default 30)
    while strictly keeping transcript, summary, and action items intact.
    Writes an audit log entry for the purge.
    """
    days = retention_days if retention_days is not None else getattr(settings, "RECORDING_RETENTION_DAYS", 30)
    cutoff = datetime.datetime.utcnow() - datetime.timedelta(days=days)
    from app.database import SessionLocal
    db = SessionLocal()
    purged_count = 0
    try:
        from app.models import Recording, AuditLog
        expired_recs = db.query(Recording).filter(
            Recording.created_at < cutoff,
            Recording.status != "expired"
        ).all()
        for rec in expired_recs:
            if rec.storage_key and os.path.exists(rec.storage_key):
                try:
                    os.remove(rec.storage_key)
                except Exception as e:
                    logger.warning(f"Retention file removal error: {e}")
            rec.status = "expired"
            purged_count += 1
            db.add(AuditLog(
                user_id=None,
                user_email="system@meetora.ai",
                action="RECORDING_RETENTION_PURGE",
                resource=f"meeting:{rec.meeting_id}",
                status="SUCCESS",
                severity="INFO",
                details={"recording_id": rec.id, "retention_days": days}
            ))
        db.commit()
        logger.info(f"Retention purge task finished: cleaned {purged_count} expired recordings.")
        return {"purged_count": purged_count, "retention_days": days}
    finally:
        db.close()


@celery_app.task(name="trigger_meeting_bot_task")
def trigger_meeting_bot_task(meeting_id: int):
    """
    Celery task to automatically dispatch the AI notetaker bot to an external meeting.
    Runs 1 minute before scheduled start time.
    """
    from app.database import SessionLocal
    from app.models import Meeting, AuditLog
    from app.bot_providers import get_bot_provider, validate_meeting_url
    import asyncio

    db = SessionLocal()
    try:
        meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
        if not meeting:
            logger.error(f"Meeting {meeting_id} not found for trigger_meeting_bot_task")
            return {"status": "error", "message": f"Meeting {meeting_id} not found"}

        if meeting.source != "external_link" or not meeting.auto_join or not meeting.consent_confirmed:
            logger.info(f"Bot auto-join skipped for meeting {meeting_id}: conditions not met")
            return {"status": "skipped", "message": "Auto-join disabled or consent missing"}

        if meeting.bot_status in ["recording", "completed", "cancelled", "removed"]:
            logger.info(f"Bot auto-join skipped for meeting {meeting_id}: status={meeting.bot_status}")
            return {"status": "skipped", "message": f"Already in status {meeting.bot_status}"}

        valid, plat, err = validate_meeting_url(meeting.meeting_link or "")
        if not valid:
            meeting.bot_status = "failed"
            meeting.bot_error = err
            db.commit()
            return {"status": "failed", "error": err}

        provider = get_bot_provider(meeting.bot_provider)
        try:
            res = asyncio.run(provider.join(meeting.id, meeting.meeting_link, getattr(settings, "BOT_NAME", "Meetora Notetaker (recording)")))
            meeting.bot_id = res.get("bot_id")
            meeting.bot_status = res.get("status", "joining")
            meeting.bot_error = None
            db.add(AuditLog(
                user_id=meeting.user_id,
                user_email="bot@meetora.ai",
                action="BOT_REQUESTED",
                resource=f"meeting:{meeting_id}",
                status="SUCCESS",
                severity="INFO",
                details={"bot_id": meeting.bot_id, "provider": meeting.bot_provider, "auto": True}
            ))
            db.commit()
            return {"status": "dispatched", "bot_id": meeting.bot_id}
        except Exception as e:
            meeting.bot_status = "failed"
            meeting.bot_error = str(e)
            db.commit()
            return {"status": "failed", "error": str(e)}
    finally:
        db.close()


def schedule_meeting_bot(meeting_id: int, scheduled_at: datetime.datetime):
    """
    Schedules the bot trigger 1 minute before scheduled_at.
    """
    try:
        now = datetime.datetime.utcnow()
        eta = scheduled_at - datetime.timedelta(minutes=1)
        if eta < now:
            trigger_meeting_bot_task.apply_async(args=[meeting_id])
        else:
            trigger_meeting_bot_task.apply_async(args=[meeting_id], eta=eta)
        logger.info(f"Scheduled meeting bot for meeting {meeting_id} at {eta}")
    except Exception as e:
        logger.warning(f"Could not enqueue scheduled meeting bot: {e}")
