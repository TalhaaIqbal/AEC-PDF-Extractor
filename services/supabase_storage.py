"""
Supabase Storage Service
Handles file upload and download operations with Supabase Storage
"""
import os
import httpx
from typing import Optional
from config.settings import SUPABASE_URL, SUPABASE_KEY, SUPABASE_BUCKET


class SupabaseStorage:
    """Supabase Storage client for file operations"""
    
    def __init__(self):
        self.url = SUPABASE_URL
        self.key = SUPABASE_KEY
        self.bucket = SUPABASE_BUCKET
        self.headers = {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json"
        }
    
    async def upload_file(self, file_path: str, storage_path: str) -> str:
        """
        Upload a file to Supabase Storage
        
        Args:
            file_path: Local path to the file
            storage_path: Path in Supabase storage (e.g., "uploads/session_id/filename.pdf")
        
        Returns:
            Public URL of the uploaded file
        """
        with open(file_path, "rb") as f:
            file_content = f.read()
        
        upload_url = f"{self.url}/storage/v1/object/{self.bucket}/{storage_path}"
        
        async with httpx.AsyncClient() as client:
            response = await client.put(
                upload_url,
                headers={
                    "apikey": self.key,
                    "Authorization": f"Bearer {self.key}",
                    "Content-Type": "application/pdf"
                },
                content=file_content
            )
            
            if response.status_code not in [200, 201]:
                raise Exception(f"Supabase upload failed: {response.text}")
        
        # Return public URL
        return f"{self.url}/storage/v1/object/public/{self.bucket}/{storage_path}"
    
    async def download_file(self, storage_path: str, local_path: str) -> None:
        """
        Download a file from Supabase Storage
        
        Args:
            storage_path: Path in Supabase storage
            local_path: Local path to save the file
        """
        download_url = f"{self.url}/storage/v1/object/public/{self.bucket}/{storage_path}"
        
        async with httpx.AsyncClient() as client:
            response = await client.get(download_url)
            
            if response.status_code != 200:
                raise Exception(f"Supabase download failed: {response.text}")
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        
        with open(local_path, "wb") as f:
            f.write(response.content)
    
    async def upload_bytes(self, file_content: bytes, storage_path: str, content_type: str = "application/pdf") -> str:
        """
        Upload bytes directly to Supabase Storage
        
        Args:
            file_content: File content as bytes
            storage_path: Path in Supabase storage
            content_type: MIME type of the file
        
        Returns:
            Public URL of the uploaded file
        """
        upload_url = f"{self.url}/storage/v1/object/{self.bucket}/{storage_path}"
        print(f"DEBUG bucket={self.bucket} url={upload_url}")
        
        async with httpx.AsyncClient() as client:
            response = await client.put(
                upload_url,
                headers={
                    "apikey": self.key,
                    "Authorization": f"Bearer {self.key}",
                    "Content-Type": content_type
                },
                content=file_content
            )
            
            print(f"DEBUG response status={response.status_code} text={response.text}")
            
            if response.status_code not in [200, 201]:
                raise Exception(f"Supabase upload failed: {response.text}")
        
        return f"{self.url}/storage/v1/object/public/{self.bucket}/{storage_path}"
    
    async def upload_stream(self, file_stream, storage_path: str, content_type: str = "application/pdf", chunk_size: int = 5 * 1024 * 1024) -> str:
        """
        Upload a file stream to Supabase Storage in chunks to avoid memory issues
        
        Args:
            file_stream: File-like object to read from
            storage_path: Path in Supabase storage
            content_type: MIME type of the file
            chunk_size: Size of chunks to upload (default 5MB)
        
        Returns:
            Public URL of the uploaded file
        """
        upload_url = f"{self.url}/storage/v1/object/{self.bucket}/{storage_path}"
        print(f"DEBUG Streaming upload to bucket={self.bucket} url={upload_url}")
        
        async def file_generator():
            while True:
                chunk = await file_stream.read(chunk_size)
                if not chunk:
                    break
                yield chunk
        
        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.put(
                upload_url,
                headers={
                    "apikey": self.key,
                    "Authorization": f"Bearer {self.key}",
                    "Content-Type": content_type
                },
                content=file_generator()
            )
            
            print(f"DEBUG response status={response.status_code}")
            
            if response.status_code not in [200, 201]:
                raise Exception(f"Supabase upload failed: {response.text}")
        
        return f"{self.url}/storage/v1/object/public/{self.bucket}/{storage_path}"
    
    async def delete_file(self, storage_path: str) -> None:
        """
        Delete a file from Supabase Storage
        
        Args:
            storage_path: Path in Supabase storage
        """
        delete_url = f"{self.url}/storage/v1/object/{self.bucket}/{storage_path}"
        
        async with httpx.AsyncClient() as client:
            response = await client.delete(
                delete_url,
                headers={
                    "apikey": self.key,
                    "Authorization": f"Bearer {self.key}"
                }
            )
            
            if response.status_code not in [200, 204]:
                raise Exception(f"Supabase delete failed: {response.text}")


# Global instance
supabase_storage = SupabaseStorage() if all([SUPABASE_URL, SUPABASE_KEY, SUPABASE_BUCKET]) else None