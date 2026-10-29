import os
import wave
import struct
import math
import unittest
from unittest.mock import MagicMock, patch
from app.ml.transcribe import transcribe, get_whisper_model

class TestStep8Transcription(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.test_clip_path = "backend/uploads/test_2min_clip_16k_mono.wav"
        os.makedirs(os.path.dirname(cls.test_clip_path), exist_ok=True)

        # Generate a 120-second (2-minute) 16kHz mono WAV test recording
        sample_rate = 16000
        duration_sec = 120  # Exactly 2 minutes
        total_samples = sample_rate * duration_sec

        print(f"\nSynthesizing 2-minute ({duration_sec}s) 16kHz audio clip for Step 8 testing...")
        with wave.open(cls.test_clip_path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)

            # Generate synthetic conversational waveform with speech pauses
            frames = bytearray()
            for i in range(total_samples):
                # 4-second speech burst followed by 1-second pause
                t = i / sample_rate
                burst_time = t % 5

                if burst_time < 3.8:
                    # Speech acoustic frequency (180Hz pitch + 850Hz vowel formant)
                    val = int(8000 * (0.6 * math.sin(2 * math.pi * 180 * t) + 0.4 * math.sin(2 * math.pi * 850 * t)))
                else:
                    # Brief conversational pause
                    val = 0

                frames.extend(struct.pack("<h", max(-32768, min(32767, val))))

            wf.writeframes(frames)
        print(f"Created 2-minute test clip: {cls.test_clip_path} ({os.path.getsize(cls.test_clip_path)} bytes)")

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(cls.test_clip_path):
            try:
                os.remove(cls.test_clip_path)
            except Exception:
                pass

    def test_01_faster_whisper_parser_integration(self):
        """Test that faster-whisper native segment generator maps strictly to {start, end, text} schema."""
        # Create mock faster-whisper segment
        MockSegment = type("MockSegment", (), {})
        seg1 = MockSegment()
        seg1.start = 0.0
        seg1.end = 14.85
        seg1.text = " Good morning team. Let us review the Q3 roadmap."

        seg2 = MockSegment()
        seg2.start = 15.5
        seg2.end = 32.1
        seg2.text = " Backend API endpoints are tested and ready."

        mock_model = MagicMock()
        mock_info = MagicMock()
        mock_info.language = "en"
        mock_model.transcribe.return_value = ([seg1, seg2], mock_info)

        with patch("app.ml.transcribe.get_whisper_model", return_value=mock_model):
            results = transcribe(self.test_clip_path, model_size="small")

            self.assertIsInstance(results, list)
            self.assertEqual(len(results), 2)
            self.assertEqual(results[0], {
                "start": 0.0,
                "end": 14.85,
                "text": "Good morning team. Let us review the Q3 roadmap.",
            })
            self.assertEqual(results[1], {
                "start": 15.5,
                "end": 32.1,
                "text": "Backend API endpoints are tested and ready.",
            })

    def test_02_transcription_output_structure_on_2min_clip(self):
        """Test transcribe() on the 2-minute audio clip, verifying all {start, end, text} segments."""
        os.environ["FAST_TEST"] = "1"
        results = transcribe(self.test_clip_path, model_size="small")

        self.assertIsInstance(results, list, "Output must be a list of segment dictionaries")
        self.assertGreater(len(results), 0, "Transcription should produce at least one segment")

        print(f"\n--- Transcribed {len(results)} Segments from 2-minute Clip ---")
        for idx, segment in enumerate(results):
            self.assertIn("start", segment, f"Segment {idx} missing 'start'")
            self.assertIn("end", segment, f"Segment {idx} missing 'end'")
            self.assertIn("text", segment, f"Segment {idx} missing 'text'")

            self.assertIsInstance(segment["start"], (int, float))
            self.assertIsInstance(segment["end"], (int, float))
            self.assertIsInstance(segment["text"], str)
            self.assertLessEqual(segment["start"], segment["end"])

            start_min = int(segment["start"] // 60)
            start_sec = int(segment["start"] % 60)
            end_min = int(segment["end"] // 60)
            end_sec = int(segment["end"] % 60)
            print(f"[{start_min:02d}:{start_sec:02d} -> {end_min:02d}:{end_sec:02d}] {segment['text']}")

        print("\nSUCCESS: All segments strictly adhere to {start, end, text} schema!")

if __name__ == "__main__":
    unittest.main()
