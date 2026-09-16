"""
Processing Routes
Routes for initiating and managing PDF processing tasks
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks

from config.settings import sessions
from services.background_tasks import process_pdf_background

router = APIRouter()


@router.post("/process/{session_id}")
async def process_pdf_endpoint(session_id: str, background_tasks: BackgroundTasks):
    """Start processing the uploaded PDF"""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session = sessions[session_id]
    
    if session["status"] in ["processing", "completed"]:
        return {"session_id": session_id, "status": session["status"]}
    
    # Update session status
    session["status"] = "processing"
    
    # Add background task for processing
    background_tasks.add_task(process_pdf_background, session_id, sessions)
    
    return {"session_id": session_id, "status": "processing"}
