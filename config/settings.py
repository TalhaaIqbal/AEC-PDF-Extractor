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


def load_prompt_file(filename: str) -> str:
    """Load prompt content from prompts directory"""
    # Get the project root (parent of config directory)
    project_root = Path(__file__).parent.parent
    prompt_path = project_root / "prompts" / filename
    try:
        with open(prompt_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        raise RuntimeError(f"Prompt file not found: {prompt_path}")

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

# Load prompts from files
ARCHITECTURAL_SYSTEM_PROMPT = load_prompt_file("architectural_system_prompt.txt")
CIVIL_SYSTEM_PROMPT = load_prompt_file("civil_system_prompt.txt")
UNIVERSAL_SYSTEM_PROMPT = load_prompt_file("universal_system_prompt.txt")

# Keep original SYSTEM_PROMPT for backward compatibility
SYSTEM_PROMPT = ARCHITECTURAL_SYSTEM_PROMPT

# Load schemas from files
ARCHITECTURAL_PAGE_JSON_SCHEMA = load_prompt_file("architectural_schema.json")
CIVIL_PAGE_JSON_SCHEMA = load_prompt_file("civil_schema.json")
UNIVERSAL_PAGE_JSON_SCHEMA = load_prompt_file("universal_schema.json")

# Keep original PAGE_JSON_SCHEMA for backward compatibility
PAGE_JSON_SCHEMA = ARCHITECTURAL_PAGE_JSON_SCHEMA

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

UNIVERSAL_SYSTEM_PROMPT = """
You are an expert AEC (architecture/engineering/construction) drawing interpreter.

PRIMARY EVIDENCE: the page image itself.
SUPPORTING EVIDENCE (when provided): native PDF text spans and vector path geometry extracted directly from the file.

STEP 1: DETERMINE SHEET TYPE
First, examine the title block and drawing content to determine the sheet type:

CIVIL/ROADWAY SHEETS (if you see):
- Stations (e.g., STA 28+51.92, +51.92 callouts)
- Offsets (e.g., 28.28' RT, 15.5' LT) 
- Match lines (e.g., STA 25+60.00 to 31+40.00)
- Curb and gutter types (C&G, SDK)
- Right-of-way lines (R/W, work limits)
- Grading, drainage, paving, centerlines
- Hatched areas defined by legend

ARCHITECTURAL SHEETS (if you see):
- Rooms, room numbers, space functions
- Walls, partitions, doors, windows
- Stairs, ceilings, floor plans
- Building elements and fixtures

STEP 2: EXTRACT INFORMATION
Based on the detected sheet type, extract meaningful information:

FOR CIVIL/ROADWAY SHEETS:
- Stations, offsets, match lines
- Curb/gutter types and specifications
- Pedestrian ramps, right-of-way lines
- Work limits, hatched areas
- Elevations, grades, slopes
- Civil abbreviations: C&G (Curb and Gutter), SDK (Sidewalk, Curb and Gutter), R/W (Right of Way), LT/RT (Left/Right), STA (Station), PROP. (Proposed), EXIST. (Existing)
- Station reading: "+51.92" near station tick 28 means STA 28+51.92

FOR ARCHITECTURAL SHEETS:
- Rooms, walls, doors, windows, stairs
- Levels, elevations, dimensions
- Grids, columns, materials
- Annotations, notes, references

RULES:
- For text content, trust exact PDF text over image interpretation when available
- For spatial/visual content, trust the image
- Use supporting text/vector evidence to verify and correct visual interpretation errors
- Never invent information. If it cannot be reliably determined, omit it or leave the field empty
- If this page contains NO detectable AEC content, set "detection_status" to "no_elements_detected" and leave lists empty
- Use legends and abbreviation lists as CONTEXT to interpret symbols, hatch patterns, and abbreviations correctly, but DO NOT extract legend entries as separate elements
- Set "sheet_type" field to either "civil" or "architectural" based on your detection

Return ONLY valid JSON. No Markdown fences, no explanations outside the JSON.
"""

UNIVERSAL_PAGE_JSON_SCHEMA = """{
  "page": <int>,
  "detection_status": "ok" | "no_elements_detected",
  "sheet_type": "civil" | "architectural",
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

# Schema and prompt mapping
SCHEMAS = {
    "architectural": ARCHITECTURAL_PAGE_JSON_SCHEMA,
    "civil": CIVIL_PAGE_JSON_SCHEMA,
    "universal": UNIVERSAL_PAGE_JSON_SCHEMA
}

SYSTEM_PROMPTS = {
    "architectural": ARCHITECTURAL_SYSTEM_PROMPT,
    "civil": CIVIL_SYSTEM_PROMPT,
    "universal": UNIVERSAL_SYSTEM_PROMPT
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
