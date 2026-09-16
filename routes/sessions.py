"""
Session Management Routes
Routes for session deletion and cleanup
"""
from fastapi import APIRouter, HTTPException
from pathlib import Path

from config.settings import UPLOAD_DIR, OUTPUT_DIR, sessions
from utils.file_helpers import cleanup_session

router = APIRouter()


@router.delete("/session/{session_id}")
async def delete_session(session_id: str):
    """Delete a session and clean up files"""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Clean up files
    cleanup_session(session_id, UPLOAD_DIR, OUTPUT_DIR)
    
    # Remove from sessions
    del sessions[session_id]
    
    return {"message": "Session deleted successfully"}
