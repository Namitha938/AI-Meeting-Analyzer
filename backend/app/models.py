import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, Float, JSON, UniqueConstraint
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
    voiceprint_enrolled = Column(Boolean, default=False)
    voiceprint_sample_path = Column(String(500), nullable=True)
    voiceprint_metrics = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    meetings = relationship("Meeting", foreign_keys="Meeting.user_id", back_populates="owner", cascade="all, delete-orphan")
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
    description = Column(Text, nullable=True)
    scheduled_at = Column(DateTime, nullable=True)
    effectiveness_score = Column(Integer, nullable=True)
    effectiveness_pillars = Column(JSON, nullable=True)
    source = Column(String(50), default="upload", nullable=False)  # live_room | external_link | upload
    is_live = Column(Boolean, default=False, nullable=False)
    room_name = Column(String(100), nullable=True)
    meeting_code = Column(String(50), unique=True, nullable=True, index=True)
    passcode_hash = Column(String(255), nullable=True)
    live_status = Column(String(50), default="scheduled", nullable=False)  # scheduled | live | recording | processing | completed | failed | cancelled
    host_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    started_at = Column(DateTime, nullable=True)
    ended_at = Column(DateTime, nullable=True)
    record_mode = Column(String(50), default="audio_video", nullable=False)  # audio_only | audio_video
    locked = Column(Boolean, default=False, nullable=False)
    waiting_room_enabled = Column(Boolean, default=False, nullable=False)  # Require host admission

    # Phase 5: External Meeting Link & AI Notetaker Bot fields
    meeting_link = Column(String(500), nullable=True)
    platform = Column(String(50), nullable=True)  # google_meet | zoom | ms_teams | other
    auto_join = Column(Boolean, default=True, nullable=False)
    consent_confirmed = Column(Boolean, default=False, nullable=False)
    consent_confirmed_at = Column(DateTime, nullable=True)
    bot_provider = Column(String(50), default="mock", nullable=False)
    bot_id = Column(String(100), nullable=True, index=True)
    bot_status = Column(String(50), default="not_requested", nullable=False)  # not_requested | scheduled | joining | waiting_for_admission | recording | processing | completed | failed | cancelled | removed
    bot_error = Column(Text, nullable=True)

    owner = relationship("User", foreign_keys=[user_id], back_populates="meetings")
    host = relationship("User", foreign_keys=[host_id])
    transcripts = relationship("Transcript", back_populates="meeting", cascade="all, delete-orphan")
    summary = relationship("Summary", back_populates="meeting", uselist=False, cascade="all, delete-orphan")
    action_items = relationship("ActionItem", back_populates="meeting", cascade="all, delete-orphan")
    decisions = relationship("Decision", back_populates="meeting", cascade="all, delete-orphan")
    comments = relationship("Comment", back_populates="meeting", cascade="all, delete-orphan")
    analytics = relationship("MeetingAnalytics", back_populates="meeting", uselist=False, cascade="all, delete-orphan")
    shares = relationship("MeetingShare", back_populates="meeting", cascade="all, delete-orphan")
    live_participants = relationship("LiveParticipant", back_populates="meeting", cascade="all, delete-orphan")
    chats = relationship("MeetingChat", back_populates="meeting", cascade="all, delete-orphan")
    recordings = relationship("Recording", back_populates="meeting", cascade="all, delete-orphan")
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=True)
    team = relationship("Team", back_populates="meetings")

    @property
    def has_passcode(self) -> bool:
        return bool(self.passcode_hash)

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
    edited_by_user = Column(Boolean, default=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    updated_by = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    meeting = relationship("Meeting", back_populates="summary")

class MeetingShare(Base):
    __tablename__ = "meeting_shares"

    id = Column(Integer, primary_key=True, index=True)
    meeting_id = Column(Integer, ForeignKey("meetings.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    can_edit = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    meeting = relationship("Meeting", back_populates="shares")
    user = relationship("User")

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
    start_time_sec = Column(Float, nullable=True)
    source_segment_id = Column(Integer, nullable=True)
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
    start_time_sec = Column(Float, nullable=True)
    source_segment_id = Column(Integer, nullable=True)
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
    meeting_id = Column(Integer, nullable=True)  # Detached (set to NULL) upon meeting deletion to preserve dataset
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

class WebhookIntegration(Base):
    __tablename__ = "webhook_integrations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    provider = Column(String(50), default="slack")  # slack, teams, notion, custom
    name = Column(String(100), nullable=False)
    webhook_url = Column(String(500), nullable=False)
    is_active = Column(Boolean, default=True)
    events = Column(JSON, default=lambda: ["meeting.completed", "action_item.created"])
    secret_token = Column(String(100), nullable=True)
    last_triggered_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class TrackedKeyword(Base):
    __tablename__ = "tracked_keywords"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    keyword = Column(String(100), nullable=False, index=True)
    category = Column(String(50), default="Risk")  # Risk, Commercial, Security, Product, Decision
    color = Column(String(20), default="orange")
    alert_enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    user_email = Column(String(255), nullable=False)
    action = Column(String(100), nullable=False)  # AUTH_LOGIN, 2FA_ENABLE, MEETING_RECORD, EXPORT_PDF, GDPR_EXPORT, ROLE_CHANGE
    resource = Column(String(100), nullable=True)
    ip_address = Column(String(50), default="127.0.0.1")
    status = Column(String(20), default="SUCCESS")  # SUCCESS, FAILED
    severity = Column(String(20), default="INFO")  # INFO, WARNING, CRITICAL
    details = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class Team(Base):
    __tablename__ = "teams"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(60), nullable=False)
    color = Column(String(50), default="violet")
    description = Column(Text, nullable=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("owner_id", "name", name="uq_team_owner_name"),
    )

    owner = relationship("User", foreign_keys=[owner_id])
    members = relationship("TeamMember", back_populates="team", cascade="all, delete-orphan")
    invites = relationship("TeamInvite", back_populates="team", cascade="all, delete-orphan")
    meetings = relationship("Meeting", back_populates="team")

class TeamMember(Base):
    __tablename__ = "team_members"

    id = Column(Integer, primary_key=True, index=True)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    role = Column(String(20), default="member", nullable=False)  # owner, admin, member, viewer
    joined_at = Column(DateTime, default=datetime.datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("team_id", "user_id", name="uq_team_user"),
    )

    team = relationship("Team", back_populates="members")
    user = relationship("User")

class TeamInvite(Base):
    __tablename__ = "team_invites"

    id = Column(Integer, primary_key=True, index=True)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=False)
    email = Column(String(255), nullable=False)
    role = Column(String(20), default="member", nullable=False)  # admin, member, viewer
    token = Column(String(100), unique=True, nullable=False, index=True)
    invited_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    accepted_at = Column(DateTime, nullable=True)
    revoked_at = Column(DateTime, nullable=True)

    team = relationship("Team", back_populates="invites")
    invited_by = relationship("User", foreign_keys=[invited_by_id])

class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    type = Column(String(50), default="team")
    read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    user = relationship("User")

class LiveParticipant(Base):
    __tablename__ = "live_participants"

    id = Column(Integer, primary_key=True, index=True)
    meeting_id = Column(Integer, ForeignKey("meetings.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    display_name = Column(String(150), nullable=False)
    role = Column(String(20), default="participant", nullable=False)  # host | cohost | participant
    status = Column(String(30), default="admitted", nullable=False)  # waiting | admitted | denied | removed
    is_muted = Column(Boolean, default=False, nullable=False)
    video_disabled = Column(Boolean, default=False, nullable=False)
    joined_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    left_at = Column(DateTime, nullable=True)
    consent_at = Column(DateTime, nullable=True)

    meeting = relationship("Meeting", back_populates="live_participants")
    user = relationship("User")

class MeetingChat(Base):
    __tablename__ = "meeting_chats"

    id = Column(Integer, primary_key=True, index=True)
    meeting_id = Column(Integer, ForeignKey("meetings.id"), nullable=False, index=True)
    sender_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    sender_name = Column(String(100), nullable=False)
    message = Column(Text, nullable=False)
    is_private = Column(Boolean, default=False, nullable=False)
    recipient_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    meeting = relationship("Meeting", back_populates="chats")
    sender = relationship("User", foreign_keys=[sender_id])
    recipient = relationship("User", foreign_keys=[recipient_id])


class Recording(Base):
    __tablename__ = "recordings"

    id = Column(Integer, primary_key=True, index=True)
    meeting_id = Column(Integer, ForeignKey("meetings.id"), nullable=False, index=True)
    kind = Column(String(50), default="composite_video", nullable=False)  # composite_video | composite_audio | participant_audio
    participant_id = Column(String(100), nullable=True)
    storage_key = Column(String(500), nullable=True)
    duration = Column(Float, default=0.0)
    size_bytes = Column(Integer, default=0)
    status = Column(String(50), default="recording", nullable=False)  # recording | ready | failed
    egress_id = Column(String(100), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    meeting = relationship("Meeting", back_populates="recordings")
