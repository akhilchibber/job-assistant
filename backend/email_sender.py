import os
import base64
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build


def _build_gmail_service():
    """Build Gmail API service using OAuth2 credentials from env vars."""
    creds = Credentials(
        token=os.environ["GMAIL_TOKEN"],
        refresh_token=os.environ["GMAIL_REFRESH_TOKEN"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["GMAIL_CLIENT_ID"],
        client_secret=os.environ["GMAIL_CLIENT_SECRET"],
    )
    return build("gmail", "v1", credentials=creds)


def send_application_email(
    sender_email: str,
    recipient_email: str,
    subject: str,
    body: str,
    resume_bytes: bytes,
    cover_letter_bytes: bytes,
) -> dict:
    """
    Send an email with resume and cover letter as PDF attachments.
    Returns a dict with message id on success.
    """
    msg = MIMEMultipart()
    msg["From"] = sender_email
    msg["To"] = recipient_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    # Attach resume
    _attach_pdf(msg, resume_bytes, "resume.pdf")
    # Attach cover letter
    _attach_pdf(msg, cover_letter_bytes, "cover_letter.pdf")

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    service = _build_gmail_service()
    sent = service.users().messages().send(userId="me", body={"raw": raw}).execute()
    return sent


def _attach_pdf(msg: MIMEMultipart, pdf_bytes: bytes, filename: str):
    part = MIMEBase("application", "octet-stream")
    part.set_payload(pdf_bytes)
    encoders.encode_base64(part)
    part.add_header("Content-Disposition", f'attachment; filename="{filename}"')
    msg.attach(part)
