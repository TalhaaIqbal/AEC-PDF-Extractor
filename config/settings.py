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
UPLOAD_DIR = Path("uploads")
OUTPUT_DIR = Path("outputs")
UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

# In-memory session storage (in production, use Redis or database)
sessions: Dict[str, dict] = {}

# CORS configuration
CORS_ORIGINS = ["http://localhost:3000", "http://localhost:3001"]
CORS_ALLOW_CREDENTIALS = True
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

# JSON Schemas
SYSTEM_PROMPT = """
You are an expert AEC (architecture / engineering / construction)
drawing interpreter.

PRIMARY EVIDENCE: the page image itself.
SUPPORTING EVIDENCE (when provided): native PDF text spans and
vector path geometry extracted directly from the file.

Your job is to detect and extract only MEANINGFUL, RELIABLE AEC
information:

PROJECT / SHEET
- project name, project number, sheet number, sheet title,
  drawing title, discipline, drawing type, revision info

SPACES
- room names, room numbers, space functions, major zones

ELEMENTS
- walls, partitions, doors, windows, openings, stairs, ramps,
  columns, structural elements, important fixtures

DIMENSIONS / LEVELS
- dimensions, elevations, floor levels, ceiling heights,
  grid references

ANNOTATIONS
- notes, material callouts, specifications, section/detail
  references

RELATIONSHIPS
- room adjacency, door-connects-room-A-to-room-B, window belongs
  to a wall/room, stairs connect levels

RULES:
- Trust the image over any supporting text/vector evidence.
- Never invent information. If it cannot be reliably determined,
  omit it or leave the field empty.
- If this page contains NO detectable AEC content at all (blank
  page, cover sheet with no drawing, unreadable scan, etc.), set
  "detection_status" to "no_elements_detected" and leave every
  list empty rather than guessing.
- Ignore borders, page frames, and the title block/legend UNLESS
  extracting sheet/project metadata from them specifically.
- Do not reproduce raw OCR/vector noise or machine IDs.

Return ONLY valid JSON. No Markdown fences, no explanations
outside the JSON.
"""

PAGE_JSON_SCHEMA = """{
  "page": <int>,
  "detection_status": "ok" | "no_elements_detected",
  "sheet": {
    "sheet_number": null,
    "sheet_title": null,
    "drawing_title": null,
    "discipline": null,
    "drawing_type": null
  },
  "project": {
    "project_name": null,
    "project_number": null
  },
  "levels": [],
  "grids": [],
  "rooms": [],
  "walls": [],
  "doors": [],
  "windows": [],
  "columns": [],
  "stairs": [],
  "dimensions": [],
  "elevations": [],
  "annotations": [],
  "references": [],
  "materials": [],
  "notes": [],
  "relationships": []
}"""

FINAL_SCHEMA = """{
  "project": {"project_name": null, "project_number": null},
  "sheets": [],
  "levels": [],
  "grids": [],
  "rooms": [],
  "walls": [],
  "doors": [],
  "windows": [],
  "columns": [],
  "stairs": [],
  "dimensions": [],
  "elevations": [],
  "annotations": [],
  "references": [],
  "materials": [],
  "notes": [],
  "relationships": [],
  "pages": []
}"""


def configure_cors(app: FastAPI) -> None:
    """Configure CORS middleware for the FastAPI application"""
    app.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ORIGINS,
        allow_credentials=CORS_ALLOW_CREDENTIALS,
        allow_methods=CORS_ALLOW_METHODS,
        allow_headers=CORS_ALLOW_HEADERS,
    )
