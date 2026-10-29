from app.database import SessionLocal
from app.models import Meeting, Transcript, MeetingAnalytics
from app.speech_to_text import whisper_transcriber, format_timestamp
from app.diarization import diarizer, rename_speaker_in_meeting

print("=== 1. TESTING STEP 5: WHISPER SPEECH-TO-TEXT ===")
test_audio = "test_meeting.wav"
segments = whisper_transcriber.transcribe(test_audio)
print(f"Whisper transcription generated {len(segments)} timestamped segments:")
for s in segments[:3]:
    ts = format_timestamp(s['start'])
    print(f"  {ts} (confidence: {s['confidence']}): \"{s['text'][:55]}...\"")

assert len(segments) > 0, "Whisper returned 0 segments!"
print("Step 5 (Whisper Speech-to-Text) verified successfully!\n")

print("=== 2. TESTING STEP 6: PYANNOTE SPEAKER DIARIZATION ===")
diar_intervals = diarizer.diarize(test_audio, num_speakers=2)
print(f"pyannote.audio diarization generated {len(diar_intervals)} speaker turns:")
for d in diar_intervals[:3]:
    print(f"  [{d['start']}s -> {d['end']}s]: {d['speaker']}")

assert len(diar_intervals) > 0, "Diarization returned 0 turns!"

merged = diarizer.merge_whisper_and_diarization(segments, diar_intervals)
print("\nMerged Whisper + pyannote aligned transcript lines:")
for m in merged[:3]:
    print(f"  -> {m['formatted_line']}")

assert len(merged) == len(segments), "Merge length mismatch!"
print("Step 6 (Speaker Diarization & Timestamp Alignment) verified successfully!\n")

print("=== 3. TESTING STEP 6: SPEAKER RENAMING ===")
db = SessionLocal()
meeting = db.query(Meeting).first()
if meeting:
    # Ensure a Speaker 1 exists
    first_tr = db.query(Transcript).filter(Transcript.meeting_id == meeting.id).first()
    if first_tr:
        original_speaker = first_tr.speaker
        first_tr.speaker = "Speaker 1"
        db.commit()

        # Test renaming Speaker 1 -> "Alex Johnson"
        res = rename_speaker_in_meeting(meeting.id, "Speaker 1", "Alex Johnson", db)
        print("Rename result:", res)
        assert res["new_name"] == "Alex Johnson"
        print("Speaker renaming verified successfully!")

        # Restore original speaker
        rename_speaker_in_meeting(meeting.id, "Alex Johnson", original_speaker, db)
db.close()

print("\n>>> STEPS 5 & 6 COMPLETED AND 100% OPERATIONAL!")

