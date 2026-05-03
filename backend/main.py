import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

from graph import pipeline

app = FastAPI(title="AI Job Application Assistant")

# Allow GitHub Pages frontend to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten to your GitHub Pages URL after deployment
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Required environment variables — fail fast if any are missing
# ---------------------------------------------------------------------------
REQUIRED_ENV_VARS = [
    "GROQ_API_KEY",
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
# Request / Response models
# ---------------------------------------------------------------------------

class GenerateRequest(BaseModel):
    job_url: str
    sender_email: str = "rishika3895@gmail.com"


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
    # Validate env vars before running the pipeline
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
