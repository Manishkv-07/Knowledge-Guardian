from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from app.config import settings
from app.api.documents import router as documents_router
from app.api.search import router as search_router
from app.api.chat import router as chat_router
from app.api.queries import router as queries_router
from app.api.connections import router as connections_router
from app.api.flashcards import router as flashcards_router
from app.api.memories import router as memories_router
from app.api.stats import router as stats_router
from app.api.exports import router as exports_router

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
app.include_router(chat_router, prefix="/api")
app.include_router(queries_router, prefix="/api")
app.include_router(connections_router, prefix="/api")
app.include_router(flashcards_router, prefix="/api")
app.include_router(memories_router, prefix="/api")
app.include_router(stats_router, prefix="/api")
app.include_router(exports_router, prefix="/api")

@app.on_event("startup")
async def seed_data_on_startup():
    """Seed sample data on server start to populate the frontend panels for demo purposes"""
    from app.services.memory_manager import memory_manager
    try:
        memory_manager.seed_demo_data_if_empty()
    except Exception as e:
        print(f"Failed to seed demo data on startup: {e}")

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
