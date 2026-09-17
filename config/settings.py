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
LLM_MAX_IMAGE_DIMENSION = 2000  # Maximum dimension for images sent to LLM
PDF_DPI = 250  # Maximum DPI for rendering (will be optimized to LLM_MAX_IMAGE_DIMENSION)
MAX_CONTEXT_CHARS = 30000

# JSON Schemas
ARCHITECTURAL_SYSTEM_PROMPT = """
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
- For text content (room names, dimensions, sheet numbers, annotations), trust exact PDF text over image interpretation when available.
- For spatial/visual content (relationships, geometry, positions), trust the image.
- Use supporting text/vector evidence to verify and correct visual interpretation errors from blurry images.
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

# Keep original SYSTEM_PROMPT for backward compatibility
SYSTEM_PROMPT = ARCHITECTURAL_SYSTEM_PROMPT

CIVIL_SYSTEM_PROMPT = """
You are an expert civil engineering drawing interpreter.

PRIMARY EVIDENCE: the page image itself.
SUPPORTING EVIDENCE (when provided): native PDF text spans and
vector path geometry extracted directly from the file.

Your job is to detect and extract only MEANINGFUL, RELIABLE civil
engineering information:

ROADWAY ELEMENTS:
- Stations (e.g., STA 28+51.92, +51.92 callouts)
- Offsets (e.g., 28.28' RT, 15.5' LT)
- Match lines (e.g., STA 25+60.00 to 31+40.00)
- Curb and gutter types (C&G, SDK)
- Pedestrian ramps (CR-A, type, slope)
- Right-of-way lines (R/W, work limits)
- Hatched areas (per legend)
- Elevations and grades

CIVIL ABBREVIATIONS:
- C&G: Curb and Gutter
- SDK: Sidewalk, Curb and Gutter
- R/W: Right of Way
- LT/RT: Left/Right offset
- STA: Station
- PROP.: Proposed
- EXIST.: Existing
- TC: Top of Curb
- BC: Bottom of Curb
- CL: Centerline

STATION READING RULES:
- A "+51.92" callout near station tick 28 means STA 28+51.92
- Stations are typically in format: whole+feet.hundredths
- Match lines define station ranges for elements
- Offsets are perpendicular distance from centerline

RULES:
- For text content (stations, offsets, specifications), trust exact PDF text over image interpretation when available.
- For spatial/visual content (positions, relationships), trust the image.
- Use supporting text/vector evidence to verify and correct visual interpretation errors from blurry images.
- Never invent information. If it cannot be reliably determined, omit it or leave the field empty.
- If this page contains NO detectable civil content at all, set "detection_status" to "no_elements_detected" and leave every list empty rather than guessing.
- Validate that stations fall within the sheet's match line ranges when provided.

