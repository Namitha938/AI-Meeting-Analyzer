import pytest
import asyncio
import hmac
import hashlib
import json
import httpx
from unittest.mock import patch, AsyncMock, MagicMock
from app.bot_providers.recall_provider import RecallMeetingBotProvider

@pytest.fixture
def provider():
    return RecallMeetingBotProvider(
        api_key="test_recall_api_key_123",
        webhook_secret="test_webhook_secret_xyz",
        base_url="https://us-east-1.recall.ai/api/v1"
    )


def test_recall_join_success(provider):
    async def run():
        mock_resp_data = {
            "id": "bot_rec_999",
            "meeting_url": "https://meet.google.com/abc-defg-hij",
            "bot_name": "Meetora Notetaker (recording)",
            "status_changes": [{"code": "ready"}]
        }

        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.json.return_value = mock_resp_data

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_resp

            result = await provider.join(
                meeting_id=42,
                meeting_url="https://meet.google.com/abc-defg-hij",
                bot_name="Meetora Notetaker (recording)"
            )

            assert result["bot_id"] == "bot_rec_999"
            assert result["status"] == "scheduled"
            mock_post.assert_called_once()
            call_kwargs = mock_post.call_args[1]
            assert call_kwargs["headers"]["Authorization"] == "Token test_recall_api_key_123"
            assert call_kwargs["json"]["meeting_url"] == "https://meet.google.com/abc-defg-hij"

    asyncio.run(run())


def test_recall_join_error_handling(provider):
    async def run():
        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.text = '{"error": "Invalid meeting URL"}'

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_resp

            with pytest.raises(RuntimeError) as exc_info:
                await provider.join(
                    meeting_id=42,
                    meeting_url="https://invalid-url.com",
                    bot_name="Meetora Notetaker"
                )
            assert "Recall join failed: 400" in str(exc_info.value)

    asyncio.run(run())


def test_recall_status_mapping(provider):
    async def run():
        status_expectations = {
            "ready": "scheduled",
            "joining_call": "joining",
            "in_waiting_room": "waiting_for_admission",
            "in_call_recording": "recording",
            "call_ended": "processing",
            "done": "completed",
            "fatal": "failed",
        }

        for recall_code, expected_meetora_status in status_expectations.items():
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {
                "id": "bot_123",
                "status_changes": [{"code": recall_code, "sub_code": "kicked_by_host" if recall_code == "fatal" else None}]
            }

            with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
                mock_get.return_value = mock_resp
                status_res = await provider.get_status("bot_123")
                assert status_res["status"] == expected_meetora_status
                if recall_code == "fatal":
                    assert status_res["error"] == "kicked_by_host"

    asyncio.run(run())


def test_recall_status_error_retry_resilience(provider):
    async def run():
        # Simulate API error 502 Bad Gateway
        mock_resp = MagicMock()
        mock_resp.status_code = 502

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_resp
            status_res = await provider.get_status("bot_123")
            assert status_res["status"] == "failed"
            assert "API error 502" in status_res["error"]

    asyncio.run(run())


def test_recall_leave_and_delete_media(provider):
    async def run():
        mock_resp = MagicMock()
        mock_resp.status_code = 200

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_resp
            left = await provider.leave("bot_123")
            assert left is True

        with patch("httpx.AsyncClient.delete", new_callable=AsyncMock) as mock_delete:
            mock_delete.return_value = mock_resp
            deleted = await provider.delete_bot_media("bot_123")
            assert deleted is True

    asyncio.run(run())


def test_recall_webhook_signature_verification(provider):
    body = b'{"event": "bot.status_change", "data": {"id": "bot_123", "status": {"code": "in_call_recording"}}}'
    secret = "test_webhook_secret_xyz"
    valid_sig = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()

    # 1. Valid signature
    assert provider.verify_webhook({"webhook-signature": valid_sig}, body) is True
    assert provider.verify_webhook({"x-recall-signature": valid_sig}, body) is True

    # 2. Tampered body
    tampered_body = b'{"event": "bot.status_change", "data": {"id": "bot_tampered"}}'
    assert provider.verify_webhook({"webhook-signature": valid_sig}, tampered_body) is False

    # 3. Invalid signature
    assert provider.verify_webhook({"webhook-signature": "invalid_hex_string"}, body) is False

    # 4. Missing signature
    assert provider.verify_webhook({}, body) is False

    # 5. Missing secret in provider
    no_secret_provider = RecallMeetingBotProvider(api_key="key", webhook_secret=None)
    assert no_secret_provider.verify_webhook({"webhook-signature": valid_sig}, body) is False


def test_recall_parse_webhook_event(provider):
    payload = {
        "event": "bot.complete",
        "data": {
            "id": "bot_test_456",
            "status": {"code": "done"},
            "recordings": [
                {
                    "media_shortcuts": {
                        "video_url": "https://storage.recall.ai/recordings/bot_test_456.mp4"
                    }
                }
            ],
            "transcript": [
                {"speaker": "Alice", "words": [{"text": "Hello"}]}
            ]
        }
    }

    parsed = provider.parse_webhook_event(payload)
    assert parsed["event"] == "bot.complete"
    assert parsed["bot_id"] == "bot_test_456"
    assert parsed["status"] == "completed"
    assert parsed["media_url"] == "https://storage.recall.ai/recordings/bot_test_456.mp4"
    assert parsed["diarized_transcript"] is not None
