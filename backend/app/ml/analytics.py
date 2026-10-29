"""
Module 6 / Step 12: Conversational Analytics Engine
Delegates to Step 12 sentiment.py (RoBERTa sentiment per segment and per speaker,
and talk-time distribution computed directly from diarization timestamps).
"""

import logging
from typing import List, Dict, Any, Optional

from app.ml.sentiment import (
    compute_full_analytics,
    compute_speaker_talk_times,
    compute_speaker_sentiments,
    analyze_segment_sentiment,
)

logger = logging.getLogger("meetora.ml.analytics")


def compute_analytics(
    transcripts: List[Dict[str, Any]],
    actions: Optional[List[Dict[str, Any]]] = None,
    decisions: Optional[List[Dict[str, Any]]] = None,
    participants: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Step 12: Calculates RoBERTa sentiment per speaker, diarization talk-time distribution,
    topic segmentation, and meeting effectiveness.
    """
    logger.info(f"Computing Step 12 conversational analytics on {len(transcripts)} utterances.")
    return compute_full_analytics(
        transcripts=transcripts,
        actions=actions or [],
        decisions=decisions or [],
        participants=participants,
    )
