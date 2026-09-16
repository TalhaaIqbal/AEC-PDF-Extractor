"""
Health Check Routes
Routes for API health monitoring and basic service information
"""
from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def root():
    return {"message": "AEC Drawing Intelligence Pipeline API", "status": "running"}


@router.get("/health")
async def health_check():
    return {"status": "healthy"}
