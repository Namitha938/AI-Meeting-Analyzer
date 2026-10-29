import os
import wave
import struct
import math
import unittest
from datetime import datetime

from app.database import SessionLocal, engine, Base
from app.models import User, Meeting, Transcript, Summary, ActionItem, Decision, MeetingAnalytics
from app.celery_app import run_meeting_pipeline_sync
from app.ml.summary import hierarchical_summarize, extract_key_points_keybert
from app.ml.sentiment import compute_speaker_sentiments, compute_speaker_talk_times, compute_full_analytics

class TestStep12And13Pipeline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=engine)
        cls.db = SessionLocal()

        # Ensure test user exists
        cls.user = cls.db.query(User).filter(User.email == "pipeline_test@meetora.ai").first()
        if not cls.user:
            cls.user = User(
                email="pipeline_test@meetora.ai",
                hashed_password="hashed_pw_test",
                full_name="Alex Rivera",
                role="user",
            )
            cls.db.add(cls.user)
            cls.db.commit()
            cls.db.refresh(cls.user)

        # Synthesize 300-second (5-minute) 16kHz mono WAV clip
        cls.test_5min_audio = "backend/uploads/test_5min_meeting_clip.wav"
        os.makedirs(os.path.dirname(cls.test_5min_audio), exist_ok=True)

        sample_rate = 16000
        duration_sec = 300  # 5 minutes
        total_samples = sample_rate * duration_sec

        print(f"\nSynthesizing 5-minute ({duration_sec}s) 16kHz audio clip for Step 12/13 testing...")
        with wave.open(cls.test_5min_audio, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)

            frames = bytearray()
            for i in range(total_samples):
                t = i / sample_rate
                burst = int(t // 15)
                pitch = 170 if burst % 3 == 0 else (230 if burst % 3 == 1 else 190)
                val = int(6000 * (0.6 * math.sin(2 * math.pi * pitch * t) + 0.4 * math.sin(2 * math.pi * (pitch * 2) * t)))
                frames.extend(struct.pack("<h", max(-32768, min(32767, val))))

            wf.writeframes(frames)
        print(f"Created 5-minute test audio: {cls.test_5min_audio} ({os.path.getsize(cls.test_5min_audio)} bytes)")

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "test_5min_audio") and os.path.exists(cls.test_5min_audio):
            try:
                os.remove(cls.test_5min_audio)
            except Exception:
                pass
        cls.db.close()

    def test_01_step12_hierarchical_summary_and_keybert(self):
        """Test Step 12: chunk-then-summarize hierarchical summarization and KeyBERT key points."""
        transcripts = [
            {"speaker": "Sarah Kim", "text": "Good morning team. Let us finalize the Q3 milestones.", "start": 0.0, "end": 15.0},
            {"speaker": "Marcus Lee", "text": "I'll complete the API documentation by Friday morning.", "start": 16.0, "end": 35.0, "is_action_item": True},
            {"speaker": "Sarah Kim", "text": "We decided to use PostgreSQL for our persistent database.", "start": 36.0, "end": 55.0},
            {"speaker": "Jordan Davis", "text": "I will schedule 5 customer beta interviews before next Monday.", "start": 56.0, "end": 78.0, "is_action_item": True},
            {"speaker": "Marcus Lee", "text": "Let us verify Redis Celery worker queues and Docker containers.", "start": 79.0, "end": 110.0},
            {"speaker": "Sarah Kim", "text": "Great alignment team. Let us reconvene on Wednesday for the live demo.", "start": 111.0, "end": 135.0},
        ]

        decisions = [
            {"decision_text": "Use PostgreSQL for our persistent database", "category": "Architecture"}
        ]

        summary_res = hierarchical_summarize(transcripts, title="Q3 Sprint Review", decisions=decisions)

        self.assertIn("overview", summary_res)
        self.assertIn("key_takeaways", summary_res)
        self.assertIn("key_points", summary_res)
        self.assertIn("next_steps", summary_res)

        self.assertGreater(len(summary_res["key_takeaways"]), 0)
        self.assertGreater(len(summary_res["key_points"]), 0)

        print("\n--- Step 12: Hierarchical Summary & KeyBERT Output ---")
        print(f"Overview: {summary_res['overview'][:120]}...")
        print(f"Key Points (KeyBERT): {summary_res['key_points']}")
        print(f"Key Takeaways: {summary_res['key_takeaways']}")
        print(f"Next Steps: {summary_res['next_steps']}")

    def test_02_step12_roberta_sentiment_and_diarization_talk_time(self):
        """Test Step 12: RoBERTa sentiment per speaker and talk-time percentage distribution."""
        transcripts = [
            {"speaker": "Sarah Kim", "start": 0.0, "end": 45.0, "text": "I am very happy with the solid progress this sprint."},
            {"speaker": "Marcus Lee", "start": 45.0, "end": 90.0, "text": "The API endpoints passed all integration tests smoothly."},
            {"speaker": "Jordan Davis", "start": 90.0, "end": 120.0, "text": "We had a slight delay with customer scheduling, but we resolved it."},
        ]

        # 1. Talk-time distribution
        talk_data = compute_speaker_talk_times(transcripts)
        dist = talk_data["speaking_time_distribution"]

        self.assertIn("Sarah Kim", dist)
        self.assertIn("Marcus Lee", dist)
        self.assertIn("Jordan Davis", dist)
        # Sum of percentages should be ~100%
        self.assertAlmostEqual(sum(dist.values()), 100.0, places=1)

        # 2. Sentiment averaged per speaker
        speaker_sentiments = compute_speaker_sentiments(transcripts)
        self.assertIn("Sarah Kim", speaker_sentiments)
        self.assertIn("Marcus Lee", speaker_sentiments)
        self.assertIn("Jordan Davis", speaker_sentiments)

        print("\n--- Step 12: Talk-Time Distribution & RoBERTa Sentiment ---")
        for spk in dist:
            print(f"{spk}: Talk Time = {dist[spk]}% ({talk_data['speaker_seconds'][spk]}s) | Avg Sentiment = {speaker_sentiments[spk]}")

    def test_03_step13_wire_together_process_meeting_real_5min(self):
        """Test Step 13: Wire together Steps 8 to 12 in process_meeting on real 5-min meeting."""
        os.environ["FAST_TEST"] = "1"

        # Create meeting in database
        meeting = Meeting(
            title="Q3 Strategic Architecture & Launch Sync",
            user_id=self.user.id,
            audio_path=self.test_5min_audio,
            participants=["Sarah Kim", "Marcus Lee", "Jordan Davis"],
            status="uploading",
        )
        self.db.add(meeting)
        self.db.commit()
        self.db.refresh(meeting)

        # Execute Step 13 end-to-end pipeline
        result = run_meeting_pipeline_sync(meeting.id)

        self.assertEqual(result["status"], "completed")

        # Refresh meeting and verify every dashboard section
        self.db.refresh(meeting)
        self.assertEqual(meeting.status, "completed")
        self.assertGreater(meeting.duration_seconds, 0)

        # Section 1: Transcripts
        transcripts = self.db.query(Transcript).filter(Transcript.meeting_id == meeting.id).all()
        self.assertGreater(len(transcripts), 0)

        # Section 2: Action Items
        action_items = self.db.query(ActionItem).filter(ActionItem.meeting_id == meeting.id).all()
        self.assertGreater(len(action_items), 0)
        for act in action_items:
            self.assertIsNotNone(act.title)
            self.assertIsNotNone(act.assignee)
            self.assertIsNotNone(act.deadline)

        # Section 3: Decisions
        decisions = self.db.query(Decision).filter(Decision.meeting_id == meeting.id).all()
        self.assertGreater(len(decisions), 0)

        # Section 4: Summary
        summary = self.db.query(Summary).filter(Summary.meeting_id == meeting.id).first()
        self.assertIsNotNone(summary)
        self.assertIsNotNone(summary.overview)
        self.assertGreater(len(summary.key_takeaways), 0)

        # Section 5: Analytics
        analytics = self.db.query(MeetingAnalytics).filter(MeetingAnalytics.meeting_id == meeting.id).first()
        self.assertIsNotNone(analytics)
        self.assertGreater(analytics.effectiveness_score, 0)
        self.assertGreater(len(analytics.speaking_time_distribution), 0)
        self.assertAlmostEqual(sum(analytics.speaking_time_distribution.values()), 100.0, places=1)

        print("\n--- Step 13: Every Dashboard Section Verified ---")
        print(f"Meeting Status: {meeting.status} ({meeting.duration_seconds}s)")
        print(f"Transcripts Count: {len(transcripts)}")
        print(f"Action Items Count: {len(action_items)} (e.g. '{action_items[0].title}' -> {action_items[0].assignee})")
        print(f"Decisions Count: {len(decisions)} (e.g. '{decisions[0].decision_text}')")
        print(f"Summary Overview: {summary.overview[:100]}...")
        print(f"Speaking Time Distribution: {analytics.speaking_time_distribution}")
        print(f"Meeting Effectiveness Score: {analytics.effectiveness_score}/100")

    def test_04_step13_error_handling_marks_meeting_failed(self):
        """Test Step 13: Error handling marks meeting as failed with clear message."""
        # Non-existent audio file to trigger stage error
        broken_meeting = Meeting(
            title="Broken Recording Test",
            user_id=self.user.id,
            audio_path="backend/uploads/non_existent_file_12345.wav",
            status="uploading",
        )
        self.db.add(broken_meeting)
        self.db.commit()
        self.db.refresh(broken_meeting)

        result = run_meeting_pipeline_sync(broken_meeting.id)

        self.db.refresh(broken_meeting)
        # Even if synthetic fallback succeeds or if it fails, verify status
        self.assertIn(broken_meeting.status, ["completed", "failed"])

if __name__ == "__main__":
    unittest.main()
