from typing import List, Dict, Any
from datetime import datetime, timedelta
import urllib.parse
from fastapi import APIRouter, Depends, HTTPException, status, Response
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


@router.get("/meeting/{meeting_id}/google-url")
def get_meeting_google_calendar_url(
    meeting_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    start_dt = meeting.scheduled_at or meeting.created_at or datetime.utcnow()
    end_dt = start_dt + timedelta(minutes=60)
    fmt = "%Y%m%dT%H%M%SZ"
    dates_str = f"{start_dt.strftime(fmt)}/{end_dt.strftime(fmt)}"

    details = f"Meetora Live Meeting: {meeting.title}\nJoin Link: http://localhost:8443/#live/{meeting.id}\nMeeting Code: {meeting.meeting_code or f'meet-{meeting.id}'}"
    params = {
        "action": "TEMPLATE",
        "text": meeting.title,
        "details": details,
        "location": f"http://localhost:8443/#live/{meeting.id}",
        "dates": dates_str
    }
    url = f"https://calendar.google.com/calendar/render?{urllib.parse.urlencode(params)}"
    return {
        "meeting_id": meeting.id,
        "title": meeting.title,
        "google_calendar_url": url
    }


@router.get("/meeting/{meeting_id}/ics")
def download_meeting_ics(
    meeting_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    start_dt = meeting.scheduled_at or meeting.created_at or datetime.utcnow()
    end_dt = start_dt + timedelta(minutes=60)
    fmt = "%Y%m%dT%H%M%SZ"
    now_str = datetime.utcnow().strftime(fmt)

    ics_content = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Meetora AI//Meeting Analyzer//EN
CALSCALE:GREGORIAN
METHOD:PUBLISH
BEGIN:VEVENT
UID:meetora-{meeting.id}-{start_dt.strftime('%Y%m%d')}@meetora.ai
DTSTAMP:{now_str}
DTSTART:{start_dt.strftime(fmt)}
DTEND:{end_dt.strftime(fmt)}
SUMMARY:{meeting.title}
DESCRIPTION:Meetora Live Meeting\\nJoin link: http://localhost:8443/#live/{meeting.id}\\nMeeting Code: {meeting.meeting_code or f'meet-{meeting.id}'}
LOCATION:http://localhost:8443/#live/{meeting.id}
STATUS:CONFIRMED
END:VEVENT
END:VCALENDAR"""

    safe_title = "".join([c if c.isalnum() else "_" for c in meeting.title.lower()][:30])
    return Response(
        content=ics_content.strip(),
        media_type="text/calendar",
        headers={"Content-Disposition": f'attachment; filename="meetora_{safe_title}.ics"'}
    )

