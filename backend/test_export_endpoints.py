from app.database import SessionLocal
from app.models import User, Meeting
from app.routers.export import export_meeting_pdf, export_meeting_docx, export_meeting_markdown, generate_follow_up_email

db = SessionLocal()
user = db.query(User).first()
meeting = db.query(Meeting).first()

print(f"Testing direct export functions for Meeting ID {meeting.id}: '{meeting.title}'...")

# 1. Test PDF Export
pdf_resp = export_meeting_pdf(meeting_id=meeting.id, current_user=user, db=db)
assert pdf_resp.status_code == 200
assert pdf_resp.body.startswith(b"%PDF-1.4"), "Invalid PDF binary"
assert b"%%EOF" in pdf_resp.body
print(f" [PASS] PDF Export: {len(pdf_resp.body)} bytes, Media: {pdf_resp.media_type}")

# 2. Test DOCX Export
docx_resp = export_meeting_docx(meeting_id=meeting.id, current_user=user, db=db)
assert docx_resp.status_code == 200
assert docx_resp.body.startswith(b"PK\x03\x04"), "Invalid DOCX zip header"
print(f" [PASS] DOCX Export: {len(docx_resp.body)} bytes, Media: {docx_resp.media_type}")

# 3. Test Markdown Export
md_resp = export_meeting_markdown(meeting_id=meeting.id, current_user=user, db=db)
assert md_resp.status_code == 200
print(f" [PASS] Markdown Export: {len(md_resp.body)} bytes")

# 4. Test Email Draft
email_resp = generate_follow_up_email(meeting_id=meeting.id, current_user=user, db=db)
assert "subject" in email_resp
assert "body" in email_resp
print(f" [PASS] Email Draft: Subject='{email_resp['subject']}'")

print("\n>>> ALL EXPORT ENDPOINTS (PDF, DOCX, MARKDOWN, EMAIL) 100% OPERATIONAL!")
