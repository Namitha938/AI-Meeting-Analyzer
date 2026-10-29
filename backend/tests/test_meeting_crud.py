import unittest
from app.database import SessionLocal
from app.models import Meeting, User, ActionItem, Decision, Transcript

class TestMeetingCRUD(unittest.TestCase):
    def setUp(self):
        self.db = SessionLocal()

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
        m = self.db.query(Meeting).first()
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

