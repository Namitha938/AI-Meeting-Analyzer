from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, Meeting, ActionItem, HumanCorrection
from app.schemas import ActionItemResponse, ActionItemUpdate
from app.auth import get_current_user

router = APIRouter(prefix="/action-items", tags=["Action Items"])

@router.get("", response_model=List[ActionItemResponse])
def get_all_user_action_items(
    status_filter: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    query = (
        db.query(ActionItem)
        .join(Meeting, Meeting.id == ActionItem.meeting_id)
        .filter(Meeting.user_id == current_user.id)
    )
    if status_filter:
        query = query.filter(ActionItem.status == status_filter)
    return query.order_by(ActionItem.created_at.desc()).all()

@router.patch("/{item_id}", response_model=ActionItemResponse)
def update_action_item(
    item_id: int,
    item_in: ActionItemUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    item = (
        db.query(ActionItem)
        .join(Meeting, Meeting.id == ActionItem.meeting_id)
        .filter(ActionItem.id == item_id, Meeting.user_id == current_user.id)
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Action item not found")

    update_data = item_in.model_dump(exclude_unset=True)
    
    # Human-in-the-loop logging: capture human corrections to retrain sentence classifier
    has_text_change = "title" in update_data and update_data["title"] != item.title
    has_assignee_change = "assignee" in update_data and update_data["assignee"] != item.assignee
    has_deadline_change = "deadline" in update_data and update_data["deadline"] != item.deadline

    if has_text_change or has_assignee_change or has_deadline_change:
        correction = HumanCorrection(
            user_id=current_user.id,
            action_item_id=item.id,
            original_text=item.title,
            corrected_text=update_data.get("title", item.title),
            original_assignee=item.assignee,
            corrected_assignee=update_data.get("assignee", item.assignee),
            original_deadline=item.deadline,
            corrected_deadline=update_data.get("deadline", item.deadline),
            correction_type="human_edit",
            model_version=item.model_version or "distilbert-v2.4",
        )
        db.add(correction)
        # Clear needs_review flag upon human edit
        item.needs_review = False
        item.confidence_score = 1.0

    for field, val in update_data.items():
        setattr(item, field, val)

    db.commit()
    db.refresh(item)
    return item

@router.post("/{item_id}/review", response_model=ActionItemResponse)
def review_and_approve_action_item(
    item_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Confidence scores & 'needs review' flags:
    User approves a low-confidence or AI-flagged action item,
    marking it reviewed and saving confirmation to the human-in-the-loop training set.
    """
    item = (
        db.query(ActionItem)
        .join(Meeting, Meeting.id == ActionItem.meeting_id)
        .filter(ActionItem.id == item_id, Meeting.user_id == current_user.id)
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Action item not found")

    item.needs_review = False
    item.confidence_score = 1.0

    # Log human verification
    correction = HumanCorrection(
        user_id=current_user.id,
        action_item_id=item.id,
        original_text=item.title,
        corrected_text=item.title,
        original_assignee=item.assignee,
        corrected_assignee=item.assignee,
        original_deadline=item.deadline,
        corrected_deadline=item.deadline,
        correction_type="human_verified",
        model_version=item.model_version or "distilbert-v2.4",
    )
    db.add(correction)
    db.commit()
    db.refresh(item)
    return item

@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_action_item(
    item_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    item = (
        db.query(ActionItem)
        .join(Meeting, Meeting.id == ActionItem.meeting_id)
        .filter(ActionItem.id == item_id, Meeting.user_id == current_user.id)
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Action item not found")

    db.delete(item)
    db.commit()
    return None
