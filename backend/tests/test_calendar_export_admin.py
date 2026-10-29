import unittest
from app.database import SessionLocal
from app.models import User, Meeting
from app.calendar_service import GoogleCalendarService, EmailReminderService
from app.routers.export import export_meeting_pdf, export_meeting_docx, export_meeting_markdown, generate_follow_up_email
from app.routers.admin import get_system_stats, get_all_users_admin

class TestCalendarExportAdmin(unittest.TestCase):
    def setUp(self):
        self.db = SessionLocal()
        self.admin = self.db.query(User).filter(User.role == "admin").first()
        self.meeting = self.db.query(Meeting).first()

    def tearDown(self):
        self.db.close()

    def test_google_calendar_sync(self):
        url = GoogleCalendarService.generate_calendar_link(
            title="Finish UX testing",
            description="Complete onboarding flows",
            deadline_str="Friday",
            meeting_title="Weekly sync"
        )
        self.assertIsInstance(url, str)
        self.assertTrue(url.startswith("https://calendar.google.com/calendar/render"))
        self.assertIn("Finish+UX+testing", url)

    def test_pdf_export_structure(self):
        resp = export_meeting_pdf(meeting_id=self.meeting.id, current_user=self.admin, db=self.db)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.body.startswith(b"%PDF-1.4"))
        self.assertIn(b"%%EOF", resp.body)

    def test_docx_export_structure(self):
        resp = export_meeting_docx(meeting_id=self.meeting.id, current_user=self.admin, db=self.db)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.body.startswith(b"PK\x03\x04"))

    def test_admin_system_metrics(self):
        stats = get_system_stats(admin=self.admin, db=self.db)
        self.assertEqual(stats["status"], "healthy")
        self.assertGreaterEqual(stats["users"]["total"], 1)
        self.assertGreaterEqual(stats["meetings"]["total"], 1)
        self.assertIn("DistilBERT", stats["system_configuration"]["model_architecture"])

if __name__ == "__main__":
    unittest.main()
