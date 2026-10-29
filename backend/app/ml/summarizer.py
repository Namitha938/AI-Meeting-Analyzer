"""
Module 5 / Step 12: Meeting Summarizer
Delegates to Step 12 summary.py (hierarchical chunk-and-summarize + KeyBERT key points).
"""

import logging
from typing import List, Dict, Any, Optional

from app.ml.summary import hierarchical_summarize, extract_key_points_keybert

logger = logging.getLogger("meetora.ml.summarizer")


def generate_summary(
    title: str,
    transcripts: List[Dict[str, Any]],
    decisions: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Step 12: Generates hierarchical meeting summary, key takeaways, and KeyBERT key points.
    """
    logger.info(f"Generating hierarchical summary for meeting: '{title}' ({len(transcripts)} transcripts)")
    return hierarchical_summarize(transcripts, title=title, decisions=decisions or [])
