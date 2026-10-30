from fastapi import APIRouter, HTTPException, Query
from typing import List, Dict, Any, Optional

from app.models.document import PatternMemoryCreate, PatternMemoryResponse
from app.services.memory_manager import memory_manager

router = APIRouter(prefix="/memories", tags=["memories"])


@router.get("/patterns", response_model=List[PatternMemoryResponse])
def get_pattern_memories(status: str = Query("active", description="Filter by status (active, dismissed)")):
    """Retrieve recurring research topic and workflow patterns."""
    patterns = memory_manager.get_pattern_memories(status=status)
    return patterns


@router.delete("/patterns/{pattern_id}")
def dismiss_pattern_memory(pattern_id: int):
    """Dismiss a cognitive pattern memory so it is no longer surfaced."""
    memory_manager.dismiss_pattern_memory(pattern_id)
    return {"detail": f"Pattern memory {pattern_id} dismissed successfully."}


@router.post("/patterns", response_model=Dict[str, Any])
def record_pattern_memory(pattern_in: PatternMemoryCreate):
    """Record or update a recurring research topic pattern."""
    memory_manager.record_pattern_memory(
        topic=pattern_in.topic,
        observation=pattern_in.observation,
        source_documents=pattern_in.source_documents
    )
    return {"status": "success", "detail": "Pattern memory recorded."}


@router.get("/context")
def get_episodic_context(query: str = Query(..., description="Query to match past episodic context"), limit: int = 3):
    """Retrieve query-relevant past episodic messages without polluting context with full history."""
    relevant_messages = memory_manager.get_relevant_episodic_context(query=query, limit=limit)
    return {"query": query, "relevant_episodic_memories": relevant_messages}
