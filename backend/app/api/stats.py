from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime
from typing import Dict, Any, List

from app.models.document import (
    get_db, DocumentORM, DocumentConnectionORM, FlashcardORM, MemoryORM
)
from app.services.vector_store import vector_store
from app.services.memory_manager import memory_manager
from app.services.llm_client import llm_client
from app.config import settings

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/")
def get_system_metrics(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Computes and returns real, observable metrics from SQLite, FAISS, BM25, and runtime configuration."""
    now = datetime.utcnow()

    # 1. Document Metrics
    total_docs = db.query(DocumentORM).count()
    indexed_docs = db.query(DocumentORM).filter(DocumentORM.status == "indexed").count()
    failed_docs = db.query(DocumentORM).filter(DocumentORM.status == "failed").count()
    processing_docs = db.query(DocumentORM).filter(DocumentORM.status == "processing").count()
    
    total_chunks_db = db.query(func.coalesce(func.sum(DocumentORM.chunk_count), 0)).scalar() or 0

    # 2. Vector & Lexical Index Metrics
    faiss_vector_count = vector_store.index.ntotal if vector_store.index is not None else 0
    faiss_metadata_count = len(vector_store.metadata)
    bm25_count = vector_store.bm25.corpus_size if vector_store.bm25 is not None else 0

    # Real Index Consistency Check:
    # Consistency requires that FAISS vector count matches metadata records count
    is_consistent = (faiss_vector_count == faiss_metadata_count)
    if is_consistent and total_chunks_db > 0:
        # If there are indexed documents, their chunk sum should also match FAISS count
        is_consistent = (faiss_vector_count == total_chunks_db)

    # 3. Connection Metrics
    total_conns = db.query(DocumentConnectionORM).count()
    saved_conns = db.query(DocumentConnectionORM).filter(DocumentConnectionORM.status == "saved").count()
    dismissed_conns = db.query(DocumentConnectionORM).filter(DocumentConnectionORM.status == "dismissed").count()
    new_conns = db.query(DocumentConnectionORM).filter(DocumentConnectionORM.status == "new").count()

    # 4. Flashcard Metrics
    total_cards = db.query(FlashcardORM).count()
    due_cards = db.query(FlashcardORM).filter(FlashcardORM.next_review_date <= now).count()

    # 5. Persistent Memory Metrics
    pattern_memories = memory_manager.get_pattern_memories(status="active")
    stored_memories_count = db.query(MemoryORM).count()

    # 6. Groq Connectivity Status (Zero Secret Exposure)
    is_groq_ready = llm_client.is_groq_configured()
    masked_key = None
    if is_groq_ready:
        api_key = settings.GROQ_API_KEY or ""
        if len(api_key) > 8:
            masked_key = f"{api_key[:4]}...{api_key[-4:]}"
        else:
            masked_key = "configured (masked)"

    # 7. Recent Ingestion Failures
    recent_failed_docs = db.query(DocumentORM).filter(DocumentORM.status == "failed").order_by(DocumentORM.upload_time.desc()).limit(5).all()
    failed_details = [
        {
            "id": d.id,
            "filename": d.filename,
            "error_detail": getattr(d, "error_detail", None) or "Ingestion error",
            "upload_time": d.upload_time.isoformat() if d.upload_time else None
        }
        for d in recent_failed_docs
    ]

    return {
        "documents": {
            "total": total_docs,
            "indexed": indexed_docs,
            "failed": failed_docs,
            "processing": processing_docs,
            "total_chunks": total_chunks_db
        },
        "vector_store": {
            "engine": "FAISS IndexFlatL2 (384-d)",
            "vector_count": faiss_vector_count,
            "metadata_count": faiss_metadata_count,
            "bm25_corpus_size": bm25_count,
            "is_consistent": is_consistent,
            "consistency_status": "consistent" if is_consistent else "desynchronized"
        },
        "intelligence": {
            "total_connections": total_conns,
            "saved_connections": saved_conns,
            "new_connections": new_conns,
            "dismissed_connections": dismissed_conns,
            "total_flashcards": total_cards,
            "due_flashcards": due_cards,
            "active_pattern_memories": len(pattern_memories),
            "stored_fact_memories": stored_memories_count
        },
        "llm_provider": {
            "provider": "GroqCloud",
            "model": settings.GROQ_MODEL,
            "is_configured": is_groq_ready,
            "masked_key": masked_key,
            "temperature": settings.GROQ_TEMPERATURE,
            "max_tokens": settings.GROQ_MAX_TOKENS
        },
        "recent_failures": failed_details,
        "timestamp": now.isoformat()
    }
