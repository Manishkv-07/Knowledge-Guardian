from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from app.config import settings
from app.api.documents import router as documents_router
from app.api.search import router as search_router

app = FastAPI(
    title="Personal Knowledge Guardian API",
    description="Proactive AI memory system backend for researchers and knowledge workers.",
    version="1.0.0"
)

# CORS middleware configured for the React/Vite frontend (running on port 3000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers for document upload and ingestion endpoints
app.include_router(documents_router, prefix="/api")
app.include_router(search_router, prefix="/api")

@app.get("/")
def read_root():
    """Root endpoint returning basic health status."""
    return {"status": "healthy"}

@app.get("/health")
@app.get("/api/health")
def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}

if __name__ == "__main__":
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=True)
