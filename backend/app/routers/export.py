from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session
from datetime import datetime

from app.database import get_db
from app.models import User, Meeting
from app.schemas import EmailDraftResponse
from app.auth import get_current_user
from app.document_generator import SimpleDocxBuilder, SimplePdfBuilder

router = APIRouter(prefix="/export", tags=["Export & Sharing"])

@router.get("/{meeting_id}/markdown")
def export_meeting_markdown(
    meeting_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    date_str = meeting.created_at.strftime('%Y-%m-%d %H:%M UTC') if meeting.created_at else "N/A"
    lines = [
        f"# {meeting.title}",
        f"**Date:** {date_str}",
        f"**Participants:** {', '.join(meeting.participants or [])}",
        "",
        "## AI Executive Summary",
        meeting.summary.overview if meeting.summary else "No summary available.",
        "",
        "### Key Takeaways",
    ]
    if meeting.summary and meeting.summary.key_takeaways:
        for pt in meeting.summary.key_takeaways:
            lines.append(f"- {pt}")
    else:
        lines.append("- No takeaways recorded.")

    lines.extend([
        "",
        "## Action Items",
    ])
    if meeting.action_items:
        for ai in meeting.action_items:
            check = "x" if ai.status == "completed" else " "
            lines.append(f"- [{check}] **{ai.title}** — Owner: {ai.assignee or 'Unassigned'} | Due: {ai.deadline or 'TBD'} [{ai.priority.upper()}]")
    else:
        lines.append("No action items.")

    lines.extend([
        "",
        "## Key Decisions",
    ])
    if meeting.decisions:
        for dec in meeting.decisions:
            lines.append(f"- **{dec.decision_text}** ({dec.category}): {dec.rationale or ''}")
    else:
        lines.append("No recorded decisions.")

    lines.extend([
        "",
        "## Full Transcript",
    ])
    if meeting.transcripts:
        for t in meeting.transcripts:
            lines.append(f"**{t.speaker}** ({int(t.start_time)}s): {t.text}")
    else:
        lines.append("No transcript available.")

    content = "\n".join(lines)
    return Response(
        content=content,
        media_type="text/markdown",
        headers={"Content-Disposition": f"attachment; filename=meetora_{meeting_id}.md"}
    )

@router.get("/{meeting_id}/pdf")
def export_meeting_pdf(
    meeting_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Generate high-fidelity meeting report PDF with summaries, action items, and diarized transcript."""
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    date_str = meeting.created_at.strftime('%B %d, %Y - %H:%M UTC') if meeting.created_at else datetime.utcnow().strftime('%B %d, %Y')
    participants_str = ", ".join(meeting.participants or ["Team"])

    pdf = SimplePdfBuilder(meeting.title)
    pdf.add_header(meeting.title, subtitle=f"Date: {date_str} | Participants: {participants_str}")

    # Summary
    pdf.add_section("1. AI Executive Summary")
    overview = meeting.summary.overview if meeting.summary else "No automated summary generated yet."
    pdf.add_text_paragraph(overview)

    if meeting.summary and meeting.summary.key_takeaways:
        pdf.add_section("Key Takeaways")
        for pt in meeting.summary.key_takeaways:
            pdf.add_text_paragraph(str(pt), bullet=True)

    # Action Items
    pdf.add_section("2. Action Items & Next Steps")
    if meeting.action_items:
        for ai in meeting.action_items:
            status_symbol = "[COMPLETED]" if ai.status == "completed" else "[TODO]"
            desc = f"{status_symbol} {ai.title} -- Assignee: {ai.assignee or 'Unassigned'} | Due: {ai.deadline or 'TBD'} | Priority: {ai.priority.upper()}"
            pdf.add_text_paragraph(desc, bullet=True)
    else:
        pdf.add_text_paragraph("No action items assigned for this meeting.")

    # Decisions
    pdf.add_section("3. Key Decisions & Strategic Alignments")
    if meeting.decisions:
        for dec in meeting.decisions:
            pdf.add_text_paragraph(f"{dec.decision_text} ({dec.category})", bullet=True)
    else:
        pdf.add_text_paragraph("No formal strategic decisions recorded.")

    # Diarized Transcript
    pdf.add_section("4. Diarized Meeting Transcript")
    if meeting.transcripts:
        for t in meeting.transcripts:
            m = int(t.start_time // 60)
            s = int(t.start_time % 60)
            line = f"[{m:02d}:{s:02d}] {t.speaker}: {t.text}"
            pdf.add_text_paragraph(line)
    else:
        pdf.add_text_paragraph("Transcript pending or not available.")

    pdf_bytes = pdf.build()
    safe_filename = "".join([c if c.isalnum() else "_" for c in meeting.title.lower()][:30])

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="meetora_{safe_filename}.pdf"'}
    )

@router.get("/{meeting_id}/docx")
def export_meeting_docx(
    meeting_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Generate professional Word Document (.docx) with formatted headings, lists, and transcripts."""
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    date_str = meeting.created_at.strftime('%B %d, %Y - %H:%M UTC') if meeting.created_at else datetime.utcnow().strftime('%B %d, %Y')
    participants_str = ", ".join(meeting.participants or ["Team"])

    docx = SimpleDocxBuilder(meeting.title)
    docx.add_heading(meeting.title, level=1)
    docx.add_paragraph(f"Date: {date_str} | Participants: {participants_str}", italic=True)

    docx.add_heading("AI Executive Summary", level=2)
    overview = meeting.summary.overview if meeting.summary else "No automated summary generated yet."
    docx.add_paragraph(overview)

    if meeting.summary and meeting.summary.key_takeaways:
        docx.add_heading("Key Takeaways", level=2)
        for pt in meeting.summary.key_takeaways:
            docx.add_paragraph(str(pt), bullet=True)

    docx.add_heading("Action Items & Deliverables", level=2)
    if meeting.action_items:
        for ai in meeting.action_items:
            status_tag = "[Done]" if ai.status == "completed" else "[Pending]"
            line = f"{status_tag} {ai.title} (Owner: {ai.assignee or 'Unassigned'}, Due: {ai.deadline or 'TBD'}, Priority: {ai.priority})"
            docx.add_paragraph(line, bullet=True)
    else:
        docx.add_paragraph("No action items recorded.")

    docx.add_heading("Strategic Decisions", level=2)
    if meeting.decisions:
        for dec in meeting.decisions:
            docx.add_paragraph(f"{dec.decision_text} [{dec.category}]", bullet=True)
    else:
        docx.add_paragraph("No key decisions recorded.")

    docx.add_heading("Diarized Transcript", level=2)
    if meeting.transcripts:
        for t in meeting.transcripts:
            m = int(t.start_time // 60)
            s = int(t.start_time % 60)
            docx.add_paragraph(f"[{m:02d}:{s:02d}] {t.speaker}: {t.text}")
    else:
        docx.add_paragraph("No transcript available.")

    docx_bytes = docx.build()
    safe_filename = "".join([c if c.isalnum() else "_" for c in meeting.title.lower()][:30])

    return Response(
        content=docx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="meetora_{safe_filename}.docx"'}
    )

@router.get("/{meeting_id}/email-draft", response_model=EmailDraftResponse)
def generate_follow_up_email(
    meeting_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    subject = f"Follow-up & Action Items: {meeting.title}"
    body_lines = [
        f"Hi Team,",
        "",
        f"Thank you for attending our session on '{meeting.title}'. Here is the automated Meetora recap and follow-up plan:",
        "",
        "EXECUTIVE SUMMARY:",
        meeting.summary.overview if meeting.summary else "Pending generation.",
        "",
        "ACTION ITEMS:",
    ]
    if meeting.action_items:
        for i, a in enumerate(meeting.action_items, 1):
            body_lines.append(f"{i}. {a.title} (Owner: {a.assignee or 'Unassigned'}, Due: {a.deadline or 'TBD'})")
    else:
        body_lines.append("No immediate action items.")

    body_lines.extend([
        "",
        "KEY DECISIONS:",
    ])
    if meeting.decisions:
        for d in meeting.decisions:
            body_lines.append(f"- {d.decision_text}")
    else:
        body_lines.append("- None")

    body_lines.extend([
        "",
        "Please let me know if anything was missed or needs adjustment.",
        "",
        f"Best regards,",
        f"{current_user.full_name or 'Meeting Host'}"
    ])

    return {
        "meeting_id": meeting.id,
        "subject": subject,
        "recipients": meeting.participants or [],
        "body": "\n".join(body_lines),
    }
