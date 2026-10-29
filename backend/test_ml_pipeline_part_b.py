import os
import unittest
from app.ml.transcription import transcribe_audio
from app.ml.diarization import diarize_audio, merge_transcripts
from app.ml.classifier import classify_sentence, classify_batch
from app.ml.extraction import extract_action_items, extract_decisions
from app.ml.summarizer import generate_summary
from app.ml.analytics import compute_analytics
from app.ml.pipeline import run_ml_pipeline

class TestMLPipelinePartB(unittest.TestCase):

    def test_01_transcription_module(self):
        """Test Module 1: Whisper speech transcription."""
        segments = transcribe_audio("test_sample.wav")
        self.assertIsInstance(segments, list)
        self.assertGreater(len(segments), 0)
        self.assertIn("start_time", segments[0])
        self.assertIn("text", segments[0])
        print(f"Module 1 (Transcription) verified: {len(segments)} segments generated.")

    def test_02_diarization_module(self):
        """Test Module 2: Speaker diarization and turn merging."""
        turns = diarize_audio("test_sample.wav", num_speakers=3)
        self.assertIsInstance(turns, list)
        self.assertGreater(len(turns), 0)
        self.assertIn("speaker", turns[0])

        # Test merge
        segments = transcribe_audio("test_sample.wav")
        merged = merge_transcripts(segments, turns, ["Sarah Kim", "Marcus Lee"])
        self.assertGreater(len(merged), 0)
        self.assertIn("speaker", merged[0])
        self.assertIn(merged[0]["speaker"], ["Sarah Kim", "Marcus Lee", "Speaker 1", "Speaker 2"])
        print(f"Module 2 (Diarization) verified: {len(turns)} turns diarized and merged.")

    def test_03_classifier_module(self):
        """Test Module 3: Sentence Intent Classifier."""
        # Action Item
        res_action = classify_sentence("I will prepare the API swagger docs and share them by Monday morning.")
        self.assertEqual(res_action["top_class"], "action_item")
        self.assertGreater(res_action["confidence"], 0.4)

        # Decision
        res_decision = classify_sentence("We agreed to adopt PostgreSQL with pgvector as our primary database.")
        self.assertEqual(res_decision["top_class"], "decision")

        # Question
        res_question = classify_sentence("Who is responsible for the weekly email digest automation?")
        self.assertEqual(res_question["top_class"], "question")

        # General Chatter
        res_general = classify_sentence("Good morning everyone, thanks for joining today's product sync on time.")
        self.assertEqual(res_general["top_class"], "general")

        print("Module 3 (Sentence Classifier) verified across all 4 target intent classes.")

    def test_04_extraction_module(self):
        """Test Module 4: Action Item & Decision Extraction."""
        sample_transcripts = [
            {"speaker": "Marcus Lee", "text": "I will share the updated API swagger specifications by Monday."},
            {"speaker": "Sarah Kim", "text": "We agreed to postpone the mobile rollout to Q3."},
            {"speaker": "Jordan Davis", "text": "Can someone check if the Redis worker is healthy?"},
            {"speaker": "Sarah Kim", "text": "Please review the onboarding Figma mockups before Friday."},
        ]

        actions = extract_action_items(sample_transcripts)
        self.assertGreaterEqual(len(actions), 1)
        self.assertEqual(actions[0]["assignee"], "Marcus Lee")
        self.assertEqual(actions[0]["deadline"], "Monday")

        decisions = extract_decisions(sample_transcripts)
        self.assertGreaterEqual(len(decisions), 1)
        self.assertIn("postpone the mobile rollout", decisions[0]["decision_text"])
        print(f"Module 4 (Extraction) verified: {len(actions)} actions, {len(decisions)} decisions parsed.")

    def test_05_summarizer_module(self):
        """Test Module 5: Executive Meeting Summarizer."""
        sample_transcripts = [
            {"speaker": "Jordan Davis", "text": "Let's review the Q3 roadmap milestones."},
            {"speaker": "Sarah Kim", "text": "Onboarding UX is our top priority for the beta rollout."},
        ]
        sample_decisions = [{"decision_text": "Prioritize mobile UX flows"}]
        summary = generate_summary("Sprint Sync", sample_transcripts, sample_decisions)
        self.assertIn("overview", summary)
        self.assertIn("key_takeaways", summary)
        self.assertGreater(len(summary["overview"]), 20)
        print("Module 5 (Summarizer) verified: Executive overview and key takeaways generated.")

    def test_06_analytics_module(self):
        """Test Module 6: Conversational Analytics."""
        sample_transcripts = [
            {"speaker": "Sarah Kim", "text": "The feedback from our pilot cohort has been amazing and encouraging.", "start_time": 0.0, "end_time": 10.0},
            {"speaker": "Marcus Lee", "text": "I am optimistic about latency benchmarks on the new cluster.", "start_time": 10.5, "end_time": 25.0},
        ]
        analytics = compute_analytics(sample_transcripts)
        self.assertIn("sentiment_score", analytics)
        self.assertIn("speaking_time_distribution", analytics)
        self.assertIn("effectiveness_score", analytics)
        print(f"Module 6 (Analytics) verified: Sentiment={analytics['sentiment_score']}, Effectiveness={analytics['effectiveness_score']}")

    def test_07_composite_pipeline(self):
        """Test Module 7: Composite End-to-End Pipeline."""
        result = run_ml_pipeline(meeting_id=999, audio_path="sample_recording.wav")
        self.assertEqual(result["meeting_id"], 999)
        self.assertIn("transcripts", result)
        self.assertIn("action_items", result)
        self.assertIn("decisions", result)
        self.assertIn("summary", result)
        self.assertIn("analytics", result)
        print("Module 7 (Composite ML Pipeline) verified end-to-end!")

if __name__ == "__main__":
    unittest.main()

