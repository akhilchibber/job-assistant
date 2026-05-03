"""
LangGraph pipeline with Supervisor pattern.

State flows through nodes:
  scraper → cover_letter → pdf_export → contact_extractor → (email | done)

The Supervisor is implemented as a conditional router — it inspects state
after each node and decides the next step, handling the email-not-found case.
"""

from typing import TypedDict, Optional
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
    # Final status log
    status_log: list


# ---------------------------------------------------------------------------
# Node wrappers
# ---------------------------------------------------------------------------

def node_scraper(state: AgentState) -> AgentState:
    state.setdefault("status_log", [])
    state = scraper_agent(state)
    state["status_log"].append(f"Scraper: {state.get('scrape_status', 'done')}")
    return state


def node_resume_loader(state: AgentState) -> AgentState:
    state["resume_text"] = fetch_resume_text()
    state["status_log"].append("Resume loaded from Supabase")
    return state


def node_cover_letter(state: AgentState) -> AgentState:
    state = cover_letter_agent(state)
    state["status_log"].append("Cover letter generated")
    return state


def node_pdf_export(state: AgentState) -> AgentState:
    pdf_bytes = generate_cover_letter_pdf(state["cover_letter_text"])
    state["cover_letter_bytes"] = pdf_bytes
    url = upload_pdf(pdf_bytes, "cover_letter.pdf")
    state["cover_letter_url"] = url
    state["status_log"].append(f"PDF exported and uploaded: {url}")
    return state


def node_contact_extractor(state: AgentState) -> AgentState:
    state = contact_extractor_agent(state)
    name = state.get("hiring_manager_name") or "not found"
    email = state.get("hiring_manager_email") or "not found"
    state["status_log"].append(f"Contact extracted — name: {name}, email: {email}")
    return state


def node_email_sender(state: AgentState) -> AgentState:
    state = email_drafter_sender_agent(state)
    state["status_log"].append(f"Email: {state.get('email_status', 'unknown')}")
    return state


# ---------------------------------------------------------------------------
# Supervisor routing — decides whether to send email or skip
# ---------------------------------------------------------------------------

def supervisor_route_after_contact(state: AgentState) -> str:
    """If a hiring manager email was found, send the email. Otherwise finish."""
    if state.get("hiring_manager_email"):
        return "send_email"
    state["email_status"] = "skipped — no hiring contact email found in job posting"
    state["status_log"].append(state["email_status"])
    return "done"


# ---------------------------------------------------------------------------
# Build the graph
# ---------------------------------------------------------------------------

def build_graph() -> StateGraph:
    graph = StateGraph(AgentState)

    graph.add_node("scraper", node_scraper)
    graph.add_node("resume_loader", node_resume_loader)
    graph.add_node("cover_letter", node_cover_letter)
    graph.add_node("pdf_export", node_pdf_export)
    graph.add_node("contact_extractor", node_contact_extractor)
    graph.add_node("email_sender", node_email_sender)

    # Entry: run scraper and resume loader (sequential for simplicity)
    graph.set_entry_point("scraper")
    graph.add_edge("scraper", "resume_loader")
    graph.add_edge("resume_loader", "cover_letter")
    graph.add_edge("cover_letter", "pdf_export")
    graph.add_edge("pdf_export", "contact_extractor")

    # Supervisor conditional routing after contact extraction
    graph.add_conditional_edges(
        "contact_extractor",
        supervisor_route_after_contact,
        {
            "send_email": "email_sender",
            "done": END,
        },
    )
    graph.add_edge("email_sender", END)

    return graph.compile()


# Compiled graph — imported by main.py
pipeline = build_graph()
