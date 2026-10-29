from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal
from app.models import User

client = TestClient(app)

# Ensure jordan is admin for admin endpoints test
db = SessionLocal()
jordan = db.query(User).filter(User.email == 'jordan@meetora.ai').first()
if jordan:
    jordan.role = 'admin'
    db.commit()
db.close()

# 1. Login as admin user
login_res = client.post('/auth/login', json={'email': 'jordan@meetora.ai', 'password': 'password123'})
token = login_res.json()['access_token']
headers = {'Authorization': f'Bearer {token}'}

# Get a meeting id
m_list = client.get('/meetings', headers=headers).json()
assert len(m_list) > 0
m_id = m_list[0]['id']

# Feature 1: Search (Full-text keyword & semantic vector search)
kw_search = client.get('/search?q=product', headers=headers)
assert kw_search.status_code == 200
print(f"1. Search (keyword 'product'): Found {kw_search.json()['total_results']} matching items.")

sem_search = client.get('/search?q=launch+timeline&semantic=true', headers=headers)
assert sem_search.status_code == 200
print(f"2. Semantic Vector Search ('launch timeline'): Found {sem_search.json()['total_results']} items.")

# Feature 2: Export to PDF
pdf_res = client.get(f'/export/{m_id}/pdf', headers=headers)
assert pdf_res.status_code == 200
assert pdf_res.headers['content-type'] == 'application/pdf'
assert len(pdf_res.content) > 100
print(f"3. PDF Export: HTTP 200 OK ({len(pdf_res.content)} bytes generated).")

# Feature 3: Export to DOCX
docx_res = client.get(f'/export/{m_id}/docx', headers=headers)
assert docx_res.status_code == 200
assert 'wordprocessingml' in docx_res.headers['content-type']
assert len(docx_res.content) > 100
print(f"4. Word DOCX Export: HTTP 200 OK ({len(docx_res.content)} bytes generated).")

# Feature 4: Follow-up Email Draft
email_res = client.get(f'/export/{m_id}/email-draft', headers=headers)
assert email_res.status_code == 200
email_draft = email_res.json()
print(f"5. Follow-up Email Draft: Subject='{email_draft['subject']}' | Body length={len(email_draft['body'])} chars.")
assert "Follow-up & Action Items:" in email_draft['subject']

# Feature 5: Google Calendar Sync & Scheduled Reminders
action_items = client.get('/action-items', headers=headers).json()
if len(action_items) > 0:
    first_item = action_items[0]['id']
    sync_res = client.post(f'/calendar/sync-action-item/{first_item}', headers=headers)
    assert sync_res.status_code == 200
    print(f"6. Calendar Sync for Action Item {first_item}: {sync_res.json()['status']} | URL generated.")

events_res = client.get('/calendar/events', headers=headers)
assert events_res.status_code == 200
print(f"7. Calendar Upcoming Events: {events_res.json()['total_events']} events scheduled.")

reminders_res = client.post('/calendar/trigger-reminders', headers=headers)
assert reminders_res.status_code == 200
rem_data = reminders_res.json()
print(f"8. Celery Beat Email Reminders: {rem_data['status']} | Dispatched count: {rem_data.get('total_reminders_dispatched', 0)}.")

# Feature 6: Admin Endpoints
stats_res = client.get('/admin/stats', headers=headers)
assert stats_res.status_code == 200
stats = stats_res.json()
print(f"9. Admin System Stats: {stats['users']['total']} users, {stats['meetings']['total']} meetings, {stats['nlp_metrics']['total_action_items']} action items.")

eval_res = client.get('/admin/model-evaluation', headers=headers)
assert eval_res.status_code == 200
print(f"10. Admin Model Evaluation: DistilBERT F1 = {eval_res.json()['classifier_metrics']['f1']:.3f}, Whisper WER = {eval_res.json()['stt_metrics']['wer']:.3f}.")

dataset_res = client.get('/admin/training-dataset', headers=headers)
assert dataset_res.status_code == 200
print(f"11. Admin Human Retraining Dataset: {dataset_res.json()['total_corrections']} human edits logged.")

print("\nALL STEP 7 EXTRA FEATURES TESTED AND PASSING!")
