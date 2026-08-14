from fastapi import APIRouter, Depends, HTTPException
from typing import List

from app.models.search import SearchQuery, SearchResult, SearchResponse
from app.services.vector_store import VectorStore, vector_store

router = APIRouter(tags=["search"])

def get_vector_store() -> VectorStore:
    """Dependency to retrieve the vector store instance."""
    return vector_store

@router.post("/search", response_model=SearchResponse)
async def search_knowledge(
    request: SearchQuery,
    store: VectorStore = Depends(get_vector_store)
):
    """Search the knowledge base and return relevant chunks with metadata."""
    # 1. Validate empty query
    if not request.query or not request.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    # 2. Check if documents/index exist
    if store.index is None or store.index.ntotal == 0:
        raise HTTPException(status_code=404, detail="No documents in knowledge base")

    # 3. Call search service
    results = store.search(query=request.query, k=request.limit)

    # 4. Format results
    search_results = []
    for r in results:
        search_results.append(
            SearchResult(
                chunk_id=r["chunk_id"],
                text=r["text"],
                document_id=r["document_id"],
                filename=r["filename"],
                similarity=r["similarity"],
                chunk_index=r["chunk_index"]
            )
        )

    # 5. Return JSON response
    return SearchResponse(
        query=request.query,
        results=search_results,
        total=len(search_results)
    )
