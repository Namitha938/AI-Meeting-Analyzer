import os
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Tuple
from app.config import settings

logger = logging.getLogger("meetora.email")

def send_smtp_email(
    recipients: List[str],
    subject: str,
    body: str,
    is_html: bool = False
) -> Tuple[bool, str]:
    """
    Sends an email to recipients using configured SMTP settings.
    Supports both Port 465 (SMTP_SSL) and Port 587 (STARTTLS).
    If SMTP credentials are not configured, logs a simulated send.
    """
    if not recipients:
        return False, "No recipient email addresses provided."

    clean_recipients = [r.strip() for r in recipients if r and r.strip()]
    if not clean_recipients:
        return False, "No valid recipient email addresses."

    smtp_user = (os.getenv("SMTP_USER") or settings.SMTP_USER or "").strip()
    smtp_pass = (os.getenv("SMTP_PASSWORD") or settings.SMTP_PASSWORD or "").strip()
    smtp_host = (os.getenv("SMTP_HOST") or settings.SMTP_HOST or "smtp.gmail.com").strip()
    smtp_port = int(os.getenv("SMTP_PORT") or settings.SMTP_PORT or 465)

    if not smtp_user or not smtp_pass:
        logger.info(f"[SIMULATED EMAIL] To: {clean_recipients} | Subject: {subject}")
        return False, "SMTP credentials (SMTP_USER / SMTP_PASSWORD) are not set. (Simulated delivery only)"

    from_email = (os.getenv("EMAILS_FROM_EMAIL") or settings.EMAILS_FROM_EMAIL or smtp_user).strip()

    # Remove any internal spaces in Gmail App Password if entered with spaces
    clean_pass = smtp_pass.replace(" ", "") if "gmail" in smtp_host.lower() else smtp_pass

    try:
        # Port 465 uses SSL directly; Port 587 uses STARTTLS
        if smtp_port == 465:
            server = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=8)
        else:
            server = smtplib.SMTP(smtp_host, smtp_port, timeout=8)
            server.starttls()

        with server:
            server.login(smtp_user, clean_pass)
            for rcpt in clean_recipients:
                msg = MIMEMultipart("alternative")
                msg["From"] = f"Meetora AI <{from_email}>"
                msg["To"] = rcpt
                msg["Subject"] = subject
                msg.attach(MIMEText(body, "html" if is_html else "plain", "utf-8"))
                server.send_message(msg)

        logger.info(f"Delivered email via SMTP to {clean_recipients}")
        return True, f"Invitation successfully delivered to {', '.join(clean_recipients)} via SMTP ({from_email})."
    except Exception as e:
        logger.error(f"Failed to dispatch SMTP email: {e}")
        # Try automatic fallback port (587 if 465 failed, or 465 if 587 failed)
        fallback_port = 587 if smtp_port == 465 else 465
        try:
            if fallback_port == 465:
                fallback_server = smtplib.SMTP_SSL(smtp_host, 465, timeout=12)
            else:
                fallback_server = smtplib.SMTP(smtp_host, 587, timeout=12)
                fallback_server.starttls()

            with fallback_server:
                fallback_server.login(smtp_user, clean_pass)
                for rcpt in clean_recipients:
                    msg = MIMEMultipart("alternative")
                    msg["From"] = f"Meetora AI <{from_email}>"
                    msg["To"] = rcpt
                    msg["Subject"] = subject
                    msg.attach(MIMEText(body, "html" if is_html else "plain", "utf-8"))
                    fallback_server.send_message(msg)

            logger.info(f"Delivered email via fallback SMTP (port {fallback_port}) to {clean_recipients}")
            return True, f"Invitation successfully delivered to {', '.join(clean_recipients)}."
        except Exception as e2:
            logger.error(f"SMTP fallback failed as well: {e2}")
            return False, f"SMTP delivery failed ({str(e2)}). Verify SMTP credentials."
