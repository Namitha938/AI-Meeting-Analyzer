import unittest
from app.nlp_analysis import (
    sentence_classifier,
    InformationExtractor,
    MeetingSummarizer,
    MeetingAnalyticsEngine,
)

class TestDistilBertAndNLP(unittest.TestCase):
    def test_sentence_classifier_four_classes(self):
        cases = [
            ("Marcus will optimize the database queries by Monday.", "action_item"),
            ("We agreed to adopt PostgreSQL for our relational data layer.", "decision"),
            ("What are the primary differences between DistilBERT and BERT?", "question"),
            ("Good morning everyone, thanks for joining today's standup call.", "general")
        ]
        for sentence, expected in cases:
            res = sentence_classifier.classify_sentence(sentence)
            self.assertEqual(res["label"], expected, f"Failed for '{sentence}': got {res['label']}")
            self.assertGreaterEqual(res["confidence"], 0.70)

    def test_ner_and_deadline_extraction(self):
        sentence = "Sarah, please review the mobile onboarding flows before our sprint demo on Friday."
        deadline = InformationExtractor.extract_deadline(sentence)
        assignee = InformationExtractor.extract_assignee(sentence, speaker="Speaker 1", participants=["Sarah Kim", "Marcus Lee"])
        priority = InformationExtractor.extract_priority(sentence)

        self.assertIn("Sarah", assignee)
        self.assertEqual(deadline, "Friday")
        self.assertIn(priority, ["high", "medium", "low"])

    def test_hierarchical_summarization(self):
        lines = [
            {"speaker": "Sarah Kim", "start_time": 0.0, "end_time": 15.0, "text": "Good morning team, let's nail down our launch milestones."},
            {"speaker": "Marcus Lee", "start_time": 15.0, "end_time": 35.0, "text": "The backend endpoints are solid and verified."}
        ]
        decisions = [{"decision_text": "Confirmed launch target", "category": "Timeline"}]
        summary = MeetingSummarizer.generate_summary("Beta Sync", lines, decisions)
        self.assertIn("overview", summary)
        self.assertIsInstance(summary["key_takeaways"], list)
        self.assertGreater(len(summary["key_takeaways"]), 0)

    def test_sentiment_and_speaking_time(self):
        lines = [
            {"speaker": "Sarah Kim", "start_time": 0.0, "end_time": 30.0, "text": "Great work team!"},
            {"speaker": "Marcus Lee", "start_time": 30.0, "end_time": 50.0, "text": "Everything is on schedule."}
        ]
        stats = MeetingAnalyticsEngine.analyze_sentiment_and_dynamics(lines, ["Sarah Kim", "Marcus Lee"])
        self.assertGreater(stats["sentiment_score"], 0.5)
        self.assertIn("Sarah Kim", stats["speaking_time_distribution"])
        self.assertIn("Marcus Lee", stats["speaking_time_distribution"])

if __name__ == "__main__":
    unittest.main()
