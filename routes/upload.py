"""
Upload Routes
Routes for PDF file upload and immediate processing
"""
from fastapi import APIRouter, UploadFile, File, HTTPException
import shutil
import uuid
import tempfile
from pathlib import Path
from aec_processor import process_pdf

from config.settings import UPLOAD_DIR, OUTPUT_DIR

router = APIRouter()


@router.post("/upload-pdf")
async def upload_pdf(file: UploadFile = File(...)):
    """Upload a PDF file and process it immediately"""
    try:
        # Validate file type
        if not file.filename.endswith('.pdf'):
            raise HTTPException(status_code=400, detail="Only PDF files are allowed")
        
        # Generate unique session ID
        session_id = str(uuid.uuid4())
        
        # Use temp directory for processing (works in both local and serverless)
        temp_dir = Path(tempfile.gettempdir()) / f"aec_{session_id}"
        temp_dir.mkdir(exist_ok=True, parents=True)
        
        # Save uploaded file to temp directory
        file_path = temp_dir / file.filename
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Process PDF immediately with all AI steps
        result = await process_pdf(
            str(file_path),
            str(temp_dir),
            progress_callback=lambda progress: None  # No progress updates needed
        )
        
        # Read the markdown report
        report_file = temp_dir / "aec_human_readable_report.md"
        markdown_report = ""
        if report_file.exists():
            with open(report_file, "r", encoding="utf-8") as f:
                markdown_report = f.read()
        
        # Clean up temp files
        try:
            shutil.rmtree(temp_dir)
        except:
            pass  # Cleanup failed but processing succeeded
        
        return {
            "session_id": session_id,
            "filename": file.filename,
            "status": "completed",
            "result": result,
            "markdown": markdown_report
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")
