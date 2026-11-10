from typing import List, Optional, Dict, Any, Set
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field, field_validator

VALID_MEETING_TAGS: Set[str] = {
    "Product",
    "Research",
    "Planning",
    "Design",
    "General",
    "AI Analyzed",
    "Live Recording",
}

# User & Auth
class UserRegister(BaseModel):
    email: str
    password: str = Field(..., min_length=6)
    full_name: Optional[str] = None
    role: Optional[str] = "user"

class UserLogin(BaseModel):
    email: str
    password: str
    totp_code: Optional[str] = None

class GoogleAuthRequest(BaseModel):
    email: str
    full_name: Optional[str] = None
    google_id: Optional[str] = None
    avatar: Optional[str] = None

class UserResponse(BaseModel):
    id: int
    email: str
    full_name: Optional[str] = None
    role: str
    is_active: bool
    avatar_url: Optional[str] = None
    job_title: Optional[str] = None
    two_factor_enabled: Optional[bool] = False
    created_at: datetime

    class Config:
        from_attributes = True

class TwoFactorSetupResponse(BaseModel):
    secret: str
    otpauth_url: str
    qr_code_url: str
    backup_codes: List[str]

class TwoFactorVerifyRequest(BaseModel):
    code: str
    secret: Optional[str] = None

class TwoFactorVerifyResponse(BaseModel):
    status: str
    message: str
    backup_codes: Optional[List[str]] = None

class UserProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    job_title: Optional[str] = None
    avatar_url: Optional[str] = None

class ForgotPasswordRequest(BaseModel):
    email: str

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(..., min_length=6)

class Token(BaseModel):
    access_token: Optional[str] = ""
    token_type: str = "bearer"
    user: Optional[UserResponse] = None
    requires_2fa: Optional[bool] = False
    expires_in: Optional[int] = None

class TokenData(BaseModel):
    email: Optional[str] = None
    role: Optional[str] = None

# Transcript
class TranscriptItem(BaseModel):
    id: Optional[int] = None
    speaker: str
    start_time: float
    end_time: float
    text: str
    timestamp_str: Optional[str] = None
    formatted_line: Optional[str] = None
    is_action_item: bool = False
    confidence: float = 0.95
    model_version: Optional[str] = "whisper-v3"
    language: Optional[str] = "en"
    translated_text: Optional[str] = None

    class Config:
        from_attributes = True

class RenameSpeakerRequest(BaseModel):
    old_name: str
    new_name: str

# Action Items
class ActionItemCreate(BaseModel):
    title: str
    assignee: Optional[str] = None
    deadline: Optional[str] = None
    priority: Optional[str] = "medium"
    status: Optional[str] = "pending"

class ActionItemUpdate(BaseModel):
    title: Optional[str] = None
    assignee: Optional[str] = None
    deadline: Optional[str] = None
    status: Optional[str] = None  # pending, in_progress, completed
    priority: Optional[str] = None
    confidence_score: Optional[float] = None
    needs_review: Optional[bool] = None

class ActionItemResponse(BaseModel):
    id: int
    meeting_id: int
    title: str
    assignee: Optional[str] = None
    deadline: Optional[str] = None
    status: str
    priority: str
    confidence_score: Optional[float] = 0.92
    needs_review: Optional[bool] = False
    start_time_sec: Optional[float] = None
    source_segment_id: Optional[int] = None
    model_version: Optional[str] = "distilbert-v2.4"
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

# Decisions
class DecisionCreate(BaseModel):
    decision_text: str
    category: Optional[str] = "General"
    rationale: Optional[str] = None
    start_time_sec: Optional[float] = None
    source_segment_id: Optional[int] = None

class DecisionResponse(BaseModel):
    id: int
    meeting_id: int
    decision_text: str
    category: str
    rationale: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

# Summary
class SummaryResponse(BaseModel):
    id: int
    meeting_id: int
    overview: str
    key_takeaways: List[str] = []
    next_steps: Optional[str] = None
    edited_by_user: Optional[bool] = False
    updated_at: Optional[datetime] = None
    updated_by: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

