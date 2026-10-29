"""
Module 2 / Step 9: Speaker Diarization Wrapper
Provides backward compatibility with the modular pipeline while delegating
to the Step 9 diarize.py implementation.
"""

from typing import List, Dict, Any, Optional
from app.ml.diarize import diarize, merge_speaker_turns

def diarize_audio(audio_path: str, num_speakers: int = 3) -> List[Dict[str, Any]]:
    """Identifies speaker turn intervals using pyannote.audio or acoustic clustering."""
    return diarize(audio_path, num_speakers=num_speakers)

def merge_transcripts(
    whisper_segments: List[Dict[str, Any]],
    diarization_intervals: List[Dict[str, Any]],
    known_participants: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """Merges Whisper segments with speaker turns by timestamp overlap."""
    participants = known_participants or ["Sarah Kim", "Marcus Lee", "Jordan Davis"]
    return merge_speaker_turns(
        whisper_segments,
        diarization_intervals,
        known_participants=participants,
    )
