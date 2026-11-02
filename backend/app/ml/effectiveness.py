"""
Module for computing Meeting Effectiveness Score and 4 Quality Pillars.

Pillars:
1. Clarity (0-100): Penalizes filler words and deviations from ideal sentence length (~15 words).
2. Actionability (0-100): 50% coverage (action items per utterance, capped at 10%) + 50% completeness (items with both assignee & deadline).
3. Engagement (0-100): 100 * (1 - Gini of per-speaker speaking time normalized by n/(n-1)). Returns 30 for 1 speaker.
4. Goal Alignment (0-100): Cosine similarity between agenda (or title) and transcript embedding, rescaled from 0.1-0.7 to 0-100.

Overall Score: Rounded mean of the 4 pillars. Returns None for empty segments.
"""

import math
import re
from typing import List, Dict, Any, Optional, Callable


FILLER_WORDS_PATTERN = re.compile(r"\b(um|uh|ah|er)\b", re.IGNORECASE)
FILLER_PHRASES = ["you know", "i mean"]


def _gini_coefficient(values: List[float]) -> float:
    """Computes standard Gini coefficient for a list of non-negative values."""
    if not values:
        return 0.0
    n = len(values)
    total = sum(values)
    if total == 0:
        return 0.0

    sorted_vals = sorted(values)
    diff_sum = 0.0
    for i, yi in enumerate(sorted_vals, 1):
        diff_sum += (2 * i - n - 1) * yi
    return diff_sum / (n * total)


def compute_clarity(segments: List[Dict[str, Any]]) -> int:
    """
    100 minus penalty for filler words per word, minus penalty when average
    sentence length is far from ~15 words.
    """
    all_texts = [s.get("text", "") for s in segments if s.get("text")]
    combined_text = " ".join(all_texts)
    if not combined_text.strip():
        return 0

    words = re.findall(r"\b[a-zA-Z0-9']+\b", combined_text.lower())
    total_words = len(words)
    if total_words == 0:
        return 0

    # Count single-word fillers
    single_fillers = len(FILLER_WORDS_PATTERN.findall(combined_text))

    # Count multi-word filler phrases
    phrase_fillers = 0
    lower_text = combined_text.lower()
    for phrase in FILLER_PHRASES:
        phrase_fillers += len(re.findall(r"\b" + re.escape(phrase) + r"\b", lower_text))

    total_fillers = single_fillers + phrase_fillers
    filler_ratio = total_fillers / total_words

    # Filler penalty: each 1% of fillers costs ~5 points (e.g., 5% fillers = 25 pts penalty)
    filler_penalty = min(60.0, filler_ratio * 500.0)

    # Average sentence length
    sentences = [sent.strip() for sent in re.split(r"[.!?]+", combined_text) if sent.strip()]
    num_sentences = max(len(sentences), 1)
    avg_sentence_len = total_words / num_sentences

    # Length penalty: deviation from 15 words
    len_dev = abs(avg_sentence_len - 15.0)
    len_penalty = min(30.0, len_dev * 1.5)

    clarity = 100.0 - filler_penalty - len_penalty
    return int(round(max(0.0, min(100.0, clarity))))


def compute_actionability(segments: List[Dict[str, Any]], action_items: List[Dict[str, Any]]) -> int:
    """
    50% coverage (action items per utterance, capped at 10%)
    plus 50% completeness (share of items with BOTH assignee and due date).
    """
    num_segments = len(segments)
    if num_segments == 0:
        return 0

    num_actions = len(action_items) if action_items else 0

    # 1. Coverage: actions / segments capped at 10% (0.10)
    coverage_ratio = num_actions / max(num_segments, 1)
    coverage_score = min(coverage_ratio / 0.10, 1.0) * 50.0

    # 2. Completeness: share of items with both assignee and due date
    if num_actions == 0:
        completeness_score = 0.0
    else:
        complete_items = 0
        for item in action_items:
            raw_assignee = str(item.get("assignee") or item.get("owner") or "").strip()
            raw_due = str(item.get("due_date") or item.get("deadline") or "").strip()

            has_assignee = bool(raw_assignee and raw_assignee.lower() not in ["unassigned", "unknown", "none", "tbd", ""])
            has_due = bool(raw_due and raw_due.lower() not in ["none", "no deadline", "tbd", ""])

            if has_assignee and has_due:
                complete_items += 1

        completeness_score = (complete_items / num_actions) * 50.0

    actionability = coverage_score + completeness_score
    return int(round(max(0.0, min(100.0, actionability))))