class SummaryUpdateRequest(BaseModel):
    overview: Optional[str] = None
    key_takeaways: Optional[List[str]] = None
    next_steps: Optional[str] = None
    updated_at: Optional[datetime] = None

# Analytics
class AnalyticsResponse(BaseModel):
    meeting_id: int
    sentiment_score: float
    talk_to_listen_ratio: float
    total_topics: int
    speaking_time_distribution: Dict[str, Any] = {}
    topic_chapters: Optional[List[Dict[str, Any]]] = []
    effectiveness_score: Optional[int] = 85
    effectiveness_breakdown: Optional[Dict[str, Any]] = {}
    created_at: datetime

    class Config:
        from_attributes = True

# Comments
class CommentCreate(BaseModel):
    text: str

class CommentResponse(BaseModel):
    id: int
    meeting_id: int
    user_id: int
    user_name: Optional[str] = None
    text: str
    created_at: datetime

    class Config:
        from_attributes = True

# Meetings
class MeetingCreate(BaseModel):
    title: str
    participants: Optional[List[str]] = []
    tags: Optional[List[str]] = []
    color: Optional[str] = "violet"
    source: Optional[str] = "upload"  # live_room | external_link | upload
    is_live: Optional[bool] = False
    record_mode: Optional[str] = "audio_video"
    passcode: Optional[str] = None
    scheduled_at: Optional[datetime] = None
    description: Optional[str] = None
    team_id: Optional[int] = None
    meeting_link: Optional[str] = None
    platform: Optional[str] = None
    auto_join: Optional[bool] = True
    consent_confirmed: Optional[bool] = False
    bot_provider: Optional[str] = "mock"

class MeetingResponse(BaseModel):
    id: int
    title: str
    user_id: int
    duration_seconds: int
    status: str
    participants: List[str] = []
    tags: List[str] = []
    color: str
    audio_path: Optional[str] = None
    model_version: Optional[str] = "meetora-pipeline-v2.4"
    primary_language: Optional[str] = "en"
    description: Optional[str] = None
    scheduled_at: Optional[datetime] = None
    effectiveness_score: Optional[int] = None
    effectiveness_pillars: Optional[Dict[str, Any]] = None
    source: Optional[str] = "upload"
    is_live: Optional[bool] = False
    room_name: Optional[str] = None
    meeting_code: Optional[str] = None
    has_passcode: Optional[bool] = False
    locked: Optional[bool] = False
    waiting_room_enabled: Optional[bool] = False
    live_status: Optional[str] = "scheduled"
    host_id: Optional[int] = None
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    record_mode: Optional[str] = "audio_video"
    meeting_link: Optional[str] = None
    platform: Optional[str] = None
    auto_join: Optional[bool] = True
    consent_confirmed: Optional[bool] = False
    consent_confirmed_at: Optional[datetime] = None
    bot_provider: Optional[str] = "mock"
    bot_id: Optional[str] = None
    bot_status: Optional[str] = "not_requested"
    bot_error: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class LiveParticipantResponse(BaseModel):
    id: int
    meeting_id: int
    user_id: Optional[int] = None
    display_name: str
    role: Optional[str] = "participant"
    status: Optional[str] = "admitted"
    is_muted: Optional[bool] = False
    video_disabled: Optional[bool] = False
    joined_at: datetime
    left_at: Optional[datetime] = None
    consent_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class LiveJoinRequest(BaseModel):
    display_name: str = Field(..., min_length=1, max_length=100)
    consent: bool = Field(..., description="Must consent to recording and analysis")
    passcode: Optional[str] = None

class LiveJoinResponse(BaseModel):
    token: str
    livekit_url: str
    room_name: str
    participant_id: str
    display_name: str
    is_host: bool
    status: Optional[str] = "admitted"
    waiting_message: Optional[str] = None

