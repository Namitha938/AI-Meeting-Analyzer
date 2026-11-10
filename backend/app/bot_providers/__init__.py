import os
from typing import Optional
from .base import MeetingBotProvider
from .mock_provider import MockMeetingBotProvider
from .recall_provider import RecallMeetingBotProvider
from .validator import validate_meeting_url, ALLOWED_DOMAINS
from app.config import settings

_mock_instance: Optional[MockMeetingBotProvider] = None

def get_bot_provider(provider_name: Optional[str] = None) -> MeetingBotProvider:
    global _mock_instance
    name = (provider_name or settings.BOT_PROVIDER or "mock").lower()

    if name == "recall":
        return RecallMeetingBotProvider()
    elif name == "mock":
        if _mock_instance is None:
            _mock_instance = MockMeetingBotProvider()
        return _mock_instance
    else:
        # Default fallback to mock
        if _mock_instance is None:
            _mock_instance = MockMeetingBotProvider()
        return _mock_instance

__all__ = [
    "MeetingBotProvider",
    "MockMeetingBotProvider",
    "RecallMeetingBotProvider",
    "validate_meeting_url",
    "ALLOWED_DOMAINS",
    "get_bot_provider",
]

