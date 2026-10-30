from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text, ForeignKey, Float
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
    processing_stage = Column(String, default="completed")  # uploaded, extracting, chunking, embedding, indexing, discovering, completed, failed
    error_detail = Column(String, nullable=True)
    chunk_count = Column(Integer, default=0)

    @property
    def upload_date(self):
        return self.upload_time

    memories = relationship("MemoryORM", back_populates="document", cascade="all, delete-orphan")
    source_connections = relationship(
        "DocumentConnectionORM",
        foreign_keys="DocumentConnectionORM.source_doc_id",
        back_populates="source_doc",
        cascade="all, delete-orphan"
    )
    target_connections = relationship(
        "DocumentConnectionORM",
        foreign_keys="DocumentConnectionORM.target_doc_id",
        back_populates="target_doc",
        cascade="all, delete-orphan"
    )
    flashcards = relationship("FlashcardORM", back_populates="document", cascade="all, delete-orphan")

class MemoryORM(Base):
    __tablename__ = "memories"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"))
    insight_type = Column(String)  # summary, key_concept, custom
    content = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    document = relationship("DocumentORM", back_populates="memories")

class DocumentConnectionORM(Base):
    __tablename__ = "document_connections"

    id = Column(Integer, primary_key=True, index=True)
    source_doc_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    target_doc_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    source_chunk_id = Column(String, index=True)
    target_chunk_id = Column(String, index=True)
    relationship_type = Column(String, index=True)  # SIMILAR, SUPPORTS, CONTRADICTS, EXTENDS, ANSWERS, RELATED
    explanation = Column(Text)
    evidence_source = Column(Text)
    evidence_target = Column(Text)
    source_filename = Column(String)
    target_filename = Column(String)
    source_page_number = Column(Integer, nullable=True)
    target_page_number = Column(Integer, nullable=True)
    confidence = Column(Float, default=0.8)  # Defined as combined retrieval similarity + evidence grounding
    status = Column(String, default="new", index=True)  # new, saved, dismissed
    created_at = Column(DateTime, default=datetime.utcnow)

    source_doc = relationship("DocumentORM", foreign_keys=[source_doc_id], back_populates="source_connections")
    target_doc = relationship("DocumentORM", foreign_keys=[target_doc_id], back_populates="target_connections")

class FlashcardORM(Base):
    __tablename__ = "flashcards"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    chunk_id = Column(String, nullable=True)
    question = Column(Text)
    answer = Column(Text)
    source_snippet = Column(Text, nullable=True)
    filename = Column(String)
    page_number = Column(Integer, nullable=True)
    status = Column(String, default="new")  # new, learning, review
    interval_days = Column(Integer, default=1)
    ease_factor = Column(Float, default=2.5)
    repetitions = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    next_review_date = Column(DateTime, default=datetime.utcnow, index=True)

    document = relationship("DocumentORM", back_populates="flashcards")

class PatternMemoryORM(Base):
    __tablename__ = "pattern_memories"

    id = Column(Integer, primary_key=True, index=True)
    topic = Column(String, index=True)
    frequency = Column(Integer, default=1)
    observation = Column(Text)
    source_documents = Column(Text, default="[]")  # JSON array of filenames
    status = Column(String, default="active")  # active, dismissed
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

# Create tables
Base.metadata.create_all(bind=engine)

def _ensure_document_columns():
    """Ensure newly added columns exist in SQLite database if upgraded."""
    try:
        import sqlite3
        conn = sqlite3.connect(DB_FILE_PATH)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(documents);")
        columns = [row[1] for row in cursor.fetchall()]
        if "processing_stage" not in columns:
            cursor.execute("ALTER TABLE documents ADD COLUMN processing_stage TEXT DEFAULT 'completed';")
        if "error_detail" not in columns:
            cursor.execute("ALTER TABLE documents ADD COLUMN error_detail TEXT DEFAULT NULL;")
        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning(f"Note on table migration: {e}")

