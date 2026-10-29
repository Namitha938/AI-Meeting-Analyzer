"""
Meetora AI Machine Learning Pipeline Package
Submodules:
- transcribe / transcription: Whisper Speech-to-Text with timestamp alignment
- diarize / diarization: pyannote.audio speaker separation and timestamp-overlap merging
- classifier: Custom trained hybrid model & rule-based intent classifier
- extract / extraction: spaCy NER owner matching & dateparser deadline extraction
- summary / summarizer: Hierarchical summarization with KeyBERT key points
- sentiment / analytics: RoBERTa sentiment per speaker & diarization talk-time distribution
- pipeline: End-to-end composite ML workflow
"""

from app.ml.transcribe import transcribe
from app.ml.transcription import transcribe_audio
from app.ml.diarize import diarize, merge_speaker_turns
from app.ml.diarization import diarize_audio, merge_transcripts
from app.ml.classifier import predict, predict_one, classify_sentence, classify_batch, load_model
from app.ml.extract import extract_action_item, extract_actions
from app.ml.extraction import extract_action_items, extract_decisions
from app.ml.summary import hierarchical_summarize, extract_key_points_keybert
from app.ml.summarizer import generate_summary
from app.ml.sentiment import compute_full_analytics, compute_speaker_sentiments, compute_speaker_talk_times
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
    "extract_action_item",
    "extract_actions",
    "extract_action_items",
    "extract_decisions",
    "hierarchical_summarize",
    "extract_key_points_keybert",
    "generate_summary",
    "compute_full_analytics",
    "compute_speaker_sentiments",
    "compute_speaker_talk_times",
    "compute_analytics",
    "run_ml_pipeline",
]
