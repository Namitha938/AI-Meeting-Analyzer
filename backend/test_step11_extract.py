import unittest
from datetime import datetime
from app.ml.extract import (
    extract_action_item,
    extract_actions,
    extract_owner,
    extract_deadline,
    match_person_to_candidates,
)

class TestStep11ActionItemExtraction(unittest.TestCase):
    def setUp(self):
        self.candidate_speakers = ["Sarah Kim", "Marcus Lee", "Jordan Davis"]
        self.meeting_users = ["Alex Rivera", "Elena Rostova"]

    def test_01_owner_matching_to_meeting_speakers_and_users(self):
        """Test matching extracted person names to candidate speakers or registered users."""
        # Exact match
        self.assertEqual(match_person_to_candidates("Sarah Kim", self.candidate_speakers), "Sarah Kim")

        # First name match
        self.assertEqual(match_person_to_candidates("Marcus", self.candidate_speakers), "Marcus Lee")
        self.assertEqual(match_person_to_candidates("Jordan", self.candidate_speakers), "Jordan Davis")

        # User roster match
        self.assertEqual(match_person_to_candidates("Elena", self.meeting_users), "Elena Rostova")
        self.assertEqual(match_person_to_candidates("Alex", self.meeting_users), "Alex Rivera")

    def test_02_spacy_ner_owner_resolution(self):
        """Test spaCy NER extraction and matching on directed tasks."""
        # 1. Directed assignment: "Marcus will deploy..."
        owner1 = extract_owner(
            "Marcus will deploy the release candidate by Friday.",
            speaker="Sarah Kim",
            candidate_speakers=self.candidate_speakers,
        )
        self.assertEqual(owner1, "Marcus Lee")

        # 2. Addressed task: "Sarah, please review the PR..."
        owner2 = extract_owner(
            "Sarah, please review the database migrations today.",
            speaker="Marcus Lee",
            candidate_speakers=self.candidate_speakers,
        )
        self.assertEqual(owner2, "Sarah Kim")

        # 3. Self-commitment: "I'll finalize the API docs..." spoken by Jordan Davis
        owner3 = extract_owner(
            "I'll finalize the API documentation by Friday morning.",
            speaker="Jordan Davis",
            candidate_speakers=self.candidate_speakers,
        )
        self.assertEqual(owner3, "Jordan Davis")

        print("\n--- spaCy NER Owner Matching Verification ---")
        print(f"Task 1 ('Marcus will deploy...'): Owner -> {owner1}")
        print(f"Task 2 ('Sarah, please review...'): Owner -> {owner2}")
        print(f"Task 3 ('I'll finalize API docs...'): Owner -> {owner3}")

    def test_03_dateparser_deadline_parsing(self):
        """Test dateparser extracting natural language deadlines into concrete ISO timestamps."""
        # Friday deadline
        display1, iso1 = extract_deadline("I'll finalize the API documentation by Friday.")
        self.assertEqual(display1.lower(), "friday")
        self.assertIsNotNone(iso1)
        # Ensure valid ISO date format YYYY-MM-DD
        self.assertRegex(iso1, r"^\d{4}-\d{2}-\d{2}$")

        # Monday deadline
        display2, iso2 = extract_deadline("Marcus will deploy the release by Monday.")
        self.assertEqual(display2.lower(), "monday")
        self.assertIsNotNone(iso2)
        self.assertRegex(iso2, r"^\d{4}-\d{2}-\d{2}$")

        # Tomorrow deadline
        display3, iso3 = extract_deadline("We need to update the Figma tokens by tomorrow.")
        self.assertEqual(display3.lower(), "tomorrow")
        self.assertIsNotNone(iso3)

        # No deadline (fallback to TBD)
        display4, iso4 = extract_deadline("Let's make sure the unit tests pass.")
        self.assertEqual(display4, "TBD")
        self.assertIsNone(iso4)

        print("\n--- dateparser Deadline Extraction Verification ---")
        print(f"'by Friday' -> Display: {display1}, Parsed ISO: {iso1}")
        print(f"'by Monday' -> Display: {display2}, Parsed ISO: {iso2}")
        print(f"'by tomorrow' -> Display: {display3}, Parsed ISO: {iso3}")
        print(f"No deadline -> Display: {display4}, Parsed ISO: {iso4}")

    def test_04_end_to_end_extract_actions_from_transcript(self):
        """Test full extraction across multi-speaker transcript."""
        transcript = [
            {
                "speaker": "Sarah Kim",
                "text": "Good morning everyone. Let's review the Q3 milestones.",
                "is_action_item": False,
            },
            {
                "speaker": "Marcus Lee",
                "text": "I'll finalize the API documentation by Friday.",
                "is_action_item": True,
            },
            {
                "speaker": "Sarah Kim",
                "text": "Let's go with PostgreSQL for the database.",
                "is_action_item": False,
            },
            {
                "speaker": "Marcus Lee",
                "text": "Jordan will schedule 5 customer beta interviews by next Monday.",
                "is_action_item": True,
            },
        ]

        actions = extract_actions(transcript, candidate_speakers=self.candidate_speakers)

        self.assertEqual(len(actions), 2)

        # Item 1: Marcus self-assigned
        self.assertEqual(actions[0]["owner"], "Marcus Lee")
        self.assertEqual(actions[0]["deadline"].lower(), "friday")
        self.assertIsNotNone(actions[0]["deadline_date"])

        # Item 2: Jordan assigned by Marcus
        self.assertEqual(actions[1]["owner"], "Jordan Davis")
        self.assertTrue("monday" in actions[1]["deadline"].lower())
        self.assertIsNotNone(actions[1]["deadline_date"])

        print(f"\n--- End-to-End Action Items Extracted ({len(actions)}) ---")
        for act in actions:
            print(f"Task: '{act['title']}' | Owner: {act['owner']} | Deadline: {act['deadline']} ({act['deadline_date']})")

if __name__ == "__main__":
    unittest.main()
