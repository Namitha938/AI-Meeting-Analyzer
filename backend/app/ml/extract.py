"""
Step 11: Action Item Information Extraction (extract.py)

For sentences labeled action_item:
  - Uses spaCy NER and proper noun resolution for the owner (person names)
  - Matches owner names to meeting speakers or users
  - Uses dateparser to parse natural language deadlines into concrete timestamps
"""

import re
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

logger = logging.getLogger("meetora.ml.extract")

# Global singleton spaCy pipeline
_SPACY_NLP: Optional[Any] = None


def get_spacy_pipeline():
    """Loads or retrieves cached spaCy NLP pipeline."""
    global _SPACY_NLP
    if _SPACY_NLP is not None:
        return _SPACY_NLP

    try:
        import spacy
        try:
            _SPACY_NLP = spacy.load("en_core_web_sm")
            logger.info("Loaded spaCy en_core_web_sm model for NER extraction.")
            return _SPACY_NLP
        except Exception:
            _SPACY_NLP = spacy.blank("en")
            logger.info("Initialized blank spaCy English pipeline.")
            return _SPACY_NLP
    except ImportError:
        logger.warning("spaCy not available. Using heuristic pattern matching.")
        return None


def match_person_to_candidates(name: str, candidates: List[str]) -> Optional[str]:
    """
    Matches an extracted person name (e.g. 'Marcus', 'Sarah') to the meeting
    speakers or registered users (e.g. 'Marcus Lee', 'Sarah Kim').
    """
    if not name or not candidates:
        return None

    clean_name = name.strip().lower()
    clean_name = re.sub(r"^[,\s]+|[,\s]+$", "", clean_name)

    # 1. Exact match (case-insensitive)
    for cand in candidates:
        if cand.strip().lower() == clean_name:
            return cand

    # 2. First name / Last name match
    for cand in candidates:
        parts = cand.strip().split()
        first_name = parts[0].lower() if parts else ""
        last_name = parts[-1].lower() if len(parts) > 1 else ""

        if clean_name == first_name or clean_name == last_name:
            return cand

    # 3. Substring match
    for cand in candidates:
        cand_lower = cand.strip().lower()
        if clean_name in cand_lower or cand_lower in clean_name:
            return cand

    return None


def extract_owner(
    sentence: str,
    speaker: Optional[str] = None,
    candidate_speakers: Optional[List[str]] = None,
    meeting_users: Optional[List[str]] = None,
) -> str:
    """
    Extracts the person responsible for the action item.
    Resolves self-commitments ('I will', 'I'll') to the current speaker,
    extracts named entities via spaCy, and matches them against meeting speakers or users.
    """
    text = sentence.strip()
    lower = text.lower()
    all_candidates = list(dict.fromkeys((candidate_speakers or []) + (meeting_users or [])))

    # 1. Check self-assignment pronoun commitments ("I'll", "I will", "I can", "I am going to")
    if re.search(r"\b(i'll|i will|i can|i am going to|i'm going to|i'll take)\b", lower):
        if speaker and speaker != "Unassigned":
            matched = match_person_to_candidates(speaker, all_candidates)
            return matched or speaker

    # 2. Check direct address patterns ("Sarah, please...", "Marcus will...", "Let's have Jordan...")
    nlp = get_spacy_pipeline()
    extracted_names = []

    if nlp is not None:
        doc = nlp(text)
        # Extract named entities of PERSON or ORG (spaCy sometimes tags single foreign names as ORG)
        for ent in doc.ents:
            if ent.label_ in ("PERSON", "ORG") and len(ent.text.strip()) > 1:
                extracted_names.append(ent.text.strip())

        # Also inspect Proper Nouns (PROPN) at the start or subject position
        for token in doc:
            if token.pos_ == "PROPN" and token.text.isalpha() and token.text.lower() not in ["friday", "monday", "tuesday", "wednesday", "thursday", "saturday", "sunday", "api", "pr", "q3", "q4"]:
                extracted_names.append(token.text)

    # Regex fallback for explicit names
    name_patterns = [
        r"^([A-Z][a-z]+)[,\s]+(?:please|can you|could you)\b",
        r"\b([A-Z][a-z]+)\s+will\s+(?:take|deploy|write|schedule|handle|review|send)\b",
        r"\bassign(?:ed)?\s+to\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b",
    ]
    for pat in name_patterns:
        m = re.search(pat, text)
        if m:
            extracted_names.append(m.group(1).strip())

    # 3. Match extracted names to candidate speakers / users
    for raw_name in extracted_names:
        matched = match_person_to_candidates(raw_name, all_candidates)
        if matched:
            return matched

    # If an extracted name was found without a candidate pool match, return the cleanest entity
    if extracted_names:
        clean = extracted_names[0]
        # Avoid common false positives
        if clean.lower() not in ["team", "everyone", "today", "tomorrow"]:
            return clean

    # 4. Fallback to current speaker or Unassigned
    if speaker and speaker != "Unassigned":
        matched = match_person_to_candidates(speaker, all_candidates)
        return matched or speaker

    return all_candidates[0] if all_candidates else "Unassigned"


