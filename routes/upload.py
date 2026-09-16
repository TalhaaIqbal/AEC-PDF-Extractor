"""
Upload Routes
Routes for PDF file upload and session initialization
"""
from fastapi import APIRouter, UploadFile, File, HTTPException
import shutil
import uuid
from pathlib import Path

from config.settings import UPLOAD_DIR, OUTPUT_DIR, sessions

router = APIRouter()


@router.post("/upload-pdf")
async def upload_pdf(file: UploadFile = File(...)):
    """Upload a PDF file and start processing"""
    try:
        # Validate file type
        if not file.filename.endswith('.pdf'):
            raise HTTPException(status_code=400, detail="Only PDF files are allowed")
        
        # Generate unique session ID
        session_id = str(uuid.uuid4())
        
        # Create session directory
        session_upload_dir = UPLOAD_DIR / session_id
        session_output_dir = OUTPUT_DIR / session_id
        session_upload_dir.mkdir(exist_ok=True)
        session_output_dir.mkdir(exist_ok=True)
        
        # Save uploaded file
        file_path = session_upload_dir / file.filename
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Initialize session state
        sessions[session_id] = {
            "status": "uploaded",
            "filename": file.filename,
            "file_path": str(file_path),
            "output_dir": str(session_output_dir),
            "progress": 0,
            "result": None,
            "error": None
        }
        
        return {
            "session_id": session_id,
            "filename": file.filename,
            "status": "uploaded"
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")