class ModerationActionRequest(BaseModel):
    participant_id: Optional[int] = None

class ModerationActionResponse(BaseModel):
    success: bool
    action: str
    message: str
    target_participant_id: Optional[int] = None

class JoinByCodeRequest(BaseModel):
    meeting_code: str = Field(..., min_length=3, max_length=50)
    passcode: Optional[str] = None

class JoinByCodeResponse(BaseModel):
    meeting_id: int
    title: str
    meeting_code: str
    requires_passcode: bool
    is_live: bool
    live_status: str

class LiveChatMessageCreate(BaseModel):
    message: str = Field(..., min_length=1)
    is_private: Optional[bool] = False
    recipient_id: Optional[int] = None

class LiveChatMessageResponse(BaseModel):
    id: int
    meeting_id: int
    sender_id: Optional[int] = None
    sender_name: str
    message: str
    is_private: bool = False
    recipient_id: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True

class LiveStatusResponse(BaseModel):
    meeting_id: int
    is_live: bool
    live_status: str
    room_name: Optional[str] = None
    meeting_code: Optional[str] = None
    has_passcode: bool = False
    locked: bool = False
    record_mode: str
    host_id: Optional[int] = None
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    active_participants_count: int = 0
    can_join: bool = False
    is_host: bool = False



class RecordingResponse(BaseModel):
    id: int
    meeting_id: int
    kind: str
    participant_id: Optional[str] = None
    storage_key: Optional[str] = None
    duration: Optional[float] = 0.0
    size_bytes: Optional[int] = 0
    status: str
    egress_id: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

class RecordingStartResponse(BaseModel):
    status: str
    recording: bool
    egress_ids: List[str] = []
    message: str

class RecordingStopResponse(BaseModel):
    status: str
    recording: bool
    message: str

class PlaybackResponse(BaseModel):
    playback_url: str
    expires_at: datetime
    kind: str
    duration: Optional[float] = None

class ChunkUploadResponse(BaseModel):
    status: str
    chunk_index: int
    total_chunks: int
    recording_id: Optional[int] = None
    meeting_id: int

class LiveEndResponse(BaseModel):
    status: str
    message: str
    ended_at: datetime

