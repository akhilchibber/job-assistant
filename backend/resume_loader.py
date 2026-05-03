import os
import io
import pdfplumber
from supabase import create_client

def get_supabase(service_role=False):
    url = os.environ["SUPABASE_URL"]
    # Use service role key for writes, anon key for reads
    key = os.environ["SUPABASE_SERVICE_KEY"] if service_role else os.environ["SUPABASE_KEY"]
    return create_client(url, key)

def fetch_resume_text() -> str:
    """Download resume PDF from Supabase Storage and extract its text."""
    supabase = get_supabase()  # anon key is fine for public bucket reads
    bucket = os.environ["SUPABASE_BUCKET"]          # e.g. "resumes"
    resume_path = os.environ["SUPABASE_RESUME_PATH"] # e.g. "resume.pdf"

    response = supabase.storage.from_(bucket).download(resume_path)
    # response is raw bytes
    with pdfplumber.open(io.BytesIO(response)) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)
    return text.strip()

def upload_pdf(pdf_bytes: bytes, filename: str) -> str:
    """Upload a PDF to Supabase Storage and return its public URL."""
    supabase = get_supabase(service_role=True)  # service role needed for writes
    bucket = os.environ["SUPABASE_BUCKET"]

    supabase.storage.from_(bucket).upload(
        path=filename,
        file=pdf_bytes,
        file_options={"content-type": "application/pdf", "upsert": "true"},
    )
    public_url = supabase.storage.from_(bucket).get_public_url(filename)
    return public_url
