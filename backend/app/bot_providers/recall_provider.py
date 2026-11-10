import hmac
import hashlib
import logging
import httpx
from typing import Dict, Any, Optional
from .base import MeetingBotProvider
from app.config import settings

logger = logging.getLogger(__name__)

class RecallMeetingBotProvider(MeetingBotProvider):
    """
    Integration for Recall.ai API v1.
    """

    STATUS_MAP = {
        "ready": "scheduled",
        "joining_call": "joining",
        "in_waiting_room": "waiting_for_admission",
        "in_call_not_recording": "joining",
        "in_call_recording": "recording",
        "call_ended": "processing",
        "done": "completed",
        "fatal": "failed",
    }

    def __init__(self, api_key: Optional[str] = None, webhook_secret: Optional[str] = None, base_url: Optional[str] = None):
        self.api_key = api_key or settings.RECALL_API_KEY
        self.webhook_secret = webhook_secret or settings.RECALL_WEBHOOK_SECRET
        self.base_url = (base_url or settings.RECALL_BASE_URL).rstrip("/")

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Token {self.api_key}",
            "Content-Type": "application/json"
        }

    async def join(self, meeting_id: int, meeting_url: str, bot_name: str) -> Dict[str, Any]:
        url = f"{self.base_url}/bot/"
        payload = {
            "meeting_url": meeting_url,
            "bot_name": bot_name,
            "transcription_options": {
                "provider": "meeting_captions"
            },
            "chat": {
                "auto_send": {
                    "in_call_recording": f"Hello! I am {bot_name}. I am recording and transcribing this meeting for Meetora AI analysis."
                }
            },
            "metadata": {
                "meetora_meeting_id": str(meeting_id)
            }
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, headers=self._headers(), json=payload)
            if resp.status_code >= 400:
                logger.error(f"Recall API join error: {resp.status_code} - {resp.text}")
                raise RuntimeError(f"Recall join failed: {resp.status_code} {resp.text}")
            data = resp.json()
            bot_id = data.get("id")
            recall_status = data.get("status_changes", [{}])[-1].get("code", "ready") if data.get("status_changes") else "ready"
            return {
                "bot_id": bot_id,
                "status": self.STATUS_MAP.get(recall_status, "joining"),
                "raw": data
            }

    async def leave(self, bot_id: str) -> bool:
        url = f"{self.base_url}/bot/{bot_id}/leave/"
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, headers=self._headers())
            return resp.status_code < 400

    async def get_status(self, bot_id: str) -> Dict[str, Any]:
        url = f"{self.base_url}/bot/{bot_id}/"
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, headers=self._headers())
            if resp.status_code >= 400:
                return {"status": "failed", "error": f"API error {resp.status_code}", "raw": {}}
            data = resp.json()
            status_changes = data.get("status_changes", [])
            last_code = status_changes[-1].get("code", "unknown") if status_changes else "unknown"
            meetora_status = self.STATUS_MAP.get(last_code, "joining")
            error_msg = None
            if meetora_status == "failed":
                error_msg = status_changes[-1].get("sub_code") or "Bot encountered an error"
            return {
                "status": meetora_status,
                "error": error_msg,
                "raw": data
            }

    def verify_webhook(self, headers: Dict[str, str], body: bytes) -> bool:
        if not self.webhook_secret:
            logger.warning("No RECALL_WEBHOOK_SECRET configured; rejecting webhook.")
            return False

        signature = headers.get("webhook-signature") or headers.get("Webhook-Signature") or headers.get("x-recall-signature")
        if not signature:
            return False

        computed = hmac.new(self.webhook_secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(signature, computed)

    def parse_webhook_event(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        event_type = payload.get("event", "")
        data = payload.get("data", {})
        bot_id = data.get("bot_id") or data.get("id") or ""
        
        status_code = data.get("status", {}).get("code") or data.get("code")
        meetora_status = self.STATUS_MAP.get(status_code, "joining")
        
        media_url = None
        recordings = data.get("recordings", [])
        if recordings:
            media_url = recordings[0].get("media_shortcuts", {}).get("video_url") or recordings[0].get("url")
            
        error = None
        if meetora_status == "failed":
            error = data.get("status", {}).get("sub_code") or "Call failed"

        transcript = data.get("transcript")

        return {
            "event": event_type,
            "bot_id": bot_id,
            "status": meetora_status,
            "media_url": media_url,
            "error": error,
            "diarized_transcript": transcript
        }

    async def delete_bot_media(self, bot_id: str) -> bool:
        url = f"{self.base_url}/bot/{bot_id}/"
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.delete(url, headers=self._headers())
            return resp.status_code < 400

