"""
Step 14: Comprehensive Pytest Test Suite
Covers:
  1. Authentication (Registration, Login JWT, /auth/me, Admin RBAC)
  2. Meetings & File Upload (Validation, Conversion, CRUD)
  3. ML Interfaces (Transcription, Diarization Overlap, Trained Classifier, spaCy/dateparser Extraction, Summary & Analytics)
"""

import os
import wave
import struct
import math
from datetime import datetime
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.database import SessionLocal, Base, engine
from app.models import User, Meeting, Transcript, Summary, ActionItem, Decision, MeetingAnalytics
from app.auth import get_password_hash, create_access_token
from app.ml.transcribe import transcribe
from app.ml.diarize import diarize, merge_speaker_turns
from app.ml.classifier import predict, predict_one, RuleBasedPlaceholder
from app.ml.extract import extract_action_item, extract_actions, extract_owner, extract_deadline
from app.ml.summary import hierarchical_summarize, extract_key_points_keybert
from app.ml.sentiment import compute_speaker_sentiments, compute_speaker_talk_times, compute_full_analytics

client = TestClient(app)

@pytest.fixture(scope="module")
def db_session():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    yield db
    db.close()

@pytest.fixture(scope="module")
def test_audio_file():
    """Generates temporary 16kHz mono audio file for upload testing."""
    os.makedirs("backend/uploads", exist_ok=True)
    audio_path = "backend/uploads/pytest_sample_16k_mono.wav"
    sample_rate = 16000
    duration_sec = 10
    total_samples = sample_rate * duration_sec

    with wave.open(audio_path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        frames = bytearray()
        for i in range(total_samples):
            t = i / sample_rate
            val = int(5000 * math.sin(2 * math.pi * 220 * t))
            frames.extend(struct.pack("<h", val))
        wf.writeframes(frames)

    yield audio_path

    if os.path.exists(audio_path):
        try:
            os.remove(audio_path)
        except Exception:
            pass


# =============================================================================
# 1. AUTHENTICATION TESTS
# =============================================================================

def test_auth_register_and_password_hashing(db_session):
    """Test user registration and bcrypt password hashing."""
    email = f"pytest_user_{int(datetime.now().timestamp())}@meetora.ai"
    payload = {
        "email": email,
        "password": "SecurePassword123!",
        "full_name": "Test Pytest Engineer",
    }
    response = client.post("/auth/register", json=payload)
    assert response.status_code in [200, 201]
    data = response.json()
    assert data["email"] == email
    assert "id" in data

    # Verify password was hashed and not stored in plaintext
    user = db_session.query(User).filter(User.email == email).first()
    assert user is not None
    assert user.hashed_password != payload["password"]
    assert user.hashed_password.startswith("$2") or len(user.hashed_password) > 30

def test_auth_login_jwt_and_me():
    """Test login returns JWT access token and GET /auth/me returns user profile."""
    email = f"pytest_jwt_{int(datetime.now().timestamp())}@meetora.ai"
    password = "MySecretPassword456!"

    reg_res = client.post("/auth/register", json={"email": email, "password": password, "full_name": "JWT User"})
    assert reg_res.status_code in [200, 201]

    # Login with JSON body
    login_res = client.post("/auth/login", json={"email": email, "password": password})
    assert login_res.status_code == 200
    token_data = login_res.json()
    assert "access_token" in token_data
    assert token_data["token_type"].lower() == "bearer"
    token = token_data["access_token"]

    # Access /auth/me with Authorization header
    me_res = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200
    me_data = me_res.json()
    assert me_data["email"] == email
    assert me_data["full_name"] == "JWT User"

def test_auth_admin_dependency_rbac(db_session):
    """Test RBAC admin dependency restricts non-admin users."""
    regular_email = f"regular_{int(datetime.now().timestamp())}@meetora.ai"
    admin_email = f"admin_{int(datetime.now().timestamp())}@meetora.ai"

    # Create regular user
    u_reg = User(email=regular_email, hashed_password=get_password_hash("pass123"), role="user")
    u_admin = User(email=admin_email, hashed_password=get_password_hash("pass123"), role="admin")
    db_session.add_all([u_reg, u_admin])
    db_session.commit()

    token_reg = create_access_token(data={"sub": regular_email})
    token_admin = create_access_token(data={"sub": admin_email})

    # Test admin-protected endpoint (e.g. GET /admin/stats)
    res_reg = client.get("/admin/stats", headers={"Authorization": f"Bearer {token_reg}"})
    assert res_reg.status_code in [401, 403]

    res_admin = client.get("/admin/stats", headers={"Authorization": f"Bearer {token_admin}"})
    assert res_admin.status_code == 200


# =============================================================================
# 2. MEETING UPLOAD & CRUD TESTS
# =============================================================================

def test_meeting_create_and_file_validation(test_audio_file):
    """Test creating a meeting, audio file upload, and format validation."""
    token = create_access_token(data={"sub": "pipeline_test@meetora.ai"})

    # 1. Invalid file format rejection
    invalid_file = ("bad_file.txt", b"Invalid text data", "text/plain")
    res_invalid = client.post(
        "/meetings",
        headers={"Authorization": f"Bearer {token}"},
        data={"title": "Invalid File Test", "participants": "Sarah Kim,Marcus Lee"},
        files={"file": invalid_file},
    )
    assert res_invalid.status_code == 400

    # 2. Valid WAV file upload
    with open(test_audio_file, "rb") as af:
        valid_file = ("sample.wav", af.read(), "audio/wav")
        res_valid = client.post(
            "/meetings",
            headers={"Authorization": f"Bearer {token}"},
            data={"title": "Q3 Sprint Planning Sync", "participants": "Sarah Kim,Marcus Lee"},
            files={"file": valid_file},
        )
        assert res_valid.status_code in [200, 201]
        data = res_valid.json()
        assert data["title"] == "Q3 Sprint Planning Sync"
        assert "id" in data
        assert data["status"] in ["uploading", "processing", "transcribing", "completed"]
        meeting_id = data["id"]

    # 3. GET /meetings list and GET /meetings/{id}
    res_list = client.get("/meetings", headers={"Authorization": f"Bearer {token}"})
    assert res_list.status_code == 200
    meetings = res_list.json()
    assert any(m["id"] == meeting_id for m in meetings)

    res_get = client.get(f"/meetings/{meeting_id}", headers={"Authorization": f"Bearer {token}"})
    assert res_get.status_code == 200
    assert res_get.json()["id"] == meeting_id

    # 4. DELETE /meetings/{id}
    res_del = client.delete(f"/meetings/{meeting_id}", headers={"Authorization": f"Bearer {token}"})
    assert res_del.status_code in [200, 204]


# =============================================================================
# 3. ML INTERFACES TESTS
# =============================================================================

def test_ml_step8_transcribe_interface(test_audio_file):
    """Test Step 8 interface: transcribe(audio_path) -> [{start, end, text}]."""
    os.environ["FAST_TEST"] = "1"
    segments = transcribe(test_audio_file, model_size="small")

    assert isinstance(segments, list)
    assert len(segments) > 0
    for seg in segments:
        assert "start" in seg
        assert "end" in seg
        assert "text" in seg
        assert seg["start"] <= seg["end"]
        assert isinstance(seg["text"], str)

def test_ml_step9_diarize_and_merge_interface(test_audio_file):
    """Test Step 9 interface: diarize(audio) and merge_speaker_turns(transcripts, turns)."""
    turns = diarize(test_audio_file, num_speakers=3)
    assert isinstance(turns, list)
    assert len(turns) > 0

    transcripts = [
        {"start": 0.0, "end": 10.0, "text": "Good morning team, let's start the review."},
        {"start": 10.0, "end": 25.0, "text": "I'll deliver the database migration by Friday."},
    ]

    merged = merge_speaker_turns(
        transcript=transcripts,
        speaker_turns=turns,
        known_participants=["Sarah Kim", "Marcus Lee", "Jordan Davis"]
    )
    assert len(merged) == len(transcripts)
    assert "speaker" in merged[0]
    assert "formatted_line" in merged[0]
    assert "overlap_duration" in merged[0]

def test_ml_step10_classifier_predict_interface():
    """Test Step 10 interface: predict(sentences) -> [{label, confidence}]."""
    sentences = [
        "I'll finalize the API documentation by Friday.",
        "Let's go with PostgreSQL for the database.",
        "Who is leading the design review?",
        "Good morning everyone, hope you are doing well.",
    ]
    results = predict(sentences)

    assert isinstance(results, list)
    assert len(results) == len(sentences)
    for res in results:
        assert "label" in res
        assert "confidence" in res
        assert res["label"] in ["action_item", "decision", "question", "general"]
        assert 0.0 <= res["confidence"] <= 1.0

    assert results[0]["label"] == "action_item"
    assert results[1]["label"] == "decision"
    assert results[2]["label"] == "question"
    assert results[3]["label"] == "general"

def test_ml_step11_extract_actions_interface():
    """Test Step 11 interface: spaCy NER owner matching and dateparser deadlines."""
    transcript = [
        {
            "speaker": "Sarah Kim",
            "text": "Marcus will deploy the release by Friday.",
            "is_action_item": True,
        },
        {
            "speaker": "Marcus Lee",
            "text": "I'll schedule 5 customer beta interviews before next Monday.",
            "is_action_item": True,
        }
    ]
    actions = extract_actions(transcript, candidate_speakers=["Sarah Kim", "Marcus Lee", "Jordan Davis"])

    assert len(actions) == 2
    assert actions[0]["owner"] == "Marcus Lee"
    assert actions[0]["deadline"].lower() == "friday"
    assert actions[0]["deadline_date"] is not None

    assert actions[1]["owner"] == "Marcus Lee"
    assert "monday" in actions[1]["deadline"].lower()

def test_ml_step12_summary_and_analytics_interface():
    """Test Step 12 interface: hierarchical_summarize (KeyBERT) & compute_full_analytics (RoBERTa)."""
    transcripts = [
        {"speaker": "Sarah Kim", "start": 0.0, "end": 20.0, "text": "Let us review our Q3 product roadmap."},
        {"speaker": "Marcus Lee", "start": 21.0, "end": 50.0, "text": "The API documentation is looking great.", "is_action_item": True},
        {"speaker": "Jordan Davis", "start": 51.0, "end": 80.0, "text": "We scheduled beta interviews with clients."},
    ]

    # Summary
    summary = hierarchical_summarize(transcripts, title="Q3 Sync")
    assert "overview" in summary
    assert "key_takeaways" in summary
    assert "key_points" in summary
    assert len(summary["key_points"]) > 0

    # Analytics
    analytics = compute_full_analytics(transcripts)
    assert "sentiment_score" in analytics
    assert "speaker_sentiments" in analytics
    assert "speaking_time_distribution" in analytics
    assert "Sarah Kim" in analytics["speaking_time_distribution"]
    assert pytest.approx(sum(analytics["speaking_time_distribution"].values()), 0.1) == 100.0

from datetime import datetime
