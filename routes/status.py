"""
Status Routes
Routes for checking processing status and progress
"""
from fastapi import APIRouter, HTTPException

from config.settings import sessions

router = APIRouter()


@router.get("/status/{session_id}")
async def get_status(session_id: str):
    """Get processing status for a session"""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session = sessions[session_id]
    
    return {
        "session_id": session_id,
        "status": session["status"],
        "progress": session["progress"],
        "filename": session["filename"],
        "error": session.get("error"),
        "has_result": session["result"] is not None
    }
