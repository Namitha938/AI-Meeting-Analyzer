import logging
from typing import List, Dict, Any

from app.nlp_analysis import MeetingSummarizer

logger = logging.getLogger("meetora.ml.summarizer")

def generate_summary(
    title: str,
    transcripts: List[Dict[str, Any]],
    decisions: List[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Module 5: Meeting Summarizer.
    Generates structured AI executive summary, key takeaways, and recommended next steps.

    Args:
        title: Meeting title.
        transcripts: List of transcript segment dicts.
        decisions: Optional list of extracted decision dicts.

    Returns:
        Dict with 'overview', 'key_takeaways', 'next_steps', and 'model_version'.
    """
    logger.info(f"Generating summary for meeting: '{title}' ({len(transcripts)} transcripts)")
    return MeetingSummarizer.generate_summary(title, transcripts, decisions or [])

