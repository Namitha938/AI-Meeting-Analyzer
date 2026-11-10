from typing import List, Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.config import settings
from app.database import get_db
from app.models import User, Meeting, Transcript, Summary, ActionItem, Decision
from app.schemas import SearchResponse, SearchResultItem
from app.auth import get_current_user
from app.search_vector import vector_search_service

router = APIRouter(prefix="/search", tags=["Search"])

class CrossMeetingAskRequest(BaseModel):
    query: str

class CitationItem(BaseModel):
    meeting_id: int
    meeting_title: str
    snippet: str
    speaker: Optional[str] = None
    timestamp: Optional[float] = None
    match_type: str = "transcript"

class CrossMeetingAskResponse(BaseModel):
    query: str
    answer: str
    citations: List[CitationItem]
    total_sources_consulted: int

@router.get("", response_model=SearchResponse)
def search_meetings(
    q: str = Query(..., min_length=1, description="Keyword to search across transcripts, summaries, decisions, and actions"),
    semantic: bool = Query(False, description="Enable pgvector / FAISS semantic vector search"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    keyword = f"%{q.lower()}%"
    results: List[SearchResultItem] = []

    # If semantic search requested, run vector search first
    if semantic:
        sem_matches = vector_search_service.search_transcripts_semantic(
            query=q,
            user_id=current_user.id,
            db=db,
            limit=10
        )
        for s in sem_matches:
            results.append(
                SearchResultItem(
                    meeting_id=s["meeting_id"],
                    meeting_title=s["meeting_title"],
                    match_type="semantic",
                    snippet=f"[{s['score'] * 100:.0f}% match] {s['snippet']}",
                    timestamp=s["timestamp"],
                )
            )

    # Search in transcripts (keyword fallback)
    t_matches = (
        db.query(Transcript, Meeting)
        .join(Meeting, Meeting.id == Transcript.meeting_id)
        .filter(Meeting.user_id == current_user.id)
        .filter(Transcript.text.ilike(keyword))
        .limit(10)
        .all()
    )
    for t, m in t_matches:
        results.append(
            SearchResultItem(
                meeting_id=m.id,
                meeting_title=m.title,
                match_type="transcript",
                snippet=f"{t.speaker}: {t.text}",
                timestamp=t.start_time,
            )
        )

    # Search in summaries
    s_matches = (
        db.query(Summary, Meeting)
        .join(Meeting, Meeting.id == Summary.meeting_id)
        .filter(Meeting.user_id == current_user.id)
        .filter(Summary.overview.ilike(keyword))
        .limit(5)
        .all()
    )
    for s, m in s_matches:
        results.append(
            SearchResultItem(
                meeting_id=m.id,
                meeting_title=m.title,
                match_type="summary",
                snippet=s.overview[:200] + "...",
                timestamp=0.0,
            )
        )

    # Search in Action Items
    a_matches = (
        db.query(ActionItem, Meeting)
        .join(Meeting, Meeting.id == ActionItem.meeting_id)
        .filter(Meeting.user_id == current_user.id)
        .filter(ActionItem.title.ilike(keyword))
        .limit(5)
        .all()
    )
    for a, m in a_matches:
        results.append(
            SearchResultItem(
                meeting_id=m.id,
                meeting_title=m.title,
                match_type="action_item",
                snippet=f"Action item: {a.title} (Owner: {a.assignee or 'Unassigned'})",
                timestamp=None,
            )
        )

    # Search in Decisions
    d_matches = (
        db.query(Decision, Meeting)
        .join(Meeting, Meeting.id == Decision.meeting_id)
        .filter(Meeting.user_id == current_user.id)
        .filter(Decision.decision_text.ilike(keyword))
        .limit(5)
        .all()
    )
    for d, m in d_matches:
        results.append(
            SearchResultItem(
                meeting_id=m.id,
                meeting_title=m.title,
                match_type="decision",
                snippet=f"Decision: {d.decision_text} ({d.category})",
                timestamp=None,
            )
        )

    return {
        "query": q,
        "total_results": len(results),
        "results": results,
    }

@router.get("/semantic")
def search_semantic(
    q: str = Query(..., min_length=1, description="Semantic concept to query via pgvector / FAISS embeddings"),
    limit: int = Query(10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    results = vector_search_service.search_transcripts_semantic(
        query=q,
        user_id=current_user.id,
        db=db,
        limit=limit
    )
    return {
        "query": q,
        "search_type": "semantic_vector",
        "provider": settings.VECTOR_SEARCH_PROVIDER,
        "dimension": settings.VECTOR_DIMENSION,
        "total_results": len(results),
        "results": results,
    }


@router.post("/ask", response_model=CrossMeetingAskResponse)
def ask_cross_meeting(
    payload: CrossMeetingAskRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Cross-Meeting AI Search ("Ask Meetora Anything"):
    Answers user queries synthesized across all their past meetings,
    grounded with clickable timestamped citations.
    """
    q = payload.query.strip()
    if not q:
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    keyword = f"%{q.lower()}%"
    citations: List[CitationItem] = []

    # 1. Action Items match
    action_matches = (
        db.query(ActionItem, Meeting)
        .join(Meeting, Meeting.id == ActionItem.meeting_id)
        .filter((Meeting.user_id == current_user.id) | (Meeting.user_id == 1))
        .filter(ActionItem.title.ilike(keyword) | ActionItem.assignee.ilike(keyword))
        .limit(5)
        .all()
    )
    for ai, m in action_matches:
        citations.append(
            CitationItem(
                meeting_id=m.id,
                meeting_title=m.title,
                snippet=f"Action item: {ai.title} (Owner: {ai.assignee or 'Unassigned'}, Due: {ai.deadline or 'TBD'})",
                speaker=ai.assignee,
                match_type="action_item"
            )
        )

    # 2. Summaries match
    summary_matches = (
        db.query(Summary, Meeting)
        .join(Meeting, Meeting.id == Summary.meeting_id)
        .filter((Meeting.user_id == current_user.id) | (Meeting.user_id == 1))
        .filter(Summary.overview.ilike(keyword))
        .limit(3)
        .all()
    )
    for s, m in summary_matches:
        citations.append(
            CitationItem(
                meeting_id=m.id,
                meeting_title=m.title,
                snippet=s.overview[:250] + ("..." if len(s.overview) > 250 else ""),
                speaker="AI Executive Summary",
                match_type="summary"
            )
        )

    # 3. Transcripts match
    transcript_matches = (
        db.query(Transcript, Meeting)
        .join(Meeting, Meeting.id == Transcript.meeting_id)
        .filter((Meeting.user_id == current_user.id) | (Meeting.user_id == 1))
        .filter(Transcript.text.ilike(keyword))
        .limit(6)
        .all()
    )
    for t, m in transcript_matches:
        citations.append(
            CitationItem(
                meeting_id=m.id,
                meeting_title=m.title,
                snippet=t.text,
                speaker=t.speaker,
                timestamp=t.start_time,
                match_type="transcript"
            )
        )

    # 4. Synthesize AI Answer
    if not citations:
        answer = f"I searched across all your recorded meetings for '{q}', but did not find any direct mentions in the transcripts, action items, or summaries."
    else:
        meetings_mentioned = list(dict.fromkeys([c.meeting_title for c in citations]))
        points = []
        for c in citations[:4]:
            speaker_tag = f" ({c.speaker})" if c.speaker else ""
            points.append(f"• In '{c.meeting_title}'{speaker_tag}: {c.snippet}")
        
        answer = (
            f"Based on your meetings ({', '.join(meetings_mentioned[:3])}), here is what was found regarding '{q}':\n\n"
            + "\n".join(points)
        )

    return CrossMeetingAskResponse(
        query=q,
        answer=answer,
        citations=citations,
        total_sources_consulted=len(citations)
    )
