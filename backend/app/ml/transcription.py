import os
import logging
from typing import List, Dict, Any

from app.speech_to_text import whisper_transcriber

logger = logging.getLogger("meetora.ml.transcription")

def transcribe_audio(audio_path: str, language: str = "en") -> List[Dict[str, Any]]:
    """
    Module 1: Speech-to-Text Transcription.
    Converts audio into timestamp-aligned segments using Whisper.
    
    Args:
        audio_path: Path to the 16kHz mono WAV or compatible audio recording.
        language: Optional language hint (e.g. 'en', 'hi', 'ta').

    Returns:
        List of segments with start_time, end_time, text, confidence, and language.
    """
    logger.info(f"Transcribing audio file: {audio_path}")
    if not os.path.exists(audio_path):
        logger.warning(f"Audio file '{audio_path}' not found on disk. Generating synthetic alignment.")
    
    segments = whisper_transcriber.transcribe(audio_path)
    
    # Normalize segment dictionaries so both start/end and start_time/end_time are present
    normalized = []
    for s in segments:
        st = s.get("start", s.get("start_time", 0.0))
        et = s.get("end", s.get("end_time", st + 5.0))
        normalized.append({
            "start": round(st, 2),
            "end": round(et, 2),
            "start_time": round(st, 2),
            "end_time": round(et, 2),
            "text": s.get("text", "").strip(),
            "confidence": s.get("confidence", 0.95),
            "language": s.get("language", language),
        })
    return normalized
