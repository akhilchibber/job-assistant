import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl
from dotenv import load_dotenv

load_dotenv()

from graph import pipeline

app = FastAPI(title="AI Job Application Assistant")

# Allow GitHub Pages frontend to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten to your GitHub Pages URL in production
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)


class GenerateRequest(BaseModel):
    job_url: str
    sender_email: str


class GenerateResponse(BaseModel):
    cover_letter_url: str
    email_status: str
    status_log: list


@app.get("/")
def health():
    return {"status": "ok", "service": "AI Job Application Assistant"}


@app.post("/generate", response_model=GenerateResponse)
def generate(req: GenerateRequest):
    if not req.job_url.startswith("http"):
        raise HTTPException(status_code=400, detail="Invalid URL")

    initial_state = {
        "job_url": req.job_url,
        "sender_email": req.sender_email or "rishika3895@gmail.com",
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
