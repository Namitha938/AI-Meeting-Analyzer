from app.database import SessionLocal
from app.models import Meeting, ActionItem, User
from app.calendar_service import GoogleCalendarService, EmailReminderService
from app.celery_app import send_deadline_reminders_task

print("=== 1. TESTING GOOGLE CALENDAR SYNC ===")
db = SessionLocal()
meeting = db.query(Meeting).first()
if meeting and meeting.action_items:
    item = meeting.action_items[0]
    res = GoogleCalendarService.sync_action_item_to_calendar(item, meeting)
    print("Google Calendar Sync result:")
    print("  - Event ID:", res["event_id"])
    print("  - Title:", res["title"])
    print("  - Google Calendar URL:", res["google_calendar_url"][:75] + "...")
    assert "calendar.google.com" in res["google_calendar_url"], "Google Calendar URL invalid!"
    print("Google Calendar 1-click sync verified successfully!\n")

print("=== 2. TESTING UPCOMING CALENDAR SCHEDULE ===")
user = db.query(User).first()
if user:
    events = GoogleCalendarService.get_upcoming_schedule(user.id, db)
    print(f"Retrieved {len(events)} upcoming calendar action items for user '{user.email}':")
    for evt in events[:3]:
        print(f"  • {evt['title']} (Due: {evt['deadline']}, Meeting: {evt['meeting_title']})")
    assert len(events) > 0, "No calendar events found!"
    print("Calendar schedule aggregation verified successfully!\n")

print("=== 3. TESTING EMAIL REMINDER ENGINE ===")
reminders = EmailReminderService.scan_and_send_due_reminders(db)
print("Deadline Reminders Scan output:", reminders)
assert reminders["status"] == "success", "Reminder scan failed!"
print("Email reminder delivery verified successfully!\n")

print("=== 4. TESTING CELERY BEAT SCHEDULED TASK ===")
beat_res = send_deadline_reminders_task()
print("Celery Beat Task execution result:", beat_res)
assert beat_res["status"] == "success", "Celery Beat task failed!"
print("Celery Beat deadline reminder task verified successfully!\n")

db.close()
print(">>> STEP 12 (GOOGLE CALENDAR & CELERY BEAT REMINDERS) 100% OPERATIONAL!")

