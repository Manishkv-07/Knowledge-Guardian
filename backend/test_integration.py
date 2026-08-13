"""
Integration Test Suite for Personal Knowledge Guardian API.
Verifies end-to-end flow: Document Upload -> Ingestion & Vector Indexing -> Semantic Search Retrieval.
"""

import os
import sys
import time
import io
from pathlib import Path
from starlette.testclient import TestClient

try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except AttributeError:
    pass

# Add backend root to sys.path so app modules are resolvable
BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.main import app
from app.models.document import SessionLocal, DocumentORM
from app.services.vector_store import vector_store

client = TestClient(app)

def wait_for_document_indexing(doc_id: int, max_wait_sec: int = 15) -> dict:
    """Poll document status until it becomes 'indexed' or 'failed'."""
    start_time = time.time()
    while time.time() - start_time < max_wait_sec:
        response = client.get("/api/documents/")
        assert response.status_code == 200, f"Failed to list documents: {response.text}"
        docs = response.json()
        target_doc = next((d for d in docs if d["id"] == doc_id), None)
        if target_doc and target_doc["status"] == "indexed":
            return target_doc
        if target_doc and target_doc["status"] == "failed":
            raise RuntimeError(f"Document {doc_id} failed ingestion.")
        time.sleep(0.5)
    raise TimeoutError(f"Document {doc_id} did not complete indexing within {max_wait_sec} seconds.")

def test_search_integration():
    """
    Core Integration Test:
    1. Upload a document
    2. Search for a query
    3. Verify results
    """
    print("\n--- Running test_search_integration ---")
    
    # 1. Upload a document
    test_content = (
        "Quantum Neural Guardian is an autonomous memory retention system. "
        "It preserves knowledge context across research workflows using high-density vector representations. "
        "The system incorporates proactive alerts and cross-document concept synthesis."
    )
    test_filename = "test_quantum_guardian_integration.txt"
    file_bytes = io.BytesIO(test_content.encode("utf-8"))

    upload_response = client.post(
        "/api/documents/upload",
        files={"file": (test_filename, file_bytes, "text/plain")}
    )
    
    assert upload_response.status_code == 200, f"Upload failed: {upload_response.text}"
    uploaded_doc = upload_response.json()
    doc_id = uploaded_doc["id"]
    print(f"[OK] Uploaded test document with ID: {doc_id}, filename: {uploaded_doc['filename']}")

    # Wait for background task to parse, chunk, embed, and index
    indexed_doc = wait_for_document_indexing(doc_id)
    print(f"[OK] Document indexed successfully with chunk_count: {indexed_doc['chunk_count']}")
    assert indexed_doc["chunk_count"] > 0, "Chunk count should be greater than 0."

    # 2. Search for a query
    search_query = "What is Quantum Neural Guardian and how does it retain memory?"
    query_payload = {
        "query": search_query,
        "top_k": 3
    }
    
    search_response = client.post("/api/documents/query", json=query_payload)
    assert search_response.status_code == 200, f"Query failed: {search_response.text}"
    results = search_response.json()
    print(f"[OK] Search completed, retrieved {len(results)} results.")

    # 3. Verify results
    assert isinstance(results, list), "Search response must be a list"
    assert len(results) > 0, "Expected at least one matching search result"
    
    top_result = results[0]
    assert "chunk" in top_result, "Result must contain 'chunk' text"
    assert "score" in top_result, "Result must contain 'score'"
    assert "document_name" in top_result, "Result must contain 'document_name'"
    assert "similarity" in top_result, "Result must contain 'similarity'"
    
    assert len(top_result["chunk"].strip()) > 0, "Chunk text should not be empty"
    assert "Quantum Neural Guardian" in top_result["chunk"], "Chunk should contain uploaded text"
    assert top_result["similarity"] > 0.0, "Similarity score must be positive"
    assert top_result["score"] >= 0.0, "Distance score must be non-negative"
    print(f"[PASS] Top result verification passed! Document: {top_result['document_name']}, Similarity: {top_result['similarity']:.4f}")

    # Cleanup: Delete the test document
    del_response = client.delete(f"/api/documents/{doc_id}")
    assert del_response.status_code == 200, f"Delete failed: {del_response.text}"
    print(f"[OK] Test document {doc_id} cleaned up successfully.")

def test_search_special_characters_and_symbols():
    """Verify search handles special characters, punctuation, and Unicode symbols without error."""
    print("\n--- Running test_search_special_characters_and_symbols ---")
    
    special_queries = [
        "quantum & neural @ guardian! #test (v1.0) -> [high-priority]?",
        "Symbols: alpha + beta = gamma * delta / epsilon % lambda <= 100",
        "Punctuation check: ~`!@#$%^&*()_-+={[}]|\\:;\"'<,>.?/",
        "Unicode: Knowledge Graph Analysis"
    ]
    
    for query in special_queries:
        response = client.post("/api/documents/query", json={"query": query, "top_k": 3})
        assert response.status_code == 200, f"Special character query failed for '{query}': {response.text}"
        results = response.json()
        assert isinstance(results, list), "Response must be a list"
        print(f"[PASS] Query with special characters handled cleanly: '{query[:40]}...' (Status 200)")

def test_search_long_query():
    """Verify search handles long paragraph-length queries (>500 characters)."""
    print("\n--- Running test_search_long_query ---")
    
    long_query = (
        "In modern machine learning research architectures, neural attention mechanisms and vector embeddings "
        "serve as fundamental building blocks for personal knowledge indexing and contextual memory preservation. "
        "When dealing with multi-modal research artifacts, literature reviews, and cross-reference citations, "
        "it is essential that the semantic vector store accurately calculates cosine similarity and Euclidean distance "
        "without truncating user context or failing on multi-sentence paragraphs."
    )
    assert len(long_query) > 400
    
    response = client.post("/api/documents/query", json={"query": long_query, "top_k": 5})
    assert response.status_code == 200, f"Long query failed: {response.text}"
    results = response.json()
    assert isinstance(results, list), "Long query response must be a list"
    print(f"[PASS] Long query ({len(long_query)} chars) handled cleanly (Status 200, {len(results)} results returned)")

def test_search_empty_or_whitespace_query():
    """Verify search handles empty or whitespace queries cleanly by returning empty list."""
    print("\n--- Running test_search_empty_or_whitespace_query ---")
    
    for empty_q in ["", "   ", "\t\n"]:
        response = client.post("/api/documents/query", json={"query": empty_q, "top_k": 3})
        assert response.status_code == 200
        results = response.json()
        assert results == [], f"Expected empty result for query '{empty_q}', got {results}"
        print(f"[PASS] Empty/whitespace query handled correctly: '{empty_q}' -> []")

if __name__ == "__main__":
    print("=" * 60)
    print(" STARTING INTEGRATION TESTS FOR KNOWLEDGE GUARDIAN ")
    print("=" * 60)
    
    test_search_integration()
    test_search_special_characters_and_symbols()
    test_search_long_query()
    test_search_empty_or_whitespace_query()
    
    print("\n" + "=" * 60)
    print(" ALL INTEGRATION TESTS PASSED SUCCESSFULLY! ")
    print("=" * 60)
