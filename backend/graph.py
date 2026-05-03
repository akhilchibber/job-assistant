"""
LangGraph pipeline with Supervisor pattern.

State flows through nodes:
  scraper + resume_loader → cover_letter → pdf_export → contact_extractor → (email | done)

The Supervisor is a conditional router node — it inspects state after contact extraction
and decides whether to send the email or skip it gracefully.
"""

import io
import pdfplumber
from typing import Optional
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, END

from agents import (
    scraper_agent,
    cover_letter_agent,
    contact_extractor_agent,
    email_drafter_sender_agent,
)
from pdf_export import generate_cover_letter_pdf
from resume_loader import fetch_resume_text, upload_pdf


# ---------------------------------------------------------------------------
# Shared state schema
# ---------------------------------------------------------------------------

class AgentState(TypedDict, total=False):
    # Inputs
    job_url: str
    sender_email: str
    # Scraped data
    jd_text: str
    scrape_status: str
    # Resume
    resume_text: str
    resume_bytes: bytes
    # Cover letter
    cover_letter_text: str
    cover_letter_bytes: bytes
    cover_letter_url: str
    # Contact
    hiring_manager_name: Optional[str]
    hiring_manager_email: Optional[str]
    # Email
    email_status: str
    # Status log shown to frontend
    status_log: list


# ---------------------------------------------------------------------------
# Node: Scraper
# ---------------------------------------------------------------------------

def node_scraper(state: AgentState) -> AgentState:
    state.setdefault("status_log", [])
    existing_jd = state.get("jd_text", "")
    state = scraper_agent(state)
    # If scraping failed but we already have JD text (e.g. injected for testing), keep it
    if state.get("scrape_status", "").startswith("error") and not state.get("jd_text"):
        state["jd_text"] = existing_jd
    state["status_log"].append(f"Job scraped ({state.get('scrape_status', 'done')})")
    return state


# ---------------------------------------------------------------------------
# Node: Resume Loader
# ---------------------------------------------------------------------------

def node_resume_loader(state: AgentState) -> AgentState:
    resume_text = fetch_resume_text()
    state["resume_text"] = resume_text
    # Also keep raw bytes for email attachment
    from resume_loader import get_supabase
    import os
    supabase = get_supabase()
    state["resume_bytes"] = supabase.storage.from_(
        os.environ["SUPABASE_BUCKET"]
    ).download(os.environ["SUPABASE_RESUME_PATH"])
    state["status_log"].append("Resume loaded from Supabase")
    return state


# ---------------------------------------------------------------------------
# Node: Cover Letter
# ---------------------------------------------------------------------------

def node_cover_letter(state: AgentState) -> AgentState:
    state = cover_letter_agent(state)
    state["status_log"].append("Cover letter generated")
    return state


# ---------------------------------------------------------------------------
# Node: PDF Export
# ---------------------------------------------------------------------------

def node_pdf_export(state: AgentState) -> AgentState:
    pdf_bytes = generate_cover_letter_pdf(state["cover_letter_text"])
    state["cover_letter_bytes"] = pdf_bytes
    url = upload_pdf(pdf_bytes, "cover_letter.pdf")
    # Strip trailing ? from Supabase public URL if present
    state["cover_letter_url"] = url.rstrip("?")
    state["status_log"].append(f"Cover letter PDF ready")
    return state


# ---------------------------------------------------------------------------
# Node: Contact Extractor
# ---------------------------------------------------------------------------

def node_contact_extractor(state: AgentState) -> AgentState:
    state = contact_extractor_agent(state)
    name = state.get("hiring_manager_name") or "not found"
    email = state.get("hiring_manager_email") or "not found"
    state["status_log"].append(f"Hiring contact: {name} | {email}")
    return state


# ---------------------------------------------------------------------------
# Node: Email Drafter & Sender
# ---------------------------------------------------------------------------

def node_email_sender(state: AgentState) -> AgentState:
    state = email_drafter_sender_agent(state)
    state["status_log"].append(f"Email: {state.get('email_status', 'unknown')}")
    return state


# ---------------------------------------------------------------------------
# Supervisor: conditional routing after contact extraction
# ---------------------------------------------------------------------------

def supervisor_route(state: AgentState) -> str:
    """
    Supervisor decision point:
    - If a hiring manager email was found → send the email
    - Otherwise → skip email, finish with PDF only
    """
    if state.get("hiring_manager_email"):
        return "send_email"
    # Graceful skip
    state["email_status"] = "skipped — no hiring contact email found in job posting"
    state["status_log"].append(state["email_status"])
    return "done"


# ---------------------------------------------------------------------------
# Build and compile the graph
# ---------------------------------------------------------------------------

def build_graph():
    graph = StateGraph(AgentState)

    graph.add_node("scraper", node_scraper)
    graph.add_node("resume_loader", node_resume_loader)
    graph.add_node("cover_letter", node_cover_letter)
    graph.add_node("pdf_export", node_pdf_export)
    graph.add_node("contact_extractor", node_contact_extractor)
    graph.add_node("email_sender", node_email_sender)

    # Pipeline edges
    graph.set_entry_point("scraper")
    graph.add_edge("scraper", "resume_loader")
    graph.add_edge("resume_loader", "cover_letter")
    graph.add_edge("cover_letter", "pdf_export")
    graph.add_edge("pdf_export", "contact_extractor")

    # Supervisor conditional routing
    graph.add_conditional_edges(
        "contact_extractor",
        supervisor_route,
        {
            "send_email": "email_sender",
            "done": END,
        },
    )
    graph.add_edge("email_sender", END)

    return graph.compile()


# Compiled pipeline — imported by main.py
pipeline = build_graph()
