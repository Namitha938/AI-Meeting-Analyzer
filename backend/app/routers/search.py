from typing import List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.config import settings
from app.database import get_db
from app.models import User, Meeting, Transcript, Summary, ActionItem, Decision
from app.schemas import SearchResponse, SearchResultItem
from app.auth import get_current_user
from app.search_vector import vector_search_service

router = APIRouter(prefix="/search", tags=["Search"])

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
