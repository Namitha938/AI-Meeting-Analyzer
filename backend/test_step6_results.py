from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal
from app.models import Decision

client = TestClient(app)

# 1. Login
login_res = client.post('/auth/login', json={'email': 'jordan@meetora.ai', 'password': 'password123'})
token = login_res.json()['access_token']
headers = {'Authorization': f'Bearer {token}'}

# 2. Get user meetings to find an analyzed meeting
meetings_res = client.get('/meetings', headers=headers)
assert meetings_res.status_code == 200
meetings = meetings_res.json()
assert len(meetings) > 0, "At least one meeting must exist"
m_id = meetings[0]['id']
print(f"Testing results endpoints on Meeting ID {m_id}: {meetings[0]['title']}")

# Ensure at least one decision exists for this meeting
db = SessionLocal()
existing_dec = db.query(Decision).filter(Decision.meeting_id == m_id).first()
if not existing_dec:
    db.add(Decision(
        meeting_id=m_id,
        decision_text="Adopt React 19 and Tailwind v4 for all future modules",
        category="Architecture",
        rationale="Superior performance and native build tooling support."
    ))
    db.commit()
db.close()

# 3. GET /meetings/{id}/transcript
tr_res = client.get(f'/meetings/{m_id}/transcript', headers=headers)
assert tr_res.status_code == 200
transcripts = tr_res.json()
print(f"1. Transcripts retrieved: {len(transcripts)} utterances.")
assert len(transcripts) > 0
print(f"   Sample: {transcripts[0]['formatted_line']}")

# 4. GET /meetings/{id}/summary
sum_res = client.get(f'/meetings/{m_id}/summary', headers=headers)
assert sum_res.status_code == 200
summary = sum_res.json()
print(f"2. Summary retrieved: {summary['overview'][:60]}...")
assert summary['overview']

# 5. GET /meetings/{id}/action-items
ai_res = client.get(f'/meetings/{m_id}/action-items', headers=headers)
assert ai_res.status_code == 200
action_items = ai_res.json()
print(f"3. Action items retrieved: {len(action_items)} items.")
assert len(action_items) > 0
item_id = action_items[0]['id']

# 6. GET /meetings/{id}/decisions
dec_res = client.get(f'/meetings/{m_id}/decisions', headers=headers)
assert dec_res.status_code == 200
decisions = dec_res.json()
print(f"4. Decisions retrieved: {len(decisions)} decisions.")
assert len(decisions) > 0
print(f"   Decision text: {decisions[0]['decision_text']}")

# 7. GET /meetings/{id}/analytics
an_res = client.get(f'/meetings/{m_id}/analytics', headers=headers)
assert an_res.status_code == 200
analytics = an_res.json()
print(f"5. Analytics retrieved: Sentiment = {analytics['sentiment_score']}, Effectiveness = {analytics.get('effectiveness_score')}")

# 8. PATCH /action-items/{id} (status, assignee, deadline)
patch_payload = {
    "status": "completed",
    "assignee": "Namitha Singu",
    "deadline": "End of Sprint"
}
patch_res = client.patch(f'/action-items/{item_id}', json=patch_payload, headers=headers)
assert patch_res.status_code == 200
updated_item = patch_res.json()
print(f"6. PATCH /action-items/{item_id}:")
print(f"   Assignee: {updated_item['assignee']} | Deadline: {updated_item['deadline']} | Status: {updated_item['status']}")
assert updated_item['assignee'] == "Namitha Singu"
assert updated_item['status'] == "completed"

# 9. POST /meetings/{id}/comments and GET /meetings/{id}/comments
comment_res = client.post(f'/meetings/{m_id}/comments', json={"text": "Great sync! All decisions are locked in."}, headers=headers)
assert comment_res.status_code == 200
comments_list = client.get(f'/meetings/{m_id}/comments', headers=headers).json()
print(f"7. Comments tested: {len(comments_list)} total comments.")
assert any(c['text'] == "Great sync! All decisions are locked in." for c in comments_list)

# 10. POST /meetings/{id}/share
share_res = client.post(f'/meetings/{m_id}/share', headers=headers)
assert share_res.status_code == 200
share_data = share_res.json()
print(f"8. Share endpoint tested: {share_data['share_url']}")
assert share_data['share_token']

print("\nALL STEP 6 RESULT SERVING & TASK ENDPOINTS PASSED SUCCESSFULLY!")