def compute_engagement(segments: List[Dict[str, Any]]) -> int:
    """
    100 * (1 - Gini of per-speaker speaking time normalized by n/(n-1)).
    If only 1 speaker, returns 30.
    """
    speaker_durations: Dict[str, float] = {}
    for s in segments:
        spk = s.get("speaker") or "Unknown"
        # Support both 'start'/'end' and 'start_time'/'end_time'
        start = float(s.get("start") if s.get("start") is not None else s.get("start_time", 0.0))
        end = float(s.get("end") if s.get("end") is not None else s.get("end_time", 0.0))
        dur = max(0.0, end - start)
        if dur == 0.0 and s.get("text"):
            # Estimate from word count if timestamps are identical
            dur = max(1.0, float(len(s.get("text", "").split())))

        speaker_durations[spk] = speaker_durations.get(spk, 0.0) + dur

    n = len(speaker_durations)
    if n <= 1:
        return 30

    durations = list(speaker_durations.values())
    raw_gini = _gini_coefficient(durations)

    # Normalize Gini by n / (n - 1) so maximum possible inequality equals 1.0
    norm_factor = n / (n - 1)
    normalized_gini = min(1.0, raw_gini * norm_factor)

    engagement = 100.0 * (1.0 - normalized_gini)
    return int(round(max(0.0, min(100.0, engagement))))


def compute_goal_alignment(
    segments: List[Dict[str, Any]],
    agenda_text: Optional[str] = None,
    embed_fn: Optional[Callable[[str], List[float]]] = None,
) -> int:
    """
    Cosine similarity between agenda (fall back to meeting title) and the
    transcript embedding, rescaled from 0.1-0.7 to 0-100 and clipped.
    """
    if embed_fn is None:
        try:
            from app.search_vector import embedding_engine
            embed_fn = embedding_engine.embed_text
        except Exception:
            return 50

    target_agenda = (agenda_text or "").strip()
    if not target_agenda:
        return 50

    transcript_text = " ".join(s.get("text", "") for s in segments if s.get("text")).strip()
    if not transcript_text:
        return 0

    v_agenda = embed_fn(target_agenda)
    v_transcript = embed_fn(transcript_text)

    dot = sum(a * b for a, b in zip(v_agenda, v_transcript))
    norm_a = math.sqrt(sum(a * a for a in v_agenda))
    norm_b = math.sqrt(sum(b * b for b in v_transcript))

    if norm_a == 0.0 or norm_b == 0.0:
        return 0

    cos_sim = dot / (norm_a * norm_b)

    # Rescale from range [0.1, 0.7] to [0, 100]
    rescaled = ((cos_sim - 0.1) / (0.7 - 0.1)) * 100.0
    return int(round(max(0.0, min(100.0, rescaled))))


def compute_effectiveness(
    segments: Optional[List[Dict[str, Any]]],
    action_items: Optional[List[Dict[str, Any]]] = None,
    agenda_text: Optional[str] = None,
    embed_fn: Optional[Callable[[str], List[float]]] = None,
) -> Optional[Dict[str, Any]]:
    """
    Computes overall meeting effectiveness score and 4 quality pillars.
    Returns None if segments is empty or has no content.
    """
    if not segments:
        return None

    # Filter out empty segments
    valid_segments = [s for s in segments if isinstance(s, dict) and s.get("text", "").strip()]
    if not valid_segments:
        return None

    actions = action_items or []

    clarity = compute_clarity(valid_segments)
    actionability = compute_actionability(valid_segments, actions)
    engagement = compute_engagement(valid_segments)
    goal_alignment = compute_goal_alignment(valid_segments, agenda_text, embed_fn)

    score = int(round((clarity + actionability + engagement + goal_alignment) / 4.0))

    return {
        "score": score,
        "pillars": {
            "clarity": clarity,
            "actionability": actionability,
            "engagement": engagement,
            "goal_alignment": goal_alignment,
        },
    }

