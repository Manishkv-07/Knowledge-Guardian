import os
import sys
from pathlib import Path

# Add backend directory to sys.path
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

# Ensure stdout supports unicode printing on Windows
try:
    sys.stdout.reconfigure(encoding='utf-8')
except AttributeError:
    pass

from app.services.ingestion import ingestion_service
from app.services.vector_store import vector_store
from app.config import settings

def run_test():
    print("=" * 60)
    print(" Running Ingestion Pipeline Integration Test ".center(60, "="))
    print("=" * 60)
    
    # 1. Create a dummy test text file
    test_filename = "guardian_manifesto.txt"
    test_filepath = BACKEND_DIR / settings.UPLOAD_DIR / test_filename
    os.makedirs(test_filepath.parent, exist_ok=True)
    
    test_content = (
        "The Personal Knowledge Guardian is a proactive AI memory system designed "
        "specifically for researchers and knowledge workers. It uses FastAPI as the API framework, "
        "SQLite for structured memory storage, and FAISS for fast local vector storage.\n\n"
        "A key goal of this project is to foster a calm, minimalist study space where students "
        "can focus on reading and academic work without technical distractions. It features "
        "semantic search capabilities powered by sentence-transformers (all-MiniLM-L6-v2) and "
        "extracts key concepts and summaries using Modal LLM integrations."
    )
    
    print(f"Writing mock document to: {test_filepath}...")
    with open(test_filepath, "w", encoding="utf-8") as f:
        f.write(test_content)
        
    try:
        # 2. Ingest document text
        mock_doc_id = "test_doc_999"
        print(f"\nStep 1: Running Ingestion Service (Splitting text)...")
        ingestion_result = ingestion_service.process_text(str(test_filepath), test_filename, document_id=mock_doc_id)
        
        doc_id = ingestion_result["document_id"]
        total_chunks = ingestion_result["total_chunks"]
        print(f"✓ Ingestion successful! Generated Document ID: {doc_id} with {total_chunks} chunks.")
        
        # Verify chunk file on disk
        chunk_file = BACKEND_DIR / settings.CHUNK_DIR / f"{doc_id}.json"
        if chunk_file.exists():
            print(f"✓ JSON Chunk file successfully written to disk: {chunk_file}")
        else:
            print(f"✗ Failed: JSON Chunk file does not exist!")
            return False

        # 3. Add to FAISS Vector Store
        print(f"\nStep 2: Generating Embeddings & Loading into FAISS Index...")
        store_result = vector_store.add_document(doc_id)
        print(f"✓ Vector Store result: {store_result}")
        
        # Verify index length
        print(f"✓ Current total vectors in FAISS index: {vector_store.index.ntotal}")

        # 4. Search Vector Store
        query = "What database is used for vector storage?"
        print(f"\nStep 3: Performing Semantic Query: '{query}'...")
        search_results = vector_store.search(query, k=2)
        
        if search_results:
            print("✓ Matches Found:")
            for i, res in enumerate(search_results):
                print(f"  Match #{i+1}:")
                print(f"    - Source File: {res['metadata']['filename']}")
                print(f"    - Matching Chunk: '{res['text'].strip()}'")
                print(f"    - Distance Score: {res['score']:.4f}")
                print(f"    - Similarity: {res['similarity']:.4f}")
            return True
        else:
            print("✗ Failed: No search matches found in FAISS!")
            return False

    except Exception as e:
        print(f"✗ Test run crashed with error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Clean up mock files
        if test_filepath.exists():
            os.remove(test_filepath)
            print(f"\nCleaned up temp mock document: {test_filepath}")

if __name__ == "__main__":
    success = run_test()
    if success:
        print("\n🎉 PHASE 1 PIPELINE TEST PASSED SUCCESSFULLY!")
        sys.exit(0)
    else:
        print("\n✗ PHASE 1 PIPELINE TEST FAILED.")
        sys.exit(1)
