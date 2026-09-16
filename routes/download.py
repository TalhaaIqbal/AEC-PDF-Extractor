"""
Download Routes
Routes for downloading processed files in various formats
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, RedirectResponse
import shutil
from pathlib import Path
import tempfile
import os

from config.settings import OUTPUT_DIR, sessions, SUPABASE_URL, SUPABASE_BUCKET
from services.supabase_storage import supabase_storage

router = APIRouter()


@router.get("/download/{session_id}/{file_type}")
async def download_file(session_id: str, file_type: str):
    """Download processed files (json, markdown, or zip)"""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session = sessions[session_id]
    
    # Check if using Supabase storage
    if session.get("use_supabase") and supabase_storage:
        return await download_from_supabase(session_id, file_type, session)
    
    # Use local file storage
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


async def download_from_supabase(session_id: str, file_type: str, session: dict):
    """Download files from Supabase storage"""
    if file_type == "json":
        storage_path = f"results/{session_id}/final_aec_model.json"
        filename = "final_aec_model.json"
    elif file_type == "markdown":
        storage_path = f"results/{session_id}/aec_human_readable_report.md"
        filename = "aec_human_readable_report.md"
    elif file_type == "zip":
        # For zip, we'd need to create it on the fly or pre-upload it
        # For now, redirect to JSON as fallback
        storage_path = f"results/{session_id}/final_aec_model.json"
        filename = "final_aec_model.json"
    else:
        raise HTTPException(status_code=400, detail="Invalid file type")
    
    # Redirect to Supabase public URL
    public_url = f"{SUPABASE_URL}/storage/v1/object/public/{SUPABASE_BUCKET}/{storage_path}"
    return RedirectResponse(url=public_url)
