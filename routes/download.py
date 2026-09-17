"""
Download Routes
Routes for downloading processed files in various formats
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
import shutil
from pathlib import Path

from config.settings import OUTPUT_DIR, sessions

router = APIRouter()


@router.get("/download/{session_id}/{file_type}")
async def download_file(session_id: str, file_type: str):
    """Download processed files (json, markdown, or zip)"""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session = sessions[session_id]
    output_dir = Path(session["output_dir"])
    
    if file_type == "json":
        file_path = output_dir / "final_aec_model.json"
    elif file_type == "markdown":
        file_path = output_dir / "aec_human_readable_report.md"
    elif file_type == "zip":
        # Create zip file if it doesn't exist
        zip_path = output_dir.parent / f"{session_id}_results.zip"
        if not zip_path.exists():
            shutil.make_archive(str(zip_path.with_suffix('')), 'zip', output_dir)
        file_path = zip_path
    else:
        raise HTTPException(status_code=400, detail="Invalid file type")
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(
        file_path,
        media_type='application/octet-stream',
        filename=file_path.name
    )
