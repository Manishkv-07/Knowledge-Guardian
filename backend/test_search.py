import os
import sys
from pathlib import Path

# Add backend directory to sys.path
BACKEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_DIR))

# Ensure console supports unicode on Windows
try:
    sys.stdout.reconfigure(encoding='utf-8')
except AttributeError:
    pass

from app.services.vector_store import VectorStore

def test_search():
    vector_store = VectorStore()
    
    # If index is empty, dynamically ingest a sample from test_data
    if vector_store.index is None or vector_store.index.ntotal == 0:
        print("FAISS index is currently empty. Ingesting sample text to run test...")
        from app.services.ingestion import ingestion_service
        test_file = BACKEND_DIR / "test_data" / "transformer_attention_mechanisms.txt"
        
        # If test_data folder hasn't been generated, create a quick file
        if not test_file.exists():
            test_file.parent.mkdir(parents=True, exist_ok=True)
            with open(test_file, "w", encoding="utf-8") as f:
                f.write(
                    "Understanding Transformer Attention Mechanisms. "
                    "Self-attention maps query vectors to key vectors to compute weighted value vectors. "
                    "RAG systems utilize FAISS index lookups to fetch context."
                )
        
        ingest_res = ingestion_service.process_text(str(test_file), test_file.name, document_id="test_search_doc_init")
        vector_store.add_document(ingest_res["document_id"])
        vector_store._load()

    # Search for similar chunks
    results = vector_store.search("What is attention in transformers?", k=3)
    
    # Assertions
    assert len(results) > 0, "Search returned 0 results!"
    assert "filename" in results[0], "Key 'filename' is missing from search results!"
    assert 0 <= results[0]["similarity"] <= 1, f"Similarity score {results[0]['similarity']} is out of bounds [0, 1]!"
    
    print(f"✅ Search works! Found {len(results)} results")
    print(f"Top result details:")
    print(f"  - Filename: {results[0]['filename']}")
    print(f"  - Text: '{results[0]['text'][:80]}...'")
    print(f"  - Similarity: {results[0]['similarity']}")

if __name__ == "__main__":
    test_search()
