import logging
from typing import List, Dict, Any

from app.diarization import diarizer

logger = logging.getLogger("meetora.ml.diarization")

def diarize_audio(audio_path: str, num_speakers: int = 3) -> List[Dict[str, Any]]:
    """
    Module 2: Speaker Diarization.
    Identifies speaker turn intervals ('who spoke when') using pyannote.audio.

    Args:
        audio_path: Path to the audio file.
        num_speakers: Expected number of distinct speakers.

    Returns:
        List of turn intervals: [{'speaker': 'Speaker 1', 'start': 0.0, 'end': 14.5}, ...]
    """
    logger.info(f"Diarizing audio: {audio_path} (num_speakers={num_speakers})")
    return diarizer.diarize(audio_path, num_speakers=num_speakers)

def merge_transcripts(
    whisper_segments: List[Dict[str, Any]],
    diarization_intervals: List[Dict[str, Any]],
    known_participants: List[str] = None,
) -> List[Dict[str, Any]]:
    """
    Merges Whisper text segments with speaker diarization turns based on timestamp overlap.

    Args:
        whisper_segments: Output from transcribe_audio().
        diarization_intervals: Output from diarize_audio().
        known_participants: Optional team member names (e.g. ['Sarah Kim', 'Marcus Lee']).

    Returns:
        Combined transcript items with speaker, start_time, end_time, text, is_action_item.
    """
    participants = known_participants or ["Sarah Kim", "Marcus Lee", "Jordan Davis"]
    return diarizer.merge_whisper_and_diarization(
        whisper_segments,
        diarization_intervals,
        known_participants=participants,
    )

