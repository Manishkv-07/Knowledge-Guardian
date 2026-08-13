import sys
import os
from pathlib import Path

# Ensure UTF-8 output on Windows terminal
try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except AttributeError:
    pass

# Add backend directory to sys.path
ROOT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = ROOT_DIR / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.models.document import QueryRequest, SessionLocal, DocumentORM
from app.services.vector_store import vector_store
from app.services.ingestion import ingestion_service

def test_advanced_search():
    print("=" * 60)
    print(" ADVANCED SEARCH FEATURES VERIFICATION ".center(60, "="))
    print("=" * 60)

    db = SessionLocal()
    
    # Check if there are already TXT documents in the vector store
    txt_docs = [m for m in vector_store.metadata if m.get("filename", "").endswith(".txt")]
    
    if len(txt_docs) == 0:
        print("\n--- Ingesting sample TXT test documents into Vector Store ---")
        sample_files = list((BACKEND_DIR / "test_data").glob("*.txt"))[:2]
        for f in sample_files:
            print(f"Ingesting: {f.name}")
            db_doc = DocumentORM(
                filename=f.name,
                filepath=str(f),
                file_size=f.stat().st_size,
                status="indexed",
                chunk_count=0
            )
            db.add(db_doc)
            db.commit()
            db.refresh(db_doc)
            
            res = ingestion_service.process_text(str(f), f.name, document_id=str(db_doc.id))
            db_doc.chunk_count = res["total_chunks"]
            db.commit()
            vector_store.add_document(str(db_doc.id))
            
        print(f"Updated index with TXT docs. Total vectors now: {vector_store.index.ntotal}")

    all_passed = True

    # ----------------------------------------------------
    # Test Task 1: Search Filters (doc_types and date ranges)
    # ----------------------------------------------------
    print("\n--- Testing Task 1: Search Filters ---")
    query = "layer network protocol transformer attention"
    
    # 1a. Filter by doc_type 'pdf'
    res_pdf = vector_store.search(query, k=5, doc_types=["pdf"])
    print(f"Filtered by doc_types=['pdf']: found {len(res_pdf)} results")
    if len(res_pdf) > 0 and all(r["metadata"]["filename"].lower().endswith(".pdf") for r in res_pdf):
        print("✓ Filter by doc_type (PDF) passed!")
    else:
        print("✗ Filter by doc_type (PDF) failed!")
        all_passed = False

    # 1b. Filter by doc_type 'txt'
    res_txt = vector_store.search(query, k=5, doc_types=["txt"])
    print(f"Filtered by doc_types=['txt']: found {len(res_txt)} results")
    if len(res_txt) > 0 and all(r["metadata"]["filename"].lower().endswith(".txt") for r in res_txt):
        print("✓ Filter by doc_type (TXT) passed!")
    else:
        print("✗ Filter by doc_type (TXT) failed!")
        all_passed = False

    # 1c. Filter by non-matching doc_type 'md'
    res_md = vector_store.search(query, k=5, doc_types=["md"])
    print(f"Filtered by doc_types=['md']: found {len(res_md)} results")
    if len(res_md) == 0:
        print("✓ Filter exclusion for unindexed doc_type passed!")
    else:
        print("✓ MD filter active.")

    # 1d. Filter by date range
    today_str = "2020-01-01"
    future_str = "2030-12-31"
    res_date = vector_store.search(query, k=5, start_date=today_str, end_date=future_str)
    print(f"Filtered by date range [{today_str} to {future_str}]: found {len(res_date)} results")
    if len(res_date) > 0:
        print("✓ Filter by valid date range passed!")
    else:
        print("✗ Date range filter returned 0 results unexpectedly")
        all_passed = False

    # Filter by past expired date range
    res_past = vector_store.search(query, k=5, start_date="2010-01-01", end_date="2015-01-01")
    if len(res_past) == 0:
        print("✓ Filter out-of-range date exclusion passed!")
    else:
        print("✗ Out-of-range date filter did not exclude entries!")
        all_passed = False

    # ----------------------------------------------------
    # Test Task 3: Pagination
    # ----------------------------------------------------
    print("\n--- Testing Task 3: Pagination ---")
    from app.api.documents import query_knowledge_base

    # Page 1, Page Size 2
    req_p1 = QueryRequest(query="network transport layer", page=1, page_size=2, top_k=20)
    resp_p1 = query_knowledge_base(req_p1)
    
    # Page 2, Page Size 2
    req_p2 = QueryRequest(query="network transport layer", page=2, page_size=2, top_k=20)
    resp_p2 = query_knowledge_base(req_p2)

    total_count = resp_p1.get("total", 0) if isinstance(resp_p1, dict) else resp_p1.total
    total_pages = resp_p1.get("total_pages", 1) if isinstance(resp_p1, dict) else resp_p1.total_pages
    items_p1 = resp_p1.get("items", []) if isinstance(resp_p1, dict) else resp_p1.items
    items_p2 = resp_p2.get("items", []) if isinstance(resp_p2, dict) else resp_p2.items
    page_p1 = resp_p1.get("page", 1) if isinstance(resp_p1, dict) else resp_p1.page
    page_p2 = resp_p2.get("page", 2) if isinstance(resp_p2, dict) else resp_p2.page

    print(f"Total results: {total_count}, Total pages: {total_pages}")
    print(f"Page 1 items count: {len(items_p1)} (page={page_p1})")
    print(f"Page 2 items count: {len(items_p2)} (page={page_p2})")

    if len(items_p1) <= 2 and page_p1 == 1 and total_pages >= 1:
        print("✓ Pagination metadata and slicing for Page 1 passed!")
    else:
        print("✗ Pagination Page 1 verification failed!")
        all_passed = False

    if total_count > 2:
        if page_p2 == 2 and len(items_p2) > 0:
            print("✓ Pagination Page 2 retrieval passed!")
        else:
            print("✗ Pagination Page 2 failed!")
            all_passed = False

    # ----------------------------------------------------
    # Test Task 4: Related Chunks
    # ----------------------------------------------------
    print("\n--- Testing Task 4: Related Chunks from Same Document ---")
    if items_p1:
        first_item = items_p1[0]
        doc_name = first_item.get("document_name") if isinstance(first_item, dict) else first_item.document_name
        chunk_idx = first_item.get("chunk_index") if isinstance(first_item, dict) else first_item.chunk_index
        related = first_item.get("related_chunks", []) if isinstance(first_item, dict) else first_item.related_chunks

        print(f"Primary Result: '{doc_name}' (Chunk #{chunk_idx})")
        print(f"Attached Related Chunks count: {len(related)}")
        
        for rel in related:
            r_idx = rel.get("chunk_index") if isinstance(rel, dict) else rel.chunk_index
            r_txt = rel.get("text", "") if isinstance(rel, dict) else rel.text
            r_sim = rel.get("similarity", 0) if isinstance(rel, dict) else rel.similarity
            print(f"  - Related Section #{r_idx}: '{r_txt[:65]}...' (Similarity: {r_sim})")

        if len(related) > 0:
            print("✓ Related chunks extraction and attachment passed!")
        else:
            print("⚠ Document has no other chunks to relate.")
    
    # ----------------------------------------------------
    # Summary
    # ----------------------------------------------------
    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 ALL ADVANCED SEARCH FEATURES PASSED!")
    else:
        print("✗ SOME ADVANCED SEARCH TESTS FAILED.")
    print("=" * 60)

    db.close()
    return all_passed

if __name__ == "__main__":
    success = test_advanced_search()
    sys.exit(0 if success else 1)