class MeetingUpdateRequest(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    tag: Optional[str] = None
    tags: Optional[List[str]] = None
    scheduled_at: Optional[datetime] = None
    description: Optional[str] = None
    updated_at: Optional[datetime] = None

    @field_validator("tag")
    @classmethod
    def validate_tag(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            clean = v.strip()
            if not clean:
                raise ValueError("Tag cannot be blank")
            normalized = {t.lower(): t for t in VALID_MEETING_TAGS}
            if clean.lower() not in normalized:
                valid_list = ", ".join(sorted(VALID_MEETING_TAGS))
                raise ValueError(f"Tag must be one of: {valid_list}")
            return normalized[clean.lower()]
        return v

class TranscriptLineUpdateRequest(BaseModel):
    text: Optional[str] = None
    speaker: Optional[str] = None

class MeetingStatusResponse(BaseModel):
    id: int
    status: str
    progress: int
    stage: str
    message: str

class MeetingDetailResponse(MeetingResponse):
    summary: Optional[SummaryResponse] = None
    action_items: List[ActionItemResponse] = []
    decisions: List[DecisionResponse] = []
    transcripts: List[TranscriptItem] = []
    analytics: Optional[AnalyticsResponse] = None
    comments: List[CommentResponse] = []
    chapters: Optional[List[Dict[str, Any]]] = []

class BulkDeleteRequest(BaseModel):
    meeting_ids: List[int]

class BulkDeleteFailure(BaseModel):
    id: int
    reason: str

class BulkDeleteResponse(BaseModel):
    success: bool
    deleted: List[int] = []
    failed: List[BulkDeleteFailure] = []

class SearchResultItem(BaseModel):
    meeting_id: int
    meeting_title: str
    match_type: str  # "transcript", "summary", "action_item", "decision"
    snippet: str
    timestamp: Optional[float] = None

class SearchResponse(BaseModel):
    query: str
    total_results: int
    results: List[SearchResultItem]

class EmailDraftResponse(BaseModel):
    meeting_id: int
    subject: str
    recipients: List[str]
    body: str

class EmailSendRequest(BaseModel):
    recipients: List[str]
    subject: str
    body: str

class EmailSendResponse(BaseModel):
    success: bool
    meeting_id: int
    sent_to: List[str]
    message: str


# ==========================================
# RAG Chat & Semantic Question Answering
# ==========================================
class MeetingChatRequest(BaseModel):
    query: str

class CitationItem(BaseModel):
    speaker: str
    timestamp_str: str
    start_time: float
    text: str
    relevance_score: float

class MeetingChatResponse(BaseModel):
    answer: str
    query: str
    meeting_id: Optional[int] = None
    meeting_title: Optional[str] = None
    citations: List[CitationItem] = []
    confidence: float = 0.94

# ==========================================
# Model Evaluation & Model Registry
# ==========================================
class ModelEvaluationResponse(BaseModel):
    timestamp: datetime
    dataset_size: int
    classifier_metrics: Dict[str, float]
    stt_metrics: Dict[str, Any]
    summarization_metrics: Dict[str, float]
    confusion_matrix: Dict[str, Any]
    human_corrections_collected: int

class ModelRegistryItem(BaseModel):
    id: int
    name: str
    version: str
    task_type: str
    is_active: bool
    description: Optional[str] = None
    metrics: Dict[str, Any] = {}
    created_at: datetime

    class Config:
        from_attributes = True

class ModelRollbackRequest(BaseModel):
    task_type: str
    target_version: str

# ==========================================
# Multilingual & Translation
# ==========================================
class TranslationRequest(BaseModel):
    target_language: str = "en"

class TranslationResponse(BaseModel):
    meeting_id: int
    target_language: str
    translated_count: int
    transcripts: List[TranscriptItem]

# ==========================================
# Enterprise Integrations & Webhooks
# ==========================================
class WebhookIntegrationCreate(BaseModel):
    provider: str = "slack"
    name: str
    webhook_url: str
    events: List[str] = ["meeting.completed", "action_item.created"]
    secret_token: Optional[str] = None

class WebhookIntegrationResponse(BaseModel):
    id: int
    user_id: int
    provider: str
    name: str
    webhook_url: str
    is_active: bool
    events: List[str]
    last_triggered_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True

class WebhookTestResponse(BaseModel):
    success: bool
    status_code: int
    message: str
    response_payload: Dict[str, Any]

# ==========================================
# Monitored Keywords & Risk Analytics
# ==========================================
class TrackedKeywordCreate(BaseModel):
    keyword: str
    category: str = "Risk"
    color: str = "orange"
    alert_enabled: bool = True

class TrackedKeywordResponse(BaseModel):
    id: int
    keyword: str
    category: str
    color: str
    alert_enabled: bool
    mention_count: int = 0
    created_at: datetime

    class Config:
        from_attributes = True

class KeywordMentionItem(BaseModel):
    keyword: str
    category: str
    meeting_id: int
    meeting_title: str
    speaker: str
    timestamp_str: str
    snippet: str
    sentiment: str = "neutral"

class KeywordAnalysisResponse(BaseModel):
    total_mentions: int
    risk_score: float
    keywords: List[TrackedKeywordResponse]
    recent_mentions: List[KeywordMentionItem]

# ==========================================
# SOC2 & GDPR Audit Logging
# ==========================================
class AuditLogResponse(BaseModel):
    id: int
    user_id: Optional[int]
    user_email: str
    action: str
    resource: Optional[str]
    ip_address: str
    status: str
    severity: str
    details: Dict[str, Any] = {}
    created_at: datetime

    class Config:
        from_attributes = True

class ComplianceExportResponse(BaseModel):
    format: str
    generated_at: datetime
    record_count: int
    data: List[AuditLogResponse]

class GdprPurgeResponse(BaseModel):
    success: bool
    user_email: str
    purged_meetings: int
    purged_transcripts: int
    message: str

# ==========================================
# Voiceprint Biometrics
# ==========================================
class VoiceprintEnrollRequest(BaseModel):
    sample_text: Optional[str] = None
    audio_base64: Optional[str] = None
    audio_duration_seconds: float = 10.0

class VoiceprintResponse(BaseModel):
    user_id: int
    enrolled: bool
    biometric_hash: str
    confidence_threshold: float
    message: str

# ==========================================
# Teams & Members
# ==========================================
VALID_TEAM_ROLES = {"owner", "admin", "member", "viewer"}
VALID_INVITE_ROLES = {"admin", "member", "viewer"}

class TeamCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=60)
    color: Optional[str] = "violet"
    description: Optional[str] = None

class TeamUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=60)
    color: Optional[str] = None
    description: Optional[str] = None

