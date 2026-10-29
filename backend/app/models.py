import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, Float, JSON
from sqlalchemy.orm import relationship
from app.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=True)
    role = Column(String(50), default="user", nullable=False)  # "user" or "admin"
    is_active = Column(Boolean, default=True)
    avatar_url = Column(String(500), nullable=True)
    job_title = Column(String(255), nullable=True, default="Product Manager")
    reset_token = Column(String(255), nullable=True)
    reset_token_expiry = Column(DateTime, nullable=True)
    two_factor_enabled = Column(Boolean, default=False)
    two_factor_secret = Column(String(64), nullable=True)
    backup_codes = Column(JSON, default=list)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    meetings = relationship("Meeting", back_populates="owner", cascade="all, delete-orphan")
    comments = relationship("Comment", back_populates="user", cascade="all, delete-orphan")

class Meeting(Base):
    __tablename__ = "meetings"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    audio_path = Column(String(500), nullable=True)
    duration_seconds = Column(Integer, default=0)
    file_size_bytes = Column(Integer, default=0)
    status = Column(String(50), default="uploading", nullable=False)  # uploading -> transcribing -> analyzing -> completed / failed
    participants = Column(JSON, default=list)  # ["Sarah Kim", "Marcus Lee"]
    tags = Column(JSON, default=list)  # ["Product", "Q3", "Mobile"]
    color = Column(String(50), default="violet")
    model_version = Column(String(50), default="meetora-pipeline-v2.4")
    primary_language = Column(String(20), default="en")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    owner = relationship("User", back_populates="meetings")
    transcripts = relationship("Transcript", back_populates="meeting", cascade="all, delete-orphan")
    summary = relationship("Summary", back_populates="meeting", uselist=False, cascade="all, delete-orphan")
    action_items = relationship("ActionItem", back_populates="meeting", cascade="all, delete-orphan")
    decisions = relationship("Decision", back_populates="meeting", cascade="all, delete-orphan")
    comments = relationship("Comment", back_populates="meeting", cascade="all, delete-orphan")
    analytics = relationship("MeetingAnalytics", back_populates="meeting", uselist=False, cascade="all, delete-orphan")

class Transcript(Base):
    __tablename__ = "transcripts"

    id = Column(Integer, primary_key=True, index=True)
    meeting_id = Column(Integer, ForeignKey("meetings.id"), nullable=False)
    speaker = Column(String(100), nullable=False)
    start_time = Column(Float, default=0.0)
    end_time = Column(Float, default=0.0)
    text = Column(Text, nullable=False)
    is_action_item = Column(Boolean, default=False)
    confidence = Column(Float, default=0.95)
    model_version = Column(String(50), default="whisper-v3")
    language = Column(String(20), default="en")
    translated_text = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    meeting = relationship("Meeting", back_populates="transcripts")

class Summary(Base):
    __tablename__ = "summaries"

    id = Column(Integer, primary_key=True, index=True)
    meeting_id = Column(Integer, ForeignKey("meetings.id"), unique=True, nullable=False)
    overview = Column(Text, nullable=False)
    key_takeaways = Column(JSON, default=list)  # ["point 1", "point 2"]
    next_steps = Column(Text, nullable=True)
    model_version = Column(String(50), default="bart-summarizer-v1.8")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    meeting = relationship("Meeting", back_populates="summary")

class ActionItem(Base):
    __tablename__ = "action_items"

    id = Column(Integer, primary_key=True, index=True)
    meeting_id = Column(Integer, ForeignKey("meetings.id"), nullable=False)
    title = Column(String(300), nullable=False)
    assignee = Column(String(100), nullable=True)
    deadline = Column(String(100), nullable=True)
    status = Column(String(50), default="pending", nullable=False)  # pending, in_progress, completed
    priority = Column(String(50), default="medium")  # low, medium, high
    confidence_score = Column(Float, default=0.92)
    needs_review = Column(Boolean, default=False)
    model_version = Column(String(50), default="distilbert-v2.4")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    meeting = relationship("Meeting", back_populates="action_items")

class Decision(Base):
    __tablename__ = "decisions"

    id = Column(Integer, primary_key=True, index=True)
    meeting_id = Column(Integer, ForeignKey("meetings.id"), nullable=False)
    decision_text = Column(Text, nullable=False)
    category = Column(String(100), default="General")
    rationale = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    meeting = relationship("Meeting", back_populates="decisions")

class Comment(Base):
    __tablename__ = "comments"

    id = Column(Integer, primary_key=True, index=True)
    meeting_id = Column(Integer, ForeignKey("meetings.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    text = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    meeting = relationship("Meeting", back_populates="comments")
    user = relationship("User", back_populates="comments")

class MeetingAnalytics(Base):
    __tablename__ = "meeting_analytics"

    id = Column(Integer, primary_key=True, index=True)
    meeting_id = Column(Integer, ForeignKey("meetings.id"), unique=True, nullable=False)
    sentiment_score = Column(Float, default=0.75)  # 0 to 1
    talk_to_listen_ratio = Column(Float, default=1.1)
    total_topics = Column(Integer, default=3)
    speaking_time_distribution = Column(JSON, default=dict)  # {"Sarah Kim": 45, "Marcus Lee": 35, ...}
    topic_chapters = Column(JSON, default=list)
    effectiveness_score = Column(Integer, default=85)  # 0 to 100
    effectiveness_breakdown = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    meeting = relationship("Meeting", back_populates="analytics")

class HumanCorrection(Base):
    __tablename__ = "human_corrections"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action_item_id = Column(Integer, nullable=True)
    original_text = Column(Text, nullable=False)
    corrected_text = Column(Text, nullable=False)
    original_assignee = Column(String(100), nullable=True)
    corrected_assignee = Column(String(100), nullable=True)
    original_deadline = Column(String(100), nullable=True)
    corrected_deadline = Column(String(100), nullable=True)
    correction_type = Column(String(50), default="edit")  # edit, verified, rejected, added
    model_version = Column(String(50), default="distilbert-v2.4")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class ModelRegistry(Base):
    __tablename__ = "model_registry"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    version = Column(String(50), nullable=False)
    task_type = Column(String(50), nullable=False)  # classifier, summarizer, stt, rag
    is_active = Column(Boolean, default=True)
    description = Column(String(255), nullable=True)
    metrics = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