_ensure_document_columns()

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

# Extra schemas used in endpoints
class MemoryBase(BaseModel):
    insight_type: str
    content: str

class MemoryCreate(MemoryBase):
    document_id: int
    custom_instruction: Optional[str] = None

class MemoryResponse(MemoryBase):
    id: int
    document_id: int
    created_at: datetime

    class Config:
        from_attributes = True

class DocumentResponse(BaseModel):
    """Schema for document representation returned by the API."""
    id: int
    filename: str
    upload_date: datetime  # maps to upload_time or upload_date in serialization
    chunk_count: int
    status: str
    processing_stage: Optional[str] = "completed"
    error_detail: Optional[str] = None
    memories: List[MemoryResponse] = []

    class Config:
        from_attributes = True
        # Rename output fields so upload_time maps to upload_date automatically
        # to ensure compatibility with DocumentORM
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

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
    page_number: Optional[int] = None
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
    page_number: Optional[int] = None
    doc_type: Optional[str] = None
    related_chunks: Optional[List[RelatedChunk]] = []

class PaginatedQueryResponse(BaseModel):
    items: List[QueryResultItem]
    total: int
    page: int
    page_size: int
    total_pages: int

# ==================== Phase 2 Intelligence Schemas ====================

# Cross-Document Connections
class ConnectionCreate(BaseModel):
    source_doc_id: int
    target_doc_id: int
    source_chunk_id: str
    target_chunk_id: str
    relationship_type: str  # SIMILAR, SUPPORTS, CONTRADICTS, EXTENDS, ANSWERS, RELATED
    explanation: str
    evidence_source: str
    evidence_target: str
    source_filename: str
    target_filename: str
    source_page_number: Optional[int] = None
    target_page_number: Optional[int] = None
    confidence: Optional[float] = 0.8
    status: Optional[str] = "new"

class ConnectionUpdate(BaseModel):
    status: Optional[str] = None  # new, saved, dismissed
    explanation: Optional[str] = None

class ConnectionResponse(BaseModel):
    id: int
    source_doc_id: int
    target_doc_id: int
    source_chunk_id: str
    target_chunk_id: str
    relationship_type: str
    explanation: str
    evidence_source: str
    evidence_target: str
    source_filename: str
    target_filename: str
    source_page_number: Optional[int] = None
    target_page_number: Optional[int] = None
    confidence: float
    status: str
    created_at: datetime

    class Config:
        from_attributes = True

class DiscoverConnectionsRequest(BaseModel):
    document_id: Optional[int] = None

# Source-Grounded Flashcards
class FlashcardCreate(BaseModel):
    document_id: int
    chunk_id: Optional[str] = None
    question: str
    answer: str
    source_snippet: Optional[str] = None
    filename: str
    page_number: Optional[int] = None

class FlashcardUpdate(BaseModel):
    question: Optional[str] = None
    answer: Optional[str] = None
    source_snippet: Optional[str] = None

class FlashcardReviewRequest(BaseModel):
    action: str  # again, hard, good, easy

class FlashcardResponse(BaseModel):
    id: int
    document_id: int
    chunk_id: Optional[str] = None
    question: str
    answer: str
    source_snippet: Optional[str] = None
    filename: str
    page_number: Optional[int] = None
    status: str
    interval_days: int
    ease_factor: float
    repetitions: int
    created_at: datetime
    next_review_date: datetime

    class Config:
        from_attributes = True

class GenerateFlashcardsRequest(BaseModel):
    document_id: int
    chunk_ids: Optional[List[str]] = None
    count: Optional[int] = 3

# Pattern Memories
class PatternMemoryCreate(BaseModel):
    topic: str
    observation: str
    source_documents: Optional[List[str]] = []

class PatternMemoryResponse(BaseModel):
    id: int
    topic: str
    frequency: int
    observation: str
    source_documents: str
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

