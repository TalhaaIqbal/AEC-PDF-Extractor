from fastapi import FastAPI
from config.settings import configure_cors
from routes.router import api_router

# Create FastAPI app
app = FastAPI(title="AEC Drawing Intelligence Pipeline API")

# Configure CORS
configure_cors(app)

# Register central router with all organized routes
app.include_router(api_router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
