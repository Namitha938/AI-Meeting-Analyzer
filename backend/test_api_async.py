import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import httpx
from httpx import ASGITransport
from app.main import app
from app.database import Base, engine
from app.main import seed_initial_demo_data

async def main():
    Base.metadata.create_all(bind=engine)
    seed_initial_demo_data()

    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        print("--- 1. Testing Health ---")
        res = await client.get("/health")
        assert res.status_code == 200, res.text
        print("Health OK:", res.json())

        print("\n--- 2. Testing Register ---")
        reg_data = {
            "email": "testuser@meetora.ai",
            "password": "Password123!",
            "full_name": "Test User",
            "role": "user"
        }
        res = await client.post("/auth/register", json=reg_data)
        assert res.status_code in [201, 400], res.text
        print("Register Status:", res.status_code)

        print("\n--- 3. Testing Login ---")
        login_data = {
            "email": "testuser@meetora.ai",
            "password": "Password123!"
        }
        res = await client.post("/auth/login", json=login_data)
        assert res.status_code == 200, res.text
        tokens = res.json()
        token = tokens["access_token"]
        print("Login OK. JWT Token generated:", token[:30] + "...")

        headers = {"Authorization": f"Bearer {token}"}

        print("\n--- 4. Testing GET /auth/me ---")
        res = await client.get("/auth/me", headers=headers)
        assert res.status_code == 200, res.text
        print("Current User:", res.json()["email"])

        print("\n--- 5. Testing POST /meetings ---")
        meeting_payload = {
            "title": "Sprint Planning & AI Architecture Sync",
            "participants": "Sarah Kim, Marcus Lee, Test User",
            "tags": "Sprint, AI, Backend",
            "color": "blue"
        }
        res = await client.post("/meetings", data=meeting_payload, headers=headers)
        assert res.status_code == 201, res.text
        created_meeting = res.json()
        meeting_id = created_meeting["id"]
        print(f"Meeting Created: ID={meeting_id}, Title='{created_meeting['title']}'")

        print("\n--- 6. Testing GET /meetings/{id}/status ---")
        res = await client.get(f"/meetings/{meeting_id}/status", headers=headers)
        assert res.status_code == 200, res.text
        print("Status:", res.json())

        print("\n--- 7. Testing GET /meetings/{id} (Detail) ---")
        res = await client.get(f"/meetings/{meeting_id}", headers=headers)
        assert res.status_code == 200, res.text
        detail = res.json()
        print("Transcripts count:", len(detail.get("transcripts", [])))
        print("Action items count:", len(detail.get("action_items", [])))
        print("Summary overview:", detail.get("summary", {}).get("overview"))

        print("\n--- 8. Testing PATCH /action-items/{id} ---")
        if detail.get("action_items"):
            item_id = detail["action_items"][0]["id"]
            res = await client.patch(f"/action-items/{item_id}", json={"status": "completed"}, headers=headers)
            assert res.status_code == 200, res.text
            print(f"Action item {item_id} updated status:", res.json()["status"])

        print("\n--- 9. Testing GET /search ---")
        res = await client.get("/search?q=roadmap", headers=headers)
        assert res.status_code == 200, res.text
        print(f"Search Results for 'roadmap': {res.json()['total_results']} matches")

        print("\n--- 10. Testing GET /export/{id}/markdown ---")
        res = await client.get(f"/export/{meeting_id}/markdown", headers=headers)
        assert res.status_code == 200, res.text
        print("Export Markdown length:", len(res.text), "characters")

        print("\n--- 11. Testing GET /export/{id}/email-draft ---")
        res = await client.get(f"/export/{meeting_id}/email-draft", headers=headers)
        assert res.status_code == 200, res.text
        print("Email Draft Subject:", res.json()["subject"])

        print("\n ALL BACKEND TESTS PASSED SUCCESSFULLY! ")

if __name__ == "__main__":
    asyncio.run(main())

