"""
Results Routes
Routes for retrieving processing results and extracted data
"""
from fastapi import APIRouter, HTTPException

from config.settings import sessions

router = APIRouter()


@router.get("/result/{session_id}")
async def get_result(session_id: str):
    """Get the processing result for a session"""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session = sessions[session_id]
    
    if session["status"] != "completed":
        raise HTTPException(status_code=400, detail="Processing not completed")
    
    return session["result"]
