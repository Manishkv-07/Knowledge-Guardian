from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from pathlib import Path

from app.config import settings

# Resolve directory paths for database location
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DB_FILE_PATH = BASE_DIR / settings.MEMORY_DIR / "guardian.db"

# Create database engine
DATABASE_URL = f"sqlite:///{DB_FILE_PATH}"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# SQLAlchemy Models
class DocumentORM(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, index=True)
    filepath = Column(String)
    file_size = Column(Integer)
    upload_time = Column(DateTime, default=datetime.utcnow)
    status = Column(String, default="uploaded")  # uploaded, processing, indexed, failed
    chunk_count = Column(Integer, default=0)

    @property
    def upload_date(self):
        return self.upload_time

    memories = relationship("MemoryORM", back_populates="document", cascade="all, delete-orphan")

class MemoryORM(Base):
    __tablename__ = "memories"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"))
    insight_type = Column(String)  # summary, key_concept, custom
    content = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    document = relationship("DocumentORM", back_populates="memories")

# Create tables
Base.metadata.create_all(bind=engine)

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Pydantic Schemas - Required by User Specification

class DocumentUpload(BaseModel):
    """Schema representing file upload details."""
    filename: str
    content_type: str
    file_size: int

class DocumentChunk(BaseModel):
    """Schema representing text chunks indexed in the vector store."""
    id: str
    document_id: int
    text: str
    metadata: Dict[str, Any]

class DocumentResponse(BaseModel):
    """Schema for document representation returned by the API."""
    id: int
    filename: str
    upload_date: datetime  # maps to upload_time or upload_date in serialization
    chunk_count: int
    status: str

    class Config:
        from_attributes = True
        # Rename output fields so upload_time maps to upload_date automatically
        # to ensure compatibility with DocumentORM
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

# Extra schemas used in endpoints
class MemoryBase(BaseModel):
    insight_type: str
    content: str

class MemoryCreate(MemoryBase):
    document_id: int

class MemoryResponse(MemoryBase):
    id: int
    document_id: int
    created_at: datetime

    class Config:
        from_attributes = True

class QueryRequest(BaseModel):
    query: str
    top_k: Optional[int] = 20
    doc_types: Optional[List[str]] = None  # e.g. ["pdf", "txt", "md"]
    start_date: Optional[str] = None       # ISO 8601 or YYYY-MM-DD
    end_date: Optional[str] = None         # ISO 8601 or YYYY-MM-DD
    page: Optional[int] = 1
    page_size: Optional[int] = 5
    conversation_id: Optional[str] = None

class RelatedChunk(BaseModel):
    chunk_id: str
    chunk_index: int
    text: str
    similarity: float

class QueryResultItem(BaseModel):
    chunk_id: str
    document_id: str
    document_name: str
    chunk: str
    score: float
    similarity: float
    doc_type: str
    timestamp: Optional[str] = None
    chunk_index: Optional[int] = 0
    total_chunks: Optional[int] = 1
    related_chunks: Optional[List[RelatedChunk]] = []

class QueryResponse(BaseModel):
    chunk: str
    score: float
    document_name: str
    chunk_id: Optional[str] = None
    document_id: Optional[str] = None
    similarity: Optional[float] = None
    doc_type: Optional[str] = None
    related_chunks: Optional[List[RelatedChunk]] = []

class PaginatedQueryResponse(BaseModel):
    items: List[QueryResultItem]
    total: int
    page: int
    page_size: int
    total_pages: int

