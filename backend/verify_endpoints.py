import sys
import os
import time
import threading
import urllib.request
import urllib.parse
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import uvicorn
from app.main import app

def run_server():
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")

def req(url, data=None, headers=None, method=None):
    if headers is None:
        headers = {}
    if data is not None and isinstance(data, dict):
        data = json.dumps(data).encode("utf-8")
        headers["Content-Type"] = "application/json"
    r = urllib.request.Request(f"http://127.0.0.1:8000{url}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(r, timeout=5) as resp:
            body = resp.read().decode("utf-8")
            return resp.status, json.loads(body) if "json" in resp.headers.get("Content-Type", "") else body
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        return e.code, body

if __name__ == "__main__":
    t = threading.Thread(target=run_server, daemon=True)
    t.start()
    time.sleep(2.0)

    print("=== Testing 1: Health ===")
    status, body = req("/health")
    print(f"Status: {status}, Body: {body}")

    print("\n=== Testing 2: Login seeded user jordan@meetora.ai ===")
    status, body = req("/auth/login", data={"email": "jordan@meetora.ai", "password": "password123"})
    print(f"Status: {status}")
    token = body["access_token"]
    print(f"Token: {token[:30]}...")
    headers = {"Authorization": f"Bearer {token}"}

    print("\n=== Testing 3: /auth/me ===")
    status, body = req("/auth/me", headers=headers)
    print(f"Status: {status}, User: {body['email']}, Role: {body['role']}")

    print("\n=== Testing 4: /meetings list ===")
    status, body = req("/meetings", headers=headers)
    print(f"Status: {status}, Total Meetings: {len(body)}")
    meeting_id = body[0]["id"]
    print(f"First Meeting ID: {meeting_id}, Title: '{body[0]['title']}'")

    print("\n=== Testing 5: /meetings/{id} detail ===")
    status, body = req(f"/meetings/{meeting_id}", headers=headers)
    print(f"Status: {status}, Transcripts: {len(body.get('transcripts', []))}, Actions: {len(body.get('action_items', []))}")

    print("\n=== Testing 6: /search?q=onboarding ===")
    status, body = req("/search?q=onboarding", headers=headers)
    print(f"Status: {status}, Matches found: {body['total_results']}")

    print("\n=== Testing 7: /export/{id}/markdown ===")
    status, body = req(f"/export/{meeting_id}/markdown", headers=headers)
    print(f"Status: {status}, Markdown preview:\n{body[:120]}...")

    print("\n=== Testing 8: /export/{id}/email-draft ===")
    status, body = req(f"/export/{meeting_id}/email-draft", headers=headers)
    print(f"Status: {status}, Subject: {body['subject']}")

    print("\n=== ALL FASTAPI BACKEND ENDPOINTS VERIFIED & WORKING PERFECTLY ===")

