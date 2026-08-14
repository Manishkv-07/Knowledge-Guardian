from pydantic import BaseModel
from typing import List

class SearchQuery(BaseModel):
    query: str
    limit: int = 5

class SearchResult(BaseModel):
    chunk_id: str
    text: str
    document_id: str
    filename: str
    similarity: float
    chunk_index: int

class SearchResponse(BaseModel):
    query: str
    results: List[SearchResult]
    total: int
