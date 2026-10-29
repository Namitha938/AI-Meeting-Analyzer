from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, Meeting, ActionItem
from app.auth import get_current_user
from app.calendar_service import GoogleCalendarService, EmailReminderService

router = APIRouter(prefix="/calendar", tags=["Calendar & Reminders"])

@router.post("/sync-action-item/{item_id}")
def sync_action_item(
    item_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Step 12: Syncs an Action Item to Google Calendar.
    Generates a 1-click Google Calendar QuickAdd URL with event details.
    """
    item = db.query(ActionItem).filter(ActionItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Action item not found")

    meeting = db.query(Meeting).filter(Meeting.id == item.meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    result = GoogleCalendarService.sync_action_item_to_calendar(item, meeting)
    return result

@router.get("/events")
def get_calendar_events(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Step 12: Returns all upcoming scheduled deadlines and meetings for the user's calendar.
    """
    events = GoogleCalendarService.get_upcoming_schedule(current_user.id, db)
    return {
        "user_id": current_user.id,
        "total_events": len(events),
        "events": events
    }

@router.post("/trigger-reminders")
def trigger_deadline_reminders(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Step 12: Manually runs the Celery Beat scheduled reminder pipeline
    to scan pending action items and send emails.
    """
    res = EmailReminderService.scan_and_send_due_reminders(db)
    return res