class TeamResponse(BaseModel):
    id: int
    name: str
    color: Optional[str] = "violet"
    description: Optional[str] = None
    owner_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    member_count: int = 1
    my_role: Optional[str] = None

    class Config:
        from_attributes = True

class TeamMemberResponse(BaseModel):
    id: int
    team_id: int
    user_id: int
    role: str
    joined_at: datetime
    user_email: Optional[str] = None
    user_name: Optional[str] = None
    user_avatar: Optional[str] = None

    class Config:
        from_attributes = True

class TeamMemberRoleUpdate(BaseModel):
    role: str

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        clean = v.strip().lower()
        if clean not in VALID_INVITE_ROLES:
            raise ValueError(f"Role must be one of: {', '.join(sorted(VALID_INVITE_ROLES))}")
        return clean

class TeamTransferOwnershipRequest(BaseModel):
    new_owner_user_id: int

class TeamInviteCreate(BaseModel):
    email: str
    role: str = "member"

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        clean = v.strip().lower()
        if "@" not in clean or "." not in clean:
            raise ValueError("Invalid email address")
        return clean

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        clean = v.strip().lower()
        if clean not in VALID_INVITE_ROLES:
            raise ValueError(f"Role must be one of: {', '.join(sorted(VALID_INVITE_ROLES))}")
        return clean

class TeamInviteResponse(BaseModel):
    id: int
    team_id: int
    email: str
    role: str
    invited_by_id: int
    invited_by_name: Optional[str] = None
    created_at: datetime
    expires_at: datetime
    status: str  # pending, accepted, expired, revoked
    invite_link: Optional[str] = None

    class Config:
        from_attributes = True

class NotificationResponse(BaseModel):
    id: int
    user_id: int
    title: str
    message: str
    type: str = "team"
    read: bool = False
    created_at: datetime

    class Config:
        from_attributes = True

class BotJoinRequest(BaseModel):
    consent_confirmed: bool = True

class BotStatusResponse(BaseModel):
    meeting_id: int
    bot_status: str
    bot_id: Optional[str] = None
    bot_error: Optional[str] = None
    platform: Optional[str] = None
    meeting_link: Optional[str] = None
    auto_join: bool = True
    consent_confirmed: bool = False
    elapsed_seconds: Optional[int] = 0


class LiveCaptionInput(BaseModel):
    text: str = Field(..., min_length=1)
    speaker: str = Field(default="Participant")
    timestamp: Optional[float] = 0.0
    is_final: Optional[bool] = True

class DetectedActionItem(BaseModel):
    id: Optional[int] = None
    title: str
    assignee: Optional[str] = None
    deadline: Optional[str] = None
    confidence_score: float = 0.88
    context_quote: str
    status: str = "suggested"
    start_time_sec: Optional[float] = None
    source_segment_id: Optional[int] = None

class LiveCaptionResponse(BaseModel):
    text: str
    speaker: str
    timestamp: float
    detected_action_item: Optional[DetectedActionItem] = None
