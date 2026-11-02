"""
Tests for Meeting Effectiveness Score and 4 Quality Pillars.
Requirements:
- a meeting with many fillers scores lower on clarity than a clean one
- a single dominant speaker scores lower on engagement than an even split
- action items missing assignee/due date lower actionability
- two different meetings produce different scores
- empty transcript returns None
"""

import pytest
from app.ml.effectiveness import (
    compute_effectiveness,
    compute_clarity,
    compute_actionability,
    compute_engagement,
    compute_goal_alignment,
)


def test_empty_transcript_returns_none():
    """Empty transcript list or segments without text must return None."""
    assert compute_effectiveness([]) is None
    assert compute_effectiveness(None) is None
    assert compute_effectiveness([{"speaker": "Alice", "text": "   "}]) is None


def test_fillers_score_lower_on_clarity_than_clean():
    """A meeting with many conversational fillers (um, uh, you know, etc.) must score lower on clarity than a clean one."""
    clean_segments = [
        {"speaker": "Alice", "text": "We have completed the deployment of our authentication service."},
        {"speaker": "Bob", "text": "The test coverage is solid and all end-to-end integration tests are passing."},
        {"speaker": "Charlie", "text": "Let us proceed with the production rollout as planned."},
    ]

    filler_segments = [
        {"speaker": "Alice", "text": "Um, uh, we have, you know, completed the deployment, I mean, of our service."},
        {"speaker": "Bob", "text": "Uh, er, the test coverage is, um, you know, passing I mean."},
        {"speaker": "Charlie", "text": "Um, ah, let us, you know, proceed with rollout, er, as planned."},
    ]

    clean_clarity = compute_clarity(clean_segments)
    filler_clarity = compute_clarity(filler_segments)

    assert clean_clarity > filler_clarity
    assert filler_clarity < 75


def test_dominant_speaker_scores_lower_on_engagement_than_even_split():
    """A single dominant speaker monologue must score lower on engagement than an evenly balanced discussion."""
    # Balanced 3-way split: 30s each
    balanced_segments = [
        {"speaker": "Alice", "start": 0.0, "end": 30.0, "text": "Alice speaks for thirty seconds."},
        {"speaker": "Bob", "start": 30.0, "end": 60.0, "text": "Bob speaks for thirty seconds."},
        {"speaker": "Charlie", "start": 60.0, "end": 90.0, "text": "Charlie speaks for thirty seconds."},
    ]

    # Dominant speaker: Alice speaks 88 seconds, Bob and Charlie speak 1 second each
    dominant_segments = [
        {"speaker": "Alice", "start": 0.0, "end": 88.0, "text": "Alice speaks for eighty-eight seconds alone."},
        {"speaker": "Bob", "start": 88.0, "end": 89.0, "text": "Yes."},
        {"speaker": "Charlie", "start": 89.0, "end": 90.0, "text": "Agreed."},
    ]

    balanced_eng = compute_engagement(balanced_segments)
    dominant_eng = compute_engagement(dominant_segments)

    assert balanced_eng > dominant_eng
    assert balanced_eng >= 90
    assert dominant_eng <= 30

    # Also verify single-speaker default is 30
    single_speaker_segments = [
        {"speaker": "Alice", "start": 0.0, "end": 60.0, "text": "Alice speaks completely alone throughout."},
    ]
    assert compute_engagement(single_speaker_segments) == 30


def test_missing_assignee_or_due_date_lowers_actionability():
    """Action items lacking explicit assignees or target deadlines must result in lower actionability scores."""
    segments = [
        {"speaker": "Alice", "text": "First utterance to set baseline."},
        {"speaker": "Bob", "text": "Second utterance discussing work."},
        {"speaker": "Charlie", "text": "Third utterance agreeing on milestones."},
        {"speaker": "Alice", "text": "Fourth utterance concluding the sync."},
    ]

    complete_actions = [
        {"title": "Deploy API", "assignee": "Alice", "due_date": "Friday"},
        {"title": "Draft specs", "assignee": "Bob", "due_date": "Monday"},
    ]

    incomplete_actions = [
        {"title": "Deploy API", "assignee": "Unassigned", "due_date": ""},
        {"title": "Draft specs", "assignee": "", "due_date": "None"},
    ]

    complete_score = compute_actionability(segments, complete_actions)
    incomplete_score = compute_actionability(segments, incomplete_actions)

    assert complete_score > incomplete_score
    # Complete should get full completeness score (50), incomplete gets 0 completeness
    assert complete_score - incomplete_score >= 40


def test_two_different_meetings_produce_different_scores():
    """Two meetings with differing characteristics must produce different overall scores and pillar breakdowns."""
    high_quality_meeting = {
        "segments": [
            {"speaker": "Alice", "start": 0.0, "end": 20.0, "text": "Welcome everyone. Today we are reviewing our Q3 product roadmap deliverables."},
            {"speaker": "Bob", "start": 20.0, "end": 40.0, "text": "I will finalize the backend API documentation and schema validations by Friday."},
            {"speaker": "Charlie", "start": 40.0, "end": 60.0, "text": "I can own the frontend integration testing and submit the pull request by Monday."},
        ],
        "action_items": [
            {"title": "Finalize backend API docs", "assignee": "Bob", "due_date": "Friday"},
            {"title": "Submit frontend PR", "assignee": "Charlie", "due_date": "Monday"},
        ],
        "agenda": "Q3 product roadmap deliverables and milestones",
    }

    poor_quality_meeting = {
        "segments": [
            {"speaker": "Alice", "start": 0.0, "end": 50.0, "text": "Um, uh, well, you know, we had, er, some sync yesterday and uh, I mean, stuff happened."},
            {"speaker": "Alice", "start": 50.0, "end": 55.0, "text": "Um, someone should probably do something about the servers at some point."},
        ],
        "action_items": [
            {"title": "Check servers", "assignee": "Unassigned", "due_date": ""},
        ],
        "agenda": "Enterprise Customer Contract Signing and Legal Terms",
    }

    res_high = compute_effectiveness(
        high_quality_meeting["segments"],
        high_quality_meeting["action_items"],
        high_quality_meeting["agenda"],
    )

    res_poor = compute_effectiveness(
        poor_quality_meeting["segments"],
        poor_quality_meeting["action_items"],
        poor_quality_meeting["agenda"],
    )

    assert res_high is not None
    assert res_poor is not None

    # Scores must be different
    assert res_high["score"] != res_poor["score"]
    assert res_high["score"] > res_poor["score"]

    # Pillar checks
    assert res_high["pillars"]["clarity"] > res_poor["pillars"]["clarity"]
    assert res_high["pillars"]["actionability"] > res_poor["pillars"]["actionability"]
    assert res_high["pillars"]["engagement"] > res_poor["pillars"]["engagement"]

