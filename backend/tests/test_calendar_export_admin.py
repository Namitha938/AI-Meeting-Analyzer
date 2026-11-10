import unittest
from app.database import SessionLocal, Base, engine, ensure_db_schema
from app.models import User, Meeting, Summary, Transcript, ActionItem, Decision
from app.calendar_service import GoogleCalendarService, EmailReminderService
from app.routers.export import export_meeting_pdf, export_meeting_docx, export_meeting_markdown, generate_follow_up_email
from app.routers.admin import get_system_stats, get_all_users_admin

class TestCalendarExportAdmin(unittest.TestCase):
    def setUp(self):
        Base.metadata.create_all(bind=engine)
        ensure_db_schema()
        self.db = SessionLocal()
        self.admin = self.db.query(User).filter(User.role == "admin").first()
        if not self.admin:
            self.admin = User(
                email="admin_test_ci@example.com",
                hashed_password="ci_admin_hash",
                full_name="Admin User",
                role="admin",
                is_active=True
            )
            self.db.add(self.admin)
            self.db.commit()
            self.db.refresh(self.admin)

        self.meeting = self.db.query(Meeting).first()
        if not self.meeting:
            self.meeting = Meeting(
                title="CI Pipeline Sprint Review",
                user_id=self.admin.id,
                participants=["Admin User", "Sarah Chen"],
                tags=["Engineering", "CI"],
                status="completed"
            )
            self.db.add(self.meeting)
            self.db.commit()
            self.db.refresh(self.meeting)

            summary = Summary(
                meeting_id=self.meeting.id,
                overview="Sprint review meeting to finalize features and roadmap.",
                key_takeaways=["All unit tests passing", "Ready for deployment"]
            )
            transcript = Transcript(
                meeting_id=self.meeting.id,
                speaker="Admin User",
                start_time=0.0,
                end_time=15.0,
                text="Welcome to the sprint review meeting."
            )
            action_item = ActionItem(
                meeting_id=self.meeting.id,
                title="Deploy to staging",
                assignee="Sarah Chen",
                deadline="Friday"
            )
            decision = Decision(
                meeting_id=self.meeting.id,
                decision_text="Proceed with production release"
            )
            self.db.add_all([summary, transcript, action_item, decision])
            self.db.commit()
            self.db.refresh(self.meeting)

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
