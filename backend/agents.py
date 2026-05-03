import os
import requests
from bs4 import BeautifulSoup
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage

from cover_letter_rules import COVER_LETTER_SYSTEM_PROMPT


# ---------------------------------------------------------------------------
# Shared LLM instance
# ---------------------------------------------------------------------------

def get_llm():
    return ChatGroq(
        model=os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile"),
        api_key=os.environ["GROQ_API_KEY"],
        temperature=0.3,
    )


# ---------------------------------------------------------------------------
# Scraper Agent — no LLM, pure HTTP + BeautifulSoup
# ---------------------------------------------------------------------------

def scraper_agent(state: dict) -> dict:
    """Fetch job posting URL and extract visible text."""
    url = state["job_url"]
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        # Remove script/style noise
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)
        # Trim to ~6000 chars to stay within LLM context
        state["jd_text"] = text[:6000]
        state["scrape_status"] = "success"
    except Exception as e:
        # Preserve any existing jd_text — don't blank it out on error
        if not state.get("jd_text"):
            state["jd_text"] = ""
        state["scrape_status"] = f"error: {str(e)}"
    return state


# ---------------------------------------------------------------------------
# Cover Letter Agent
# ---------------------------------------------------------------------------

def cover_letter_agent(state: dict) -> dict:
    """Generate a tailored cover letter from JD text + resume text."""
    llm = get_llm()
    messages = [
        SystemMessage(content=COVER_LETTER_SYSTEM_PROMPT),
        HumanMessage(content=f"""
JOB DESCRIPTION:
{state['jd_text']}

CANDIDATE RESUME:
{state['resume_text']}

Write the tailored cover letter now following all rules exactly.
"""),
    ]
    response = llm.invoke(messages)
    state["cover_letter_text"] = response.content.strip()
    return state


# ---------------------------------------------------------------------------
# Contact Extractor Agent
# ---------------------------------------------------------------------------

CONTACT_EXTRACTOR_SYSTEM_PROMPT = """You are an expert at extracting contact information from job postings.
Extract the hiring manager's name and email address from the job description text.

Rules:
- Return ONLY a JSON object with keys: "name" and "email"
- If name is not found, set "name" to null
- If email is not found, set "email" to null
- Do not guess or fabricate — only extract what is explicitly present
- Example output: {"name": "Jane Smith", "email": "jane@company.com"}"""


def contact_extractor_agent(state: dict) -> dict:
    """Extract hiring manager name and email from JD text."""
    import json
    llm = get_llm()
    messages = [
        SystemMessage(content=CONTACT_EXTRACTOR_SYSTEM_PROMPT),
        HumanMessage(content=f"JOB DESCRIPTION:\n{state['jd_text']}"),
    ]
    response = llm.invoke(messages)
    try:
        raw = response.content.strip()
        # Handle markdown code blocks if LLM wraps in ```json
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        contact = json.loads(raw.strip())
        state["hiring_manager_name"] = contact.get("name")
        state["hiring_manager_email"] = contact.get("email")
    except Exception:
        state["hiring_manager_name"] = None
        state["hiring_manager_email"] = None
    return state


# ---------------------------------------------------------------------------
# Email Drafter & Sender Agent
# ---------------------------------------------------------------------------

EMAIL_DRAFTER_SYSTEM_PROMPT = """You are a professional job application email writer.
Write a concise, professional email to accompany a job application.

Rules:
- Subject line: clear and specific, mention the role
- Body: 3 to 4 sentences max — introduce the candidate, mention the role, note attachments
- Warm but professional tone
- Return ONLY a JSON object with keys: "subject" and "body"
- Example: {"subject": "Application for Senior Engineer Role", "body": "Dear Jane, ..."}"""


def email_drafter_sender_agent(state: dict) -> dict:
    """Draft the application email and send it via Gmail API."""
    import json
    from email_sender import send_application_email

    llm = get_llm()
    manager_name = state.get("hiring_manager_name") or "Hiring Manager"

    messages = [
        SystemMessage(content=EMAIL_DRAFTER_SYSTEM_PROMPT),
        HumanMessage(content=f"""
Job Description Summary:
{state['jd_text'][:1500]}

Hiring Manager Name: {manager_name}
Resume Text (first 500 chars): {state['resume_text'][:500]}

Draft the application email now.
"""),
    ]
    response = llm.invoke(messages)
    try:
        raw = response.content.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        email_content = json.loads(raw.strip())
        subject = email_content.get("subject", "Job Application")
        body = email_content.get("body", "")
    except Exception:
        subject = "Job Application"
        body = f"Dear {manager_name},\n\nPlease find my resume and cover letter attached.\n\nBest regards,\nRishika Saini"

    try:
        send_application_email(
            sender_email=state["sender_email"],
            recipient_email=state["hiring_manager_email"],
            subject=subject,
            body=body,
            resume_bytes=state["resume_bytes"],
            cover_letter_bytes=state["cover_letter_bytes"],
        )
        state["email_status"] = f"sent to {state['hiring_manager_email']}"
    except Exception as e:
        state["email_status"] = f"failed: {str(e)}"

    return state