DEADLINE_REGEX_PATTERNS = [
    r"\bby\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)(?:\s+(?:morning|afternoon|evening|eod|night))?\b",
    r"\bby\s+(tomorrow|end of day|eod|noon|next week|end of week|tonight)\b",
    r"\bbefore\s+(monday|tuesday|wednesday|thursday|friday|tomorrow|[0-9]{1,2}(?::[0-9]{2})?\s*(?:am|pm)?)\b",
    r"\bby\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+[0-9]{1,2}(?:st|nd|rd|th)?\b",
    r"\bdue\s+(?:on|by|before)\s+([a-zA-Z0-9\s]+?)(?:[.,;]|$)",
]


def extract_deadline(sentence: str) -> Tuple[str, Optional[str]]:
    """
    Extracts deadline phrase and parses it with dateparser into an ISO timestamp.

    Returns:
        Tuple of (human_readable_deadline, iso_date_string)
    """
    import dateparser

    text = sentence.strip()
    lower = text.lower()
    candidate_phrase = None

    for pat in DEADLINE_REGEX_PATTERNS:
        m = re.search(pat, lower)
        if m:
            candidate_phrase = m.group(0).strip()
            break

    if not candidate_phrase:
        # Check day names or relative temporal tokens
        for day in ["friday", "monday", "tomorrow", "wednesday", "thursday", "tuesday", "saturday", "sunday", "next week", "eod"]:
            if day in lower:
                candidate_phrase = f"by {day}"
                break

    if not candidate_phrase:
        return ("TBD", None)

    # Clean phrase prefix (strip 'by ' or 'before ')
    clean_display = re.sub(r"^(by|before|due on|due by)\s+", "", candidate_phrase, flags=re.IGNORECASE).strip()

    # Parse with dateparser
    parsed_dt = None
    try:
        parsed_dt = dateparser.parse(
            clean_display,
            settings={
                "PREFER_DATES_FROM": "future",
                "RELATIVE_BASE": datetime.now(),
            }
        )
    except Exception as e:
        logger.warning(f"dateparser error for '{clean_display}': {e}")

    iso_str = parsed_dt.strftime("%Y-%m-%d") if parsed_dt else None
    display_str = clean_display.capitalize()

    return (display_str, iso_str)


def extract_priority(text: str) -> str:
    """Infers task priority based on urgency cues."""
    lower = text.lower()
    if any(w in lower for w in ["critical", "asap", "urgent", "must", "immediately", "blocker"]):
        return "high"
    if any(w in lower for w in ["polish", "nice to have", "someday", "low"]):
        return "low"
    return "medium"


def extract_action_item(
    sentence: str,
    speaker: Optional[str] = None,
    candidate_speakers: Optional[List[str]] = None,
    meeting_users: Optional[List[str]] = None,
    confidence: float = 0.95,
) -> Dict[str, Any]:
    """
    Step 11: Extracts structured action item with spaCy NER owner and dateparser deadline.

    Returns:
        {
            "title": str,
            "owner": str,
            "assignee": str,  # Alias for backward compatibility
            "deadline": str,
            "deadline_date": Optional[str],
            "confidence": float,
            "confidence_score": float,
            "priority": str,
            "raw_sentence": str,
            "status": "pending",
        }
    """
    clean_title = sentence.strip()
    clean_title = re.sub(
        r"^(i will|i'll|we need to|let's|please|can you|could you|you should)\s+",
        "",
        clean_title,
        flags=re.IGNORECASE,
    )
    clean_title = clean_title[0].upper() + clean_title[1:] if clean_title else sentence

    owner = extract_owner(
        sentence,
        speaker=speaker,
        candidate_speakers=candidate_speakers,
        meeting_users=meeting_users,
    )

    deadline_display, deadline_iso = extract_deadline(sentence)
    priority = extract_priority(sentence)

    return {
        "title": clean_title,
        "owner": owner,
        "assignee": owner,
        "deadline": deadline_display,
        "deadline_date": deadline_iso,
        "priority": priority,
        "confidence": confidence,
        "confidence_score": confidence,
        "raw_sentence": sentence,
        "status": "pending",
    }


def extract_actions(
    transcript_items: List[Dict[str, Any]],
    candidate_speakers: Optional[List[str]] = None,
    meeting_users: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """
    Extracts all action items from a transcript, filtering for sentences labeled action_item.
    """
    from app.ml.classifier import predict

    actions = []
    candidates = candidate_speakers or ["Sarah Kim", "Marcus Lee", "Jordan Davis"]

    for item in transcript_items:
        text = item.get("text", "").strip()
        speaker = item.get("speaker", "Unassigned")
        if not text:
            continue

        # Check if already tagged as action_item or run classifier
        is_action = item.get("is_action_item", False)
        conf = item.get("confidence", 0.90)

        if not is_action:
            pred = predict([text])[0]
            if pred["label"] == "action_item":
                is_action = True
                conf = pred["confidence"]

        if is_action:
            action = extract_action_item(
                sentence=text,
                speaker=speaker,
                candidate_speakers=candidates,
                meeting_users=meeting_users,
                confidence=conf,
            )
            actions.append(action)

    return actions
