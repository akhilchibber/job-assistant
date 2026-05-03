# AI-Powered Job Application Assistant

## Scope
User provides a **job posting URL** → Supervisor Agent orchestrates the pipeline →
output is a **tailored Cover Letter PDF** (downloadable) + **email sent** to the hiring contact
with Resume and Cover Letter attached.  
Resume stays fixed (stored once in Supabase). Single link, single run.

---

## Agents

| Agent | Role | LLM? |
|---|---|---|
| **Supervisor Agent** | Receives the job URL, decides which agent to invoke next, handles errors (e.g. no email found → skip sending, just return PDF) | Yes (Groq) |
| **Scraper Agent** | Fetches and extracts raw text from the job posting URL | No (BeautifulSoup) |
| **Cover Letter Agent** | Reads JD text + resume text + tailoring rules → writes cover letter | Yes (Groq) |
| **Contact Extractor Agent** | Scans JD text for hiring manager name + email | Yes (Groq) |
| **Email Drafter & Sender Agent** | Writes email subject + body, sends via Gmail API with both PDFs attached | Yes (Groq) |
| **PDF Export** | Renders cover letter text → PDF (ReportLab) | No — utility, not an agent |

---

## Pipeline Flow

```
[User Input: Job URL]
        ↓
┌─────────────────────────────┐
│      SUPERVISOR AGENT       │  ← LLM-powered, decides flow + handles errors
└─────────────────────────────┘
        ↓
  ┌─────┴──────┐
  ↓            ↓
[Scraper]   [Resume Loader — fetches from Supabase]
  ↓            ↓
  └─────┬──────┘
        ↓ (JD text + Resume text)
[Cover Letter Agent]
        ↓
[PDF Export utility]  →  cover_letter.pdf → uploaded to Supabase Storage
        ↓
[Contact Extractor Agent]
        ↓
        ├── email found?
        │     YES → [Email Drafter & Sender Agent] → email sent with both PDFs
        │     NO  → Supervisor skips email, returns PDF only
        ↓
[Output: PDF download link + email confirmation (or skip notice)]
```

---

## Tailoring Rules (System Prompt — Cover Letter Agent)
- Match the job title and company name exactly
- Mirror keywords and skills from the job description
- Highlight only resume points relevant to this specific role
- Keep tone professional, length to 1 page
- Open with a strong hook referencing the specific role and company

---

## Frontend UI (GitHub Pages)

Single page form — not a chatbot:

```
┌─────────────────────────────────────────────┐
│   🤖 AI Job Application Assistant           │
│                                             │
│   Paste Job Posting URL:                    │
│   [ https://...                           ] │
│                                             │
│   Your Email (to send from):               │
│   [ you@gmail.com                         ] │
│                                             │
│          [ Generate & Send Application ]    │
│                                             │
│   ── Status ──────────────────────────────  │
│   ✅ Job scraped                            │
│   ✅ Cover letter generated                 │
│   ✅ Hiring contact found: jane@company.com │
│   ✅ Email sent                             │
│                                             │
│   [ ⬇ Download Cover Letter PDF ]          │
└─────────────────────────────────────────────┘
```

---

## Tech Stack

| Layer | Tool | Cost |
|---|---|---|
| LLM | [Groq API](https://console.groq.com) (Llama 3) | Free tier |
| Agent Framework | LangChain + LangGraph (Supervisor pattern) | Free / open source |
| Web Scraping | `requests` + `BeautifulSoup` | Free / open source |
| Resume Storage | Supabase Storage + `pdfplumber` to parse text | Free tier (1GB) |
| PDF Generation | ReportLab | Free / open source |
| Email Sending | Gmail API (OAuth2) | Free |
| Backend Hosting | Hugging Face Spaces (CPU Basic — no sleep, 2vCPU/16GB RAM) | Free |
| Frontend Hosting | GitHub Pages | Free |

---

## Data Flow

```
resume.pdf (Supabase Storage)
        +
job URL (user input)
        ↓
FastAPI  POST /generate  (Hugging Face Spaces)
        ↓
Supervisor Agent → orchestrates all sub-agents
        ↓
returns: { pdf_url, email_status }
        ↓
Frontend (GitHub Pages): PDF download button + status message
```

---

## Implementation Steps

1. ✅ **Setup** — Groq API key, Supabase project, Gmail OAuth2 credentials, Hugging Face account, GitHub repo
2. ✅ **Resume Storage** — Upload resume PDF to Supabase Storage; `resume_loader.py` fetches + parses it with `pdfplumber`
3. ✅ **Sub-Agents** — Implement Scraper, Cover Letter, Contact Extractor, Email Drafter & Sender as individual LangGraph nodes
4. ✅ **PDF Export** — ReportLab utility renders cover letter text to styled PDF, uploads to Supabase Storage, returns public URL
5. ✅ **Supervisor Agent** — LangGraph Supervisor node wires all sub-agents, handles conditional routing (email found / not found)
6. ✅ **Backend** — FastAPI `POST /generate` triggers the Supervisor; returns PDF URL + email status
7. **Frontend** — Single `index.html` on GitHub Pages: URL input → calls backend → shows download link + status
8. **Deploy** — Backend to Hugging Face Spaces (Docker), frontend to GitHub Pages, all secrets in env vars

---

## Project Structure

```
job-assistant/
├── backend/
│   ├── main.py              # FastAPI app — single /generate endpoint
│   ├── graph.py             # LangGraph Supervisor + StateGraph wiring
│   ├── agents.py            # All sub-agent node functions
│   ├── pdf_export.py        # ReportLab PDF utility
│   ├── email_sender.py      # Gmail API integration
│   ├── resume_loader.py     # Supabase fetch + pdfplumber parse
│   ├── Dockerfile           # For Hugging Face Spaces deployment
│   └── requirements.txt
├── frontend/
│   └── index.html           # GitHub Pages UI
└── PROJECT.md
```
