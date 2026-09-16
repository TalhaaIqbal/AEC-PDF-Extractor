"""
Upload Routes
Routes for PDF file upload and synchronous processing
"""
from fastapi import APIRouter, UploadFile, File, HTTPException
import shutil
import uuid
from pathlib import Path
import tempfile
import os

from config.settings import UPLOAD_DIR, OUTPUT_DIR, sessions, USE_SUPABASE
from aec_processor import process_pdf
from services.supabase_storage import supabase_storage

router = APIRouter()


@router.post("/upload-pdf")
async def upload_pdf(file: UploadFile = File(...)):
    """Upload a PDF file and process it synchronously"""
    try:
        print(f"DEBUG: Starting upload for {file.filename}")
        
        # Validate file type
        if not file.filename.endswith('.pdf'):
            raise HTTPException(status_code=400, detail="Only PDF files are allowed")
        
        # Generate unique session ID
        session_id = str(uuid.uuid4())
        print(f"DEBUG: Generated session_id {session_id}")
        
        # Determine storage approach
        storage_path = None
        if USE_SUPABASE and supabase_storage:
            print(f"DEBUG: Using Supabase storage with streaming")
            # Create temporary local directory for processing
            temp_dir = Path(tempfile.mkdtemp())
            session_upload_dir = temp_dir / "uploads" / session_id
            session_output_dir = temp_dir / "outputs" / session_id
            session_upload_dir.mkdir(parents=True, exist_ok=True)
            session_output_dir.mkdir(parents=True, exist_ok=True)
            
            # Save file locally for processing (stream to disk to avoid memory issues)
            file_path = session_upload_dir / file.filename
            with open(file_path, "wb") as buffer:
                # Stream in chunks to avoid loading entire file into memory
                chunk_size = 1024 * 1024  # 1MB chunks
                while chunk := await file.read(chunk_size):
                    buffer.write(chunk)
            
            # Now upload to Supabase from the local file
            storage_path = f"uploads/{session_id}/{file.filename}"
            await supabase_storage.upload_file(str(file_path), storage_path)
        else:
            print(f"DEBUG: Using local storage")
            # Use local file storage
            session_upload_dir = UPLOAD_DIR / session_id
            session_output_dir = OUTPUT_DIR / session_id
            try:
                session_upload_dir.mkdir(exist_ok=True, parents=True)
                session_output_dir.mkdir(exist_ok=True, parents=True)
            except OSError as e:
                raise HTTPException(status_code=500, detail=f"Cannot create directories: {str(e)}")
            
            # Save uploaded file (stream to disk to avoid memory issues)
            file_path = session_upload_dir / file.filename
            with open(file_path, "wb") as buffer:
                # Stream in chunks to avoid loading entire file into memory
                chunk_size = 1024 * 1024  # 1MB chunks
                while chunk := await file.read(chunk_size):
                    buffer.write(chunk)
        
        print(f"DEBUG: File saved to {file_path}")
        
        # Initialize session state
        sessions[session_id] = {
            "status": "processing",
            "filename": file.filename,
            "file_path": str(file_path),
            "output_dir": str(session_output_dir),
            "progress": 0,
            "result": None,
            "error": None,
            "use_supabase": USE_SUPABASE,
            "storage_path": storage_path if USE_SUPABASE else None
        }
        
        # Process PDF synchronously
        try:
            print(f"DEBUG: Starting PDF processing")
            result = await process_pdf(
                str(file_path),
                str(session_output_dir),
                progress_callback=lambda progress: update_progress(session_id, progress)
            )
            
            print(f"DEBUG: PDF processing completed")
            sessions[session_id]["status"] = "completed"
            sessions[session_id]["result"] = result
            sessions[session_id]["progress"] = 100
            
            # If using Supabase, upload results
            if USE_SUPABASE and supabase_storage:
                print(f"DEBUG: Uploading results to Supabase")
                await upload_results_to_supabase(session_id, session_output_dir, file.filename)
            
        except Exception as e:
            print(f"DEBUG: Processing error: {str(e)}")
            import traceback
            traceback.print_exc()
            sessions[session_id]["status"] = "error"
            sessions[session_id]["error"] = str(e)
            raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")
        
        print(f"DEBUG: Upload completed successfully")
        return {
            "session_id": session_id,
            "filename": file.filename,
            "status": "completed",
            "result": result
        }
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"DEBUG: Upload error: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


async def upload_results_to_supabase(session_id: str, output_dir: Path, filename: str):
    """Upload processing results to Supabase storage"""
    if not supabase_storage:
        return
    
    try:
        # Upload final JSON result
        final_json_path = output_dir / "final_aec_model.json"
        if final_json_path.exists():
            json_storage_path = f"results/{session_id}/final_aec_model.json"
            await supabase_storage.upload_file(str(final_json_path), json_storage_path)
        
        # Upload markdown report
        markdown_path = output_dir / "aec_human_readable_report.md"
        if markdown_path.exists():
            md_storage_path = f"results/{session_id}/aec_human_readable_report.md"
            await supabase_storage.upload_file(str(markdown_path), md_storage_path)
        
        # Upload individual page results
        for page_file in output_dir.glob("page_*.json"):
            page_storage_path = f"results/{session_id}/{page_file.name}"
            await supabase_storage.upload_file(str(page_file), page_storage_path)
        
    except Exception as e:
        print(f"Failed to upload results to Supabase: {e}")


def update_progress(session_id: str, progress: int) -> None:
    """Update processing progress"""
    if session_id in sessions:
        sessions[session_id]["progress"] = progress
