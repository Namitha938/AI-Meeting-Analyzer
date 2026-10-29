import os
import wave
import struct
import math
import unittest
from unittest.mock import MagicMock, patch

from app.ml.transcribe import transcribe
from app.ml.diarize import diarize, merge_speaker_turns, get_diarization_pipeline

class TestStep9SpeakerDiarization(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.test_clip_path = "backend/uploads/test_step9_diarize_clip.wav"
        os.makedirs(os.path.dirname(cls.test_clip_path), exist_ok=True)

        # Generate a 120-second (2-minute) 16kHz mono WAV audio file
        sample_rate = 16000
        duration_sec = 120
        total_samples = sample_rate * duration_sec

        with wave.open(cls.test_clip_path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)

            frames = bytearray()
            for i in range(total_samples):
                t = i / sample_rate
                # Alternate voice pitches between speakers (Speaker 1 ~ 160Hz, Speaker 2 ~ 240Hz, Speaker 3 ~ 190Hz)
                burst = int(t // 15)
                pitch = 160 if burst % 3 == 0 else (240 if burst % 3 == 1 else 190)
                val = int(8000 * (0.6 * math.sin(2 * math.pi * pitch * t) + 0.4 * math.sin(2 * math.pi * (pitch * 3) * t)))
                frames.extend(struct.pack("<h", max(-32768, min(32767, val))))

            wf.writeframes(frames)

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(cls.test_clip_path):
            try:
                os.remove(cls.test_clip_path)
            except Exception:
                pass

    def test_01_merge_by_timestamp_overlap(self):
        """Test timestamp overlap resolution between transcripts and speaker turns."""
        transcript_segments = [
            {"start": 0.0, "end": 10.0, "text": "Good morning team, let's start the sync."},
            {"start": 10.0, "end": 28.0, "text": "The API endpoints and migrations are completed."},
            {"start": 28.0, "end": 45.0, "text": "I will handle customer beta testing and feedback."},
        ]

        speaker_turns = [
            {"speaker": "Speaker 1", "start": 0.0, "end": 12.0},    # Overlaps seg 1 (10s) and seg 2 (2s)
            {"speaker": "Speaker 2", "start": 12.0, "end": 30.0},   # Overlaps seg 2 (16s) and seg 3 (2s)
            {"speaker": "Speaker 3", "start": 30.0, "end": 50.0},   # Overlaps seg 3 (15s)
        ]

        participants = ["Sarah Kim", "Marcus Lee", "Jordan Davis"]

        merged = merge_speaker_turns(transcript_segments, speaker_turns, known_participants=participants)

        self.assertEqual(len(merged), 3)

        # Seg 1: 0-10s -> matches Speaker 1 ("Sarah Kim") with 10s overlap
        self.assertEqual(merged[0]["speaker"], "Sarah Kim")
        self.assertEqual(merged[0]["overlap_duration"], 10.0)

        # Seg 2: 10-28s -> overlaps Speaker 1 by 2s (10-12s) and Speaker 2 by 16s (12-28s). Max overlap is Speaker 2 ("Marcus Lee")
        self.assertEqual(merged[1]["speaker"], "Marcus Lee")
        self.assertEqual(merged[1]["overlap_duration"], 16.0)

        # Seg 3: 28-45s -> overlaps Speaker 2 by 2s (28-30s) and Speaker 3 by 15s (30-45s). Max overlap is Speaker 3 ("Jordan Davis")
        self.assertEqual(merged[2]["speaker"], "Jordan Davis")
        self.assertEqual(merged[2]["overlap_duration"], 15.0)

        print("\n--- Timestamp Overlap Verification ---")
        for row in merged:
            print(f"{row['formatted_line']} [Overlap: {row['overlap_duration']}s]")

    def test_02_pyannote_pipeline_parser(self):
        """Test pyannote.audio mock integration and track label parsing."""
        MockTurn = type("MockTurn", (), {})
        turn1 = MockTurn()
        turn1.start = 0.0
        turn1.end = 15.2

        turn2 = MockTurn()
        turn2.start = 16.0
        turn2.end = 35.5

        mock_diarization = MagicMock()
        mock_diarization.itertracks.return_value = [
            (turn1, None, "SPEAKER_00"),
            (turn2, None, "SPEAKER_01"),
        ]

        mock_pipeline = MagicMock(return_value=mock_diarization)

        with patch("app.ml.diarize.get_diarization_pipeline", return_value=mock_pipeline):
            intervals = diarize(self.test_clip_path, num_speakers=2)

            self.assertEqual(len(intervals), 2)
            self.assertEqual(intervals[0]["speaker"], "Speaker 00")
            self.assertEqual(intervals[0]["start"], 0.0)
            self.assertEqual(intervals[0]["end"], 15.2)

            self.assertEqual(intervals[1]["speaker"], "Speaker 01")
            self.assertEqual(intervals[1]["start"], 16.0)
            self.assertEqual(intervals[1]["end"], 35.5)

    def test_03_end_to_end_transcription_and_diarization_merge(self):
        """Test end-to-end: transcribe 2-min clip, diarize speaker turns, and merge by timestamp overlap."""
        os.environ["FAST_TEST"] = "1"

        # 1. Transcribe audio clip
        transcripts = transcribe(self.test_clip_path, model_size="small")
        self.assertGreater(len(transcripts), 0)

        # 2. Diarize speaker turns
        speaker_turns = diarize(self.test_clip_path, num_speakers=3)
        self.assertGreater(len(speaker_turns), 0)

        # 3. Merge by timestamp overlap
        team_members = ["Sarah Kim", "Marcus Lee", "Jordan Davis"]
        merged = merge_speaker_turns(transcripts, speaker_turns, known_participants=team_members)

        self.assertEqual(len(merged), len(transcripts))

        print(f"\n--- End-to-End Diarized Meeting Transcript ({len(merged)} turns) ---")
        for item in merged:
            self.assertIn("speaker", item)
            self.assertIn("start", item)
            self.assertIn("end", item)
            self.assertIn("text", item)
            self.assertIn("formatted_line", item)
            self.assertIn("timestamp_str", item)
            self.assertIn(item["speaker"], team_members)
            print(f"{item['formatted_line']}")

        print("\nSUCCESS: Speaker diarization and timestamp overlap merging verified!")

if __name__ == "__main__":
    unittest.main()
