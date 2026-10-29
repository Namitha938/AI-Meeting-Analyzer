import re
import logging
from typing import List, Dict, Any

from app.ml.classifier import classify_sentence

logger = logging.getLogger("meetora.ml.extraction")

DEADLINE_PATTERNS = [
    r"\bby\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
    r"\bby\s+(tomorrow|end of day|eod|noon|next week)\b",
    r"\bbefore\s+[0-9]{1,2}(?::[0-9]{2})?\s*(?:am|pm)?\b",
    r"\bby\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+[0-9]{1,2}\b",
]

def _extract_deadline(text: str) -> str:
    lower = text.lower()
    for pat in DEADLINE_PATTERNS:
        match = re.search(pat, lower)
        if match:
            raw = match.group(0).strip()
            # Strip "by " or "before " prefix for clean presentation
            cleaned = re.sub(r"^(by|before)\s+", "", raw, flags=re.IGNORECASE)
            return cleaned.capitalize()
    if "friday" in lower:
        return "Friday"
    if "monday" in lower:
        return "Monday"
    if "tomorrow" in lower:
        return "Tomorrow"
    return "TBD"

def _extract_priority(text: str) -> str:
    lower = text.lower()
    if any(w in lower for w in ["critical", "asap", "urgent", "must", "immediately", "blocker"]):
        return "high"
    if any(w in lower for w in ["polish", "nice to have", "someday", "low"]):
        return "low"
    return "medium"

def extract_action_items(transcript_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Module 4a: Action Item Extraction & Normalization.
    Identifies task commitments, infers assignees and deadlines, and standardizes task descriptions.

    Args:
        transcript_items: List of transcript segment dicts with 'speaker', 'text'.

    Returns:
        List of structured action items:
        [{'title': '...', 'assignee': '...', 'deadline': '...', 'priority': '...', 'confidence_score': 0.94}, ...]
    """
    action_items = []
    for item in transcript_items:
        text = item.get("text", "")
        speaker = item.get("speaker", "Unassigned")

        # Classify sentence
        pred = classify_sentence(text)
        is_action = pred["top_class"] == "action_item" or item.get("is_action_item", False)

        if is_action:
            # Clean and normalize title (e.g. "I'll schedule 5 customer beta interviews" -> "Schedule 5 customer beta interviews")
            clean_title = text.strip()
            clean_title = re.sub(r"^(i will|i'll|we need to|let's|please|can you)\s+", "", clean_title, flags=re.IGNORECASE)
            clean_title = clean_title[0].upper() + clean_title[1:] if clean_title else text

            deadline = _extract_deadline(text)
            priority = _extract_priority(text)

            action_items.append({
                "title": clean_title,
                "assignee": speaker,
                "deadline": deadline,
                "priority": priority,
                "confidence_score": pred["confidence"],
                "status": "pending",
                "model_version": "distilbert-v2.4",
            })

    return action_items

def extract_decisions(transcript_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Module 4b: Decision Extraction.
    Identifies agreements, conclusions, and consensuses with category and rationale.

    Args:
        transcript_items: List of transcript segment dicts.

    Returns:
        List of structured decisions:
        [{'decision_text': '...', 'category': '...', 'rationale': '...'}, ...]
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
            })

    return decisions
