"""KognityForge – FastAPI application entry point."""

import pathlib
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Load .env from project root (parent of backend/)
_project_root = pathlib.Path(__file__).resolve().parent.parent
load_dotenv(_project_root / ".env")

app = FastAPI(
    title="KognityForge API",
    version="0.1.0",
    description=(
        "AI-powered educational content generation workflow "
        "aligned with the 5E instructional model."
    ),
)

import os

# Lock down CORS to the Streamlit frontend
# We allow localhost for local dev, and FRONTEND_URL for production
allowed_origins = [
    "http://localhost:8501", 
    "http://127.0.0.1:8501"
]
frontend_url = os.getenv("FRONTEND_URL")
if frontend_url:
    allowed_origins.append(frontend_url)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# Ensure the backend directory is in sys.path so 'api.routes' resolves 
# regardless of whether uvicorn is run from root or backend/
import sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from api.routes import router  # noqa: E402

app.include_router(router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "kognityforge"}
