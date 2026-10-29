from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field

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
    created_at: datetime

    class Config:
        from_attributes = True

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
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

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
