import uuid
import hmac
import hashlib
from typing import Dict, Any, Optional
from .base import MeetingBotProvider

class MockMeetingBotProvider(MeetingBotProvider):
    """
    In-memory mock bot provider for unit testing, CI, and offline preview mode.
    """

    MOCK_SECRET = "meetora-mock-bot-secret"

    def __init__(self):
        # In-memory storage for simulated bots: bot_id -> dict
        self._bots: Dict[str, Dict[str, Any]] = {}

    async def join(self, meeting_id: int, meeting_url: str, bot_name: str) -> Dict[str, Any]:
        bot_id = f"mock-bot-{uuid.uuid4().hex[:8]}"
        self._bots[bot_id] = {
            "bot_id": bot_id,
            "meeting_id": meeting_id,
            "meeting_url": meeting_url,
            "bot_name": bot_name,
            "status": "joining",
            "error": None,
            "media_url": f"https://mock-storage.meetora.internal/recordings/{bot_id}.mp4"
        }
        return {
            "bot_id": bot_id,
            "status": "joining",
            "raw": self._bots[bot_id]
        }

    async def leave(self, bot_id: str) -> bool:
        if bot_id in self._bots:
            self._bots[bot_id]["status"] = "removed"
            return True
        return False

    async def get_status(self, bot_id: str) -> Dict[str, Any]:
        if bot_id not in self._bots:
            return {"status": "not_requested", "error": "Bot not found", "raw": {}}
        bot = self._bots[bot_id]
        return {
            "status": bot["status"],
            "error": bot["error"],
            "raw": bot
        }

    def verify_webhook(self, headers: Dict[str, str], body: bytes) -> bool:
        # Check standard mock signature header or query
        sig = headers.get("x-mock-signature") or headers.get("X-Mock-Signature")
        if sig == "valid-mock-signature":
            return True
        
        # Or calculate HMAC-SHA256 signature with MOCK_SECRET
        if sig:
            expected = hmac.new(self.MOCK_SECRET.encode(), body, hashlib.sha256).hexdigest()
            return hmac.compare_digest(sig, expected)
            
        token = headers.get("x-mock-token") or headers.get("X-Mock-Token")
        if token == self.MOCK_SECRET:
            return True

        return False

    def parse_webhook_event(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        # Standard format payload
        event = payload.get("event", "status_change")
        bot_id = payload.get("bot_id", "")
        status = payload.get("status", "unknown")
        media_url = payload.get("media_url")
        error = payload.get("error")
        diarized_transcript = payload.get("diarized_transcript")

        # Update internal mock state if bot exists
        if bot_id in self._bots:
            self._bots[bot_id]["status"] = status
            if error:
                self._bots[bot_id]["error"] = error

        return {
            "event": event,
            "bot_id": bot_id,
            "status": status,
            "media_url": media_url,
            "error": error,
            "diarized_transcript": diarized_transcript
        }

    async def delete_bot_media(self, bot_id: str) -> bool:
        if bot_id in self._bots:
            self._bots[bot_id]["media_deleted"] = True
            return True
        return False

    # Helper method for tests
    def set_mock_status(self, bot_id: str, status: str, error: Optional[str] = None):
        if bot_id in self._bots:
            self._bots[bot_id]["status"] = status
            self._bots[bot_id]["error"] = error

