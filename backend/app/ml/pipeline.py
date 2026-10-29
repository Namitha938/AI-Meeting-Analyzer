import logging
from typing import Dict, Any, Optional

from app.ml.transcription import transcribe_audio
from app.ml.diarization import diarize_audio, merge_transcripts
from app.ml.classifier import classify_sentence
from app.ml.extraction import extract_action_items, extract_decisions
from app.ml.summarizer import generate_summary
from app.ml.analytics import compute_analytics

logger = logging.getLogger("meetora.ml.pipeline")

def run_ml_pipeline(meeting_id: int, audio_path: str, db: Optional[Any] = None) -> Dict[str, Any]:
    """
    Composite Machine Learning Pipeline (Part B):
    Plugs directly into the Step 5 background Celery task.

    Pipeline Steps:
    1. Whisper Speech-to-Text transcription with aligned timestamps.
    2. pyannote.audio speaker diarization and turn merging.
    3. Custom DistilBERT / Softmax sentence intent classification.
    4. Action item extraction, assignee inference, and deadline normalization.
    5. Strategic decision categorization and rationale recording.
    6. Executive summary generation with key takeaways and next steps.
    7. Speaker talk-time distribution, sentiment scoring, and topic chapters.

    Args:
        meeting_id: Target database meeting ID.
        audio_path: Path to the recorded audio file.
        db: Optional active SQLAlchemy database session to persist results.

    Returns:
        Structured dictionary containing full processed meeting intelligence.
    """
    logger.info(f"=== Starting ML Pipeline for Meeting #{meeting_id} ===")

    # Step 1: Transcribe
    raw_segments = transcribe_audio(audio_path)

    # Step 2: Diarize & Merge
    diarization_turns = diarize_audio(audio_path, num_speakers=3)
    merged_transcripts = merge_transcripts(raw_segments, diarization_turns)

    # Step 3 & 4: Intent Classification & Extraction
    action_items = extract_action_items(merged_transcripts)
    decisions = extract_decisions(merged_transcripts)

    # Step 5: Summary Generation
    meeting_title = f"Meeting #{meeting_id}"
    summary_data = generate_summary(meeting_title, merged_transcripts, decisions)

    # Step 6: Analytics & Speaker Participation
    analytics_data = compute_analytics(merged_transcripts, action_items, decisions)

    logger.info(f"=== ML Pipeline completed for Meeting #{meeting_id}: "
                f"{len(merged_transcripts)} transcripts, {len(action_items)} actions, {len(decisions)} decisions ===")

    return {
        "meeting_id": meeting_id,
        "transcripts": merged_transcripts,
        "action_items": action_items,
        "decisions": decisions,
        "summary": summary_data,
        "analytics": analytics_data,
    }

