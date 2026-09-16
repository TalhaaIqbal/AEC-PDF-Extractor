"""
Central Router
Aggregates all route modules and organizes them for the API documentation
"""
from fastapi import APIRouter

# Import individual route modules
import routes.health as health
import routes.upload as upload
import routes.processing as processing
import routes.status as status
import routes.results as results
import routes.download as download
import routes.sessions as sessions

# Create main router
api_router = APIRouter()

# Include route modules with tags for API documentation organization
api_router.include_router(health.router, tags=["Health"])
api_router.include_router(upload.router, tags=["Upload"])
api_router.include_router(processing.router, tags=["Processing"])
api_router.include_router(status.router, tags=["Status"])
api_router.include_router(results.router, tags=["Results"])
api_router.include_router(download.router, tags=["Download"])
api_router.include_router(sessions.router, tags=["Sessions"])
