"""
Configuration Settings
Application configuration including CORS, directories, session storage, and AI settings
"""
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
from typing import Dict
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Directory configuration
import tempfile
import os

# Use temporary directory for serverless environments
if os.environ.get('VERCEL') or os.environ.get('AWS_LAMBDA_FUNCTION_NAME'):
    # Use temp directory for serverless environments
    UPLOAD_DIR = Path(tempfile.gettempdir()) / "uploads"
    OUTPUT_DIR = Path(tempfile.gettempdir()) / "outputs"
else:
    # Use local directories for development
    UPLOAD_DIR = Path("uploads")
    OUTPUT_DIR = Path("outputs")

# Create directories if they don't exist (will fail silently in read-only environments)
try:
    UPLOAD_DIR.mkdir(exist_ok=True, parents=True)
    OUTPUT_DIR.mkdir(exist_ok=True, parents=True)
except OSError:
    # In read-only environments, we'll handle directory creation per-request
    pass

# In-memory session storage (in production, use Redis or database)
sessions: Dict[str, dict] = {}

# CORS configuration
CORS_ORIGINS = [
    "*"
]
CORS_ALLOW_CREDENTIALS = False
CORS_ALLOW_METHODS = ["*"]
CORS_ALLOW_HEADERS = ["*"]

# AI Configuration
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY not found in environment variables")

# Processing Configuration
LLM_MAX_IMAGE_DIMENSION = 2000
PDF_DPI = 250
MAX_CONTEXT_CHARS = 30000


def configure_cors(app: FastAPI) -> None:
    """Configure CORS middleware for the FastAPI application"""
    app.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ORIGINS,
        allow_credentials=CORS_ALLOW_CREDENTIALS,
        allow_methods=CORS_ALLOW_METHODS,
        allow_headers=CORS_ALLOW_HEADERS,
    )
