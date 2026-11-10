from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

class MeetingBotProvider(ABC):
    """
    Abstract interface for AI Meeting Bot Providers (Recall.ai, Vexa, Mock).
    """

    @abstractmethod
    async def join(self, meeting_id: int, meeting_url: str, bot_name: str) -> Dict[str, Any]:
        """
        Requests the AI bot to join the target external meeting link.
        Returns: { "bot_id": str, "status": str, "raw": dict }
        """
        pass

    @abstractmethod
    async def leave(self, bot_id: str) -> bool:
        """
        Commands the bot to leave the external meeting immediately.
        """
        pass

    @abstractmethod
    async def get_status(self, bot_id: str) -> Dict[str, Any]:
        """
        Retrieves current bot status from the provider.
        Returns: { "status": str, "error": Optional[str], "raw": dict }
        """
        pass

    @abstractmethod
    def verify_webhook(self, headers: Dict[str, str], body: bytes) -> bool:
        """
        Verifies cryptographic signature / secret of incoming webhook request.
        """
        pass

    @abstractmethod
    def parse_webhook_event(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parses provider-specific payload into a standardized event format:
        {
            "event": str, # e.g. "status_change", "recording_done", "error"
            "bot_id": str,
            "status": str, # e.g. "joining", "waiting_for_admission", "recording", "completed", "failed"
            "media_url": Optional[str],
            "error": Optional[str],
            "diarized_transcript": Optional[list]
        }
        """
        pass

    @abstractmethod
    async def delete_bot_media(self, bot_id: str) -> bool:
        """
        Deletes provider-side recorded media and artifacts after downloading.
        """
        pass

