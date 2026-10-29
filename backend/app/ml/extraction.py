"""
Module 4 / Step 11: Information Extraction (Actions and Decisions)
Delegates action item extraction to Step 11 extract.py (spaCy NER + dateparser)
while maintaining backward-compatible function signatures.
"""

import re
import logging
from typing import List, Dict, Any, Optional

from app.ml.extract import extract_actions, extract_action_item
from app.ml.classifier import classify_sentence

logger = logging.getLogger("meetora.ml.extraction")


def extract_action_items(transcript_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Extracts action items using spaCy NER for owner matching and dateparser for deadlines.
    """
    logger.info(f"Extracting action items from {len(transcript_items)} transcript segments...")
    return extract_actions(transcript_items)


def extract_decisions(transcript_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Module 4b: Decision Extraction.
    Identifies agreements, conclusions, and consensuses with category and rationale.
    """
    decisions = []
    for item in transcript_items:
        text = item.get("text", "")
        pred = classify_sentence(text)

        if pred["top_class"] == "decision" or any(w in text.lower() for w in ["agreed to", "reached consensus", "decided to", "it was finalized"]):
            decisions.append({
                "decision_text": text.strip(),
                "category": "Product & Engineering",
                "rationale": "Aligned by cross-functional meeting consensus.",
                "confidence_score": pred["confidence"],
                "status": "approved",
            })

    return decisions
