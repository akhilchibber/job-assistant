import os
import json
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

from graph import pipeline

app = FastAPI(title="AI Job Application Assistant")

# Allow GitHub Pages frontend to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Required environment variables
# ---------------------------------------------------------------------------
REQUIRED_ENV_VARS = [
    "OPENROUTER_API_KEY",
    "SUPABASE_URL",
    "SUPABASE_KEY",
    "SUPABASE_SERVICE_KEY",
    "SUPABASE_BUCKET",
    "SUPABASE_RESUME_PATH",
    "GMAIL_CLIENT_ID",
    "GMAIL_CLIENT_SECRET",
    "GMAIL_TOKEN",
    "GMAIL_REFRESH_TOKEN",
]


def check_env():
    missing = [v for v in REQUIRED_ENV_VARS if not os.environ.get(v)]
    return missing


# ---------------------------------------------------------------------------
# Agent node name → frontend key mapping
# ---------------------------------------------------------------------------
NODE_TO_AGENT = {
    "scraper":           "scraper",
    "resume_loader":     "resume_loader",
    "cover_letter":      "cover_letter",
    "pdf_export":        "pdf_export",
    "contact_extractor": "contact_extractor",
    "email_sender":      "email_sender",
}


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class GenerateRequest(BaseModel):
    job_url: str
    sender_email: str = "akhil.chibber@gmail.com"


class GenerateResponse(BaseModel):
    cover_letter_url: str
    email_status: str
    status_log: list


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/")
def health():
    missing = check_env()
    if missing:
        return {
            "status": "degraded",
            "missing_env_vars": missing,
            "service": "AI Job Application Assistant",
        }
    return {"status": "ok", "service": "AI Job Application Assistant"}


@app.post("/generate", response_model=GenerateResponse)
def generate(req: GenerateRequest):
    missing = check_env()
    if missing:
        raise HTTPException(
            status_code=500,
            detail=f"Missing environment variables: {', '.join(missing)}"
        )

    if not req.job_url.startswith("http"):
        raise HTTPException(status_code=400, detail="Invalid URL — must start with http")

    initial_state = {
        "job_url": req.job_url,
        "sender_email": req.sender_email,
        "status_log": [],
    }

    try:
        final_state = pipeline.invoke(initial_state)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pipeline error: {str(e)}")

    return GenerateResponse(
        cover_letter_url=final_state.get("cover_letter_url", ""),
        email_status=final_state.get("email_status", "not attempted"),
        status_log=final_state.get("status_log", []),
    )


@app.post("/stream")
def stream(req: GenerateRequest):
    """SSE endpoint — streams agent progress events one by one as each node completes."""
    missing = check_env()
    if missing:
        raise HTTPException(
            status_code=500,
            detail=f"Missing environment variables: {', '.join(missing)}"
        )

    if not req.job_url.startswith("http"):
        raise HTTPException(status_code=400, detail="Invalid URL — must start with http")

    def event_generator():
        initial_state = {
            "job_url": req.job_url,
            "sender_email": req.sender_email,
            "status_log": [],
        }

        # Emit supervisor as running first
        yield f"data: {json.dumps({'agent': 'supervisor', 'status': 'running', 'message': 'Orchestrating pipeline...'})}\n\n"

        final_state = {}
        prev_log_len = 0

        try:
            for chunk in pipeline.stream(initial_state, stream_mode="updates"):
                for node_name, node_state in chunk.items():
                    agent_key = NODE_TO_AGENT.get(node_name)
                    if not agent_key:
                        continue

                    # Get the latest status_log entry for this node
                    log = node_state.get("status_log", [])
                    message = log[-1] if log else "Done"

                    # Determine if skipped
                    status = "skipped" if "skip" in message.lower() else "done"

                    yield f"data: {json.dumps({'agent': agent_key, 'status': status, 'message': message})}\n\n"
                    yield ": keep-alive\n\n"  # flush padding

                    # Emit next agent as running (preview)
                    node_order = list(NODE_TO_AGENT.keys())
                    idx = node_order.index(node_name) if node_name in node_order else -1
                    if idx >= 0 and idx + 1 < len(node_order):
                        next_agent = NODE_TO_AGENT[node_order[idx + 1]]
                        yield f"data: {json.dumps({'agent': next_agent, 'status': 'running', 'message': 'Processing...'})}\n\n"
                        yield ": keep-alive\n\n"  # flush padding

                    # Track final state
                    final_state.update(node_state)

            # Mark supervisor done
            yield f"data: {json.dumps({'agent': 'supervisor', 'status': 'done', 'message': 'Pipeline complete'})}\n\n"

            # Emit final event with results
            cover_letter_url = final_state.get("cover_letter_url", "")
            email_status = final_state.get("email_status", "not attempted")
            yield f"data: {json.dumps({'agent': 'supervisor', 'status': 'done', 'message': 'Pipeline complete', 'final': True, 'cover_letter_url': cover_letter_url, 'email_status': email_status})}\n\n"
            yield ": keep-alive\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'agent': 'supervisor', 'status': 'error', 'message': str(e), 'final': True})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
