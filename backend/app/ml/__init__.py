"""
Meetora AI Machine Learning Pipeline Package
Submodules:
- transcription: Whisper Speech-to-Text with timestamp alignment
- diarization: Speaker separation and utterance merging
- classifier: Custom DistilBERT / Softmax sentence intent classification
- extraction: Named Entity Recognition & rule-based action/decision extraction
- summarizer: Executive summary generation with takeaways & next steps
- analytics: Talk-time distribution, sentiment scoring, and topic chapters
- pipeline: End-to-end composite ML workflow
"""

from app.ml.transcribe import transcribe
from app.ml.transcription import transcribe_audio
from app.ml.diarization import diarize_audio, merge_transcripts
from app.ml.classifier import classify_sentence, classify_batch
from app.ml.extraction import extract_action_items, extract_decisions
from app.ml.summarizer import generate_summary
from app.ml.analytics import compute_analytics
from app.ml.pipeline import run_ml_pipeline

__all__ = [
    "transcribe",
    "transcribe_audio",
    "diarize_audio",
    "merge_transcripts",
    "classify_sentence",
    "classify_batch",
    "extract_action_items",
    "extract_decisions",
    "generate_summary",
    "compute_analytics",
    "run_ml_pipeline",
]

