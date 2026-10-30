import unittest
from app.database import SessionLocal
from app.models import Meeting, User, ActionItem, Decision, Transcript

class TestMeetingCRUD(unittest.TestCase):
    def setUp(self):
        self.db = SessionLocal()
        # Ensure a meeting with action items and decisions exists for testing
        m = self.db.query(Meeting).filter(Meeting.action_items.any()).first()
        if not m:
            m = self.db.query(Meeting).first()
            if not m:
                u = self.db.query(User).first()
                if not u:
                    u = User(email="test_crud@meetora.ai", hashed_password="hashed_pw_test", role="user")
                    self.db.add(u)
                    self.db.commit()
                m = Meeting(title="Sprint Planning Meeting", user_id=u.id, status="completed", duration_seconds=120)
                self.db.add(m)
                self.db.commit()
            
            # Ensure action item and decision exist
            item = ActionItem(meeting_id=m.id, title="Finalize test specs", status="pending")
            dec = Decision(meeting_id=m.id, decision_text="Approved architecture")
            self.db.add_all([item, dec])
            self.db.commit()

    def tearDown(self):
        self.db.close()

    def test_meetings_exist_with_relations(self):
        meetings = self.db.query(Meeting).all()
        self.assertGreaterEqual(len(meetings), 1, "Should have seeded or created meetings")
        
        m = meetings[0]
        self.assertIsNotNone(m.title)
        self.assertIsNotNone(m.user_id)
        self.assertIn(m.status, ["processing", "completed", "failed"])

    def test_action_items_and_decisions(self):
        m = self.db.query(Meeting).filter(Meeting.action_items.any()).first()
        self.assertIsNotNone(m)
        
        # Verify action items
        items = self.db.query(ActionItem).filter(ActionItem.meeting_id == m.id).all()
        self.assertGreater(len(items), 0)
        for item in items:
            self.assertIsNotNone(item.title)
            self.assertIn(item.status, ["pending", "completed"])

        # Verify decisions
        decisions = self.db.query(Decision).filter(Decision.meeting_id == m.id).all()
        self.assertGreater(len(decisions), 0)
        self.assertIsNotNone(decisions[0].decision_text)

if __name__ == "__main__":
    unittest.main()
