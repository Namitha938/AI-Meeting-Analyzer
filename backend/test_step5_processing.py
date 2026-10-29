from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal
from app.models import Meeting, User

client = TestClient(app)

# 1. Login to get token
login_res = client.post('/auth/login', json={'email': 'jordan@meetora.ai', 'password': 'password123'})
token = login_res.json()['access_token']
headers = {'Authorization': f'Bearer {token}'}

db = SessionLocal()
user = db.query(User).filter(User.email == 'jordan@meetora.ai').first()

# 2. Create meeting directly in uploading state
test_m = Meeting(
    title='Async Processing Sync',
    user_id=user.id,
    status='uploading',
    participants=['Jordan Davis', 'Sarah Kim'],
    tags=['Sprint', 'Background']
)
db.add(test_m)
db.commit()
db.refresh(test_m)
m_id = test_m.id
db.close()

# 3. Poll initial status: uploading
st1 = client.get(f'/meetings/{m_id}/status', headers=headers).json()
print(f"Stage 1 (Upload): {st1['status']} ({st1['progress']}%) - {st1['message']}")
assert st1['status'] == 'uploading'

# 4. Advance to transcribing
db = SessionLocal()
m = db.query(Meeting).filter(Meeting.id == m_id).first()
m.status = 'transcribing'
db.commit()
db.close()
st2 = client.get(f'/meetings/{m_id}/status', headers=headers).json()
print(f"Stage 2 (Transcribe): {st2['status']} ({st2['progress']}%) - {st2['message']}")
assert st2['status'] == 'transcribing'

# 5. Advance to analyzing
db = SessionLocal()
m = db.query(Meeting).filter(Meeting.id == m_id).first()
m.status = 'analyzing'
db.commit()
db.close()
st3 = client.get(f'/meetings/{m_id}/status', headers=headers).json()
print(f"Stage 3 (Analyze): {st3['status']} ({st3['progress']}%) - {st3['message']}")
assert st3['status'] == 'analyzing'

# 6. Run process_meeting task to completion
from app.celery_app import process_meeting
process_meeting(m_id)

# 7. Poll final status: completed
st4 = client.get(f'/meetings/{m_id}/status', headers=headers).json()
print(f"Stage 4 (Complete): {st4['status']} ({st4['progress']}%) - {st4['message']}")
assert st4['status'] == 'completed'
assert st4['progress'] == 100

print('ALL STEP 5 BACKGROUND PROCESSING & STATUS POLLING TESTS PASSED!')