Return ONLY valid JSON. No Markdown fences, no explanations outside the JSON.
"""

ARCHITECTURAL_PAGE_JSON_SCHEMA = """{
  "page": <int>,
  "detection_status": "ok" | "no_elements_detected",
  "sheet": {
    "sheet_number": null,
    "sheet_title": null,
    "drawing_title": null,
    "discipline": null,
    "drawing_type": null,
    "confidence": "high" | "medium" | "low"
  },
  "project": {
    "project_name": null,
    "project_number": null,
    "confidence": "high" | "medium" | "low"
  },
  "levels": [
    {
      "name": <string>,
      "elevation": <string>,
      "height": <string>,
      "units": "feet" | "meters" | "inches",
      "source_page": <int>,
      "position": {"x": <float>, "y": <float>},
      "confidence": "high" | "medium" | "low"
    }
  ],
  "grids": [
    {
      "grid_id": <string>,
      "position": {"x": <float>, "y": <float>},
      "orientation": "horizontal" | "vertical",
      "source_page": <int>,
      "confidence": "high" | "medium" | "low"
    }
  ],
  "rooms": [
    {
      "room_number": <string>,
      "room_name": <string>,
      "area": <string>,
      "perimeter": <string>,
      "function": <string>,
      "zone": <string>,
      "position": {"x": <float>, "y": <float>, "width": <float>, "height": <float>},
      "source_page": <int>,
      "confidence": "high" | "medium" | "low"
    }
  ],
  "walls": [
    {
      "wall_id": <string>,
      "type": <string>,
      "length": <string>,
      "thickness": <string>,
      "height": <string>,
      "material": <string>,
      "position": {"start": {"x": <float>, "y": <float>}, "end": {"x": <float>, "y": <float>}},
      "source_page": <int>,
      "confidence": "high" | "medium" | "low"
    }
  ],
  "doors": [
    {
      "door_id": <string>,
      "type": <string>,
      "width": <string>,
      "height": <string>,
      "swing_direction": <string>,
      "material": <string>,
      "position": {"x": <float>, "y": <float>},
      "connects_rooms": [<string>, <string>],
      "source_page": <int>,
      "confidence": "high" | "medium" | "low"
    }
  ],
  "windows": [
    {
      "window_id": <string>,
      "type": <string>,
      "width": <string>,
      "height": <string>,
      "material": <string>,
      "position": {"x": <float>, "y": <float>},
      "associated_wall": <string>,
      "source_page": <int>,
      "confidence": "high" | "medium" | "low"
    }
  ],
  "columns": [
    {
      "column_id": <string>,
      "type": <string>,
      "dimensions": {"width": <string>, "depth": <string>},
      "material": <string>,
      "position": {"x": <float>, "y": <float>},
      "source_page": <int>,
      "confidence": "high" | "medium" | "low"
    }
  ],
  "stairs": [
    {
      "stair_id": <string>,
      "type": <string>,
      "rise": <string>,
      "run": <string>,
      "width": <string>,
      "number_of_steps": <int>,
      "connects_levels": [<string>, <string>],
      "position": {"x": <float>, "y": <float>},
      "source_page": <int>,
      "confidence": "high" | "medium" | "low"
    }
  ],
  "dimensions": [
    {
      "dimension_id": <string>,
      "value": <string>,
      "units": "feet" | "meters" | "inches",
      "type": "linear" | "angular" | "radial",
      "element_type": <string>,
      "position": {"x": <float>, "y": <float>},
      "source_page": <int>,
      "confidence": "high" | "medium" | "low"
    }
  ],
  "elevations": [
    {
      "elevation_id": <string>,
      "value": <string>,
      "reference": <string>,
      "units": "feet" | "meters" | "inches",
      "position": {"x": <float>, "y": <float>},
      "source_page": <int>,
      "confidence": "high" | "medium" | "low"
    }
  ],
  "annotations": [
    {
      "annotation_id": <string>,
      "text": <string>,
      "type": <string>,
      "position": {"x": <float>, "y": <float>},
      "source_page": <int>,
      "confidence": "high" | "medium" | "low"
    }
  ],
  "references": [
    {
      "reference_id": <string>,
      "type": "section" | "detail" | "elevation",
      "target": <string>,
      "position": {"x": <float>, "y": <float>},
      "source_page": <int>,
      "confidence": "high" | "medium" | "low"
    }
  ],
  "materials": [
    {
      "material_id": <string>,
      "name": <string>,
      "specification": <string>,
      "application": <string>,
      "position": {"x": <float>, "y": <float>},
      "source_page": <int>,
      "confidence": "high" | "medium" | "low"
    }
  ],
  "notes": [
    {
      "note_id": <string>,
      "text": <string>,
      "category": <string>,
      "position": {"x": <float>, "y": <float>},
      "source_page": <int>,
      "confidence": "high" | "medium" | "low"
    }
  ],
  "relationships": [
    {
      "relationship_id": <string>,
      "type": <string>,
      "source_element": <string>,
      "target_element": <string>,
      "description": <string>,
      "source_page": <int>,
      "confidence": "high" | "medium" | "low"
    }
  ]
}"""

# Keep original PAGE_JSON_SCHEMA for backward compatibility
PAGE_JSON_SCHEMA = ARCHITECTURAL_PAGE_JSON_SCHEMA

CIVIL_PAGE_JSON_SCHEMA = """{
  "page": <int>,
  "detection_status": "ok" | "no_elements_detected",
  "sheet_type": "roadway" | "site" | "grading" | "utility" | "architectural",
  "sheet": {
    "sheet_number": null,
    "sheet_title": null,
    "drawing_title": null,
    "discipline": null,
    "drawing_type": null,
    "confidence": "high" | "medium" | "low"
  },
  "project": {
    "project_name": null,
    "project_number": null,
    "confidence": "high" | "medium" | "low"
  },
  "stations": [
    {
      "station_id": <string>,
      "station_value": <string>,
      "offset": <string>,
      "offset_direction": "left" | "right",
      "position": {"x": <float>, "y": <float>},
      "source_page": <int>,
      "confidence": "high" | "medium" | "low"
    }
  ],
  "match_lines": [
    {
      "match_line_id": <string>,
      "start_station": <string>,
      "end_station": <string>,
      "position": {"start": {"x": <float>, "y": <float>}, "end": {"x": <float>, "y": <float>}},
      "source_page": <int>,
      "confidence": "high" | "medium" | "low"
    }
  ],
  "curb_gutter": [
    {
      "type": <string>,
      "station_range": <string>,
      "specification": <string>,
      "position": {"x": <float>, "y": <float>},
      "source_page": <int>,
      "confidence": "high" | "medium" | "low"
    }
  ],
  "ramps": [
    {
      "ramp_id": <string>,
      "type": <string>,
      "station": <string>,
      "slope": <string>,
      "position": {"x": <float>, "y": <float>},
      "source_page": <int>,
      "confidence": "high" | "medium" | "low"
    }
  ],
  "right_of_way": [
    {
      "row_id": <string>,
      "type": <string>,
      "station_range": <string>,
      "width": <string>,
      "position": {"x": <float>, "y": <float>},
      "source_page": <int>,
      "confidence": "high" | "medium" | "low"
    }
  ],
  "work_limits": [
    {
      "limit_id": <string>,
      "type": <string>,
      "station_range": <string>,
      "position": {"x": <float>, "y": <float>},
      "source_page": <int>,
      "confidence": "high" | "medium" | "low"
    }
  ],
  "hatched_areas": [
    {
      "area_id": <string>,
      "legend_type": <string>,
      "description": <string>,
      "position": {"x": <float>, "y": <float>, "width": <float>, "height": <float>},
      "source_page": <int>,
      "confidence": "high" | "medium" | "low"
    }
  ],
  "elevations": [
    {
      "elevation_id": <string>,
      "value": <string>,
      "station": <string>,
      "reference": <string>,
      "units": "feet" | "meters",
      "position": {"x": <float>, "y": <float>},
      "source_page": <int>,
      "confidence": "high" | "medium" | "low"
    }
  ],
  "annotations": [
    {
      "annotation_id": <string>,
      "text": <string>,
      "type": <string>,
      "position": {"x": <float>, "y": <float>},
      "source_page": <int>,
      "confidence": "high" | "medium" | "low"
    }
  ],
  "materials": [
    {
      "material_id": <string>,
      "name": <string>,
      "specification": <string>,
      "application": <string>,
      "position": {"x": <float>, "y": <float>},
      "source_page": <int>,
      "confidence": "high" | "medium" | "low"
    }
  ],
  "notes": [
    {
      "note_id": <string>,
      "text": <string>,
      "category": <string>,
      "position": {"x": <float>, "y": <float>},
      "source_page": <int>,
      "confidence": "high" | "medium" | "low"
    }
  ]
}"""

FINAL_SCHEMA = """{
  "project": {
    "project_name": null,
    "project_number": null,
    "confidence": "high" | "medium" | "low"
  },
  "sheets": [
    {
      "sheet_number": null,
      "sheet_title": null,
      "drawing_title": null,
      "discipline": null,
      "drawing_type": null,
      "source_page": <int>,
      "confidence": "high" | "medium" | "low"
    }
  ],
  "levels": [
    {
      "name": <string>,
      "elevation": <string>,
      "height": <string>,
      "units": "feet" | "meters" | "inches",
      "source_page": <int>,
      "position": {"x": <float>, "y": <float>},
      "confidence": "high" | "medium" | "low"
    }
  ],
  "grids": [
    {
      "grid_id": <string>,
      "position": {"x": <float>, "y": <float>},
      "orientation": "horizontal" | "vertical",
      "source_page": <int>,
      "confidence": "high" | "medium" | "low"
    }
  ],
  "rooms": [
    {
      "room_number": <string>,
      "room_name": <string>,
      "area": <string>,
      "perimeter": <string>,
      "function": <string>,
      "zone": <string>,
      "position": {"x": <float>, "y": <float>, "width": <float>, "height": <float>},
      "source_page": <int>,
      "confidence": "high" | "medium" | "low"
    }
  ],
  "walls": [
    {
      "wall_id": <string>,
      "type": <string>,
      "length": <string>,
      "thickness": <string>,
      "height": <string>,
      "material": <string>,
      "position": {"start": {"x": <float>, "y": <float>}, "end": {"x": <float>, "y": <float>}},
      "source_page": <int>,
      "confidence": "high" | "medium" | "low"
    }
  ],
  "doors": [
    {
      "door_id": <string>,
      "type": <string>,
      "width": <string>,
      "height": <string>,
      "swing_direction": <string>,
      "material": <string>,
      "position": {"x": <float>, "y": <float>},
      "connects_rooms": [<string>, <string>],
      "source_page": <int>,
      "confidence": "high" | "medium" | "low"
    }
  ],
  "windows": [
    {
      "window_id": <string>,
      "type": <string>,
      "width": <string>,
      "height": <string>,
      "material": <string>,
      "position": {"x": <float>, "y": <float>},
      "associated_wall": <string>,
      "source_page": <int>,
      "confidence": "high" | "medium" | "low"
    }
  ],
  "columns": [
    {
      "column_id": <string>,
      "type": <string>,
      "dimensions": {"width": <string>, "depth": <string>},
      "material": <string>,
      "position": {"x": <float>, "y": <float>},
      "source_page": <int>,
      "confidence": "high" | "medium" | "low"
    }
  ],
  "stairs": [
    {
      "stair_id": <string>,
      "type": <string>,
      "rise": <string>,
      "run": <string>,
      "width": <string>,
      "number_of_steps": <int>,
      "connects_levels": [<string>, <string>],
      "position": {"x": <float>, "y": <float>},
      "source_page": <int>,
      "confidence": "high" | "medium" | "low"
    }
  ],
  "dimensions": [
    {
      "dimension_id": <string>,
      "value": <string>,
      "units": "feet" | "meters" | "inches",
      "type": "linear" | "angular" | "radial",
      "element_type": <string>,
      "position": {"x": <float>, "y": <float>},
      "source_page": <int>,
      "confidence": "high" | "medium" | "low"
    }
  ],
  "elevations": [
    {
      "elevation_id": <string>,
      "value": <string>,
      "reference": <string>,
      "units": "feet" | "meters" | "inches",
      "position": {"x": <float>, "y": <float>},
      "source_page": <int>,
      "confidence": "high" | "medium" | "low"
    }
  ],
  "annotations": [
    {
      "annotation_id": <string>,
      "text": <string>,
      "type": <string>,
      "position": {"x": <float>, "y": <float>},
      "source_page": <int>,
      "confidence": "high" | "medium" | "low"
    }
  ],
  "references": [
    {
      "reference_id": <string>,
      "type": "section" | "detail" | "elevation",
      "target": <string>,
      "position": {"x": <float>, "y": <float>},
      "source_page": <int>,
      "confidence": "high" | "medium" | "low"
    }
  ],
  "materials": [
    {
      "material_id": <string>,
      "name": <string>,
      "specification": <string>,
      "application": <string>,
      "position": {"x": <float>, "y": <float>},
      "source_page": <int>,
      "confidence": "high" | "medium" | "low"
    }
  ],
  "notes": [
    {
      "note_id": <string>,
      "text": <string>,
      "category": <string>,
      "position": {"x": <float>, "y": <float>},
      "source_page": <int>,
      "confidence": "high" | "medium" | "low"
    }
  ],
  "relationships": [
    {
      "relationship_id": <string>,
      "type": <string>,
      "source_element": <string>,
      "target_element": <string>,
      "description": <string>,
      "source_page": <int>,
      "confidence": "high" | "medium" | "low"
    }
  ],
  "pages": [<int>]
}"""

# Schema and prompt mapping
SCHEMAS = {
    "architectural": ARCHITECTURAL_PAGE_JSON_SCHEMA,
    "civil": CIVIL_PAGE_JSON_SCHEMA
}

SYSTEM_PROMPTS = {
    "architectural": ARCHITECTURAL_SYSTEM_PROMPT,
    "civil": CIVIL_SYSTEM_PROMPT
}

# Default to architectural for backward compatibility
DEFAULT_SHEET_TYPE = "architectural"


def configure_cors(app: FastAPI) -> None:
    """Configure CORS middleware for the FastAPI application"""
    app.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ORIGINS,
        allow_credentials=CORS_ALLOW_CREDENTIALS,
        allow_methods=CORS_ALLOW_METHODS,
        allow_headers=CORS_ALLOW_HEADERS,
    )
