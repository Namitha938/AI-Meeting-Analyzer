"""
Meetora AI Machine Learning Pipeline Package
Submodules:
- transcribe / transcription: Whisper Speech-to-Text with timestamp alignment
- diarize / diarization: pyannote.audio speaker separation and timestamp-overlap merging
- classifier: Custom trained hybrid model & rule-based intent classifier
- extraction: Named Entity Recognition & rule-based action/decision extraction
- summarizer: Executive summary generation with takeaways & next steps
- analytics: Talk-time distribution, sentiment scoring, and topic chapters
- pipeline: End-to-end composite ML workflow
"""

from app.ml.transcribe import transcribe
from app.ml.transcription import transcribe_audio
from app.ml.diarize import diarize, merge_speaker_turns
from app.ml.diarization import diarize_audio, merge_transcripts
from app.ml.classifier import predict, predict_one, classify_sentence, classify_batch, load_model
from app.ml.extraction import extract_action_items, extract_decisions
from app.ml.summarizer import generate_summary
from app.ml.analytics import compute_analytics
from app.ml.pipeline import run_ml_pipeline

__all__ = [
    "transcribe",
    "transcribe_audio",
    "diarize",
    "diarize_audio",
    "merge_speaker_turns",
    "merge_transcripts",
    "predict",
    "predict_one",
    "load_model",
    "classify_sentence",
    "classify_batch",
    "extract_action_items",
    "extract_decisions",
    "generate_summary",
    "compute_analytics",
    "run_ml_pipeline",
]
