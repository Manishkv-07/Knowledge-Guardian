import os
import sys
import time
import requests
import subprocess
import json
from pathlib import Path

# Add backend directory to sys.path
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

# Ensure stdout supports unicode printing on Windows
try:
    sys.stdout.reconfigure(encoding='utf-8')
except AttributeError:
    pass

from app.config import settings

def create_minimal_pdf(filename: str):
    """Creates a tiny valid PDF file containing readable text for PyMuPDF."""
    # This is a valid raw PDF template with a text block
    pdf_content = (
        b"%PDF-1.4\n"
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n"
        b"4 0 obj\n<< /Length 56 >>\nstream\nBT\n/F1 12 Tf\n72 712 Td\n(This is a test PDF document for Personal Knowledge Guardian.) Tj\nET\nendstream\nendobj\n"
        b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n"
        b"xref\n0 6\n0000000000 65535 f \n0000000009 00000 n \n0000000056 00000 n \n0000000111 00000 n \n0000000227 00000 n \n0000000332 00000 n \n"
        b"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n401\n%%EOF"
    )
    with open(filename, "wb") as f:
        f.write(pdf_content)
    print(f"Created temporary PDF: {filename}")

def run_test():
    print("=" * 60)
    print(" Running Ingestion Pipeline Integration Test ".center(60, "="))
    print("=" * 60)

    # 1. Create a test PDF
    pdf_filename = "test_ingestion_doc.pdf"
    pdf_filepath = BACKEND_DIR / pdf_filename
    create_minimal_pdf(pdf_filepath)

    # Start FastAPI server in a background subprocess
    print("\nStarting FastAPI server in background...")
    server_process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8087"],
        cwd=str(BACKEND_DIR),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    # Wait for uvicorn to boot up by polling the server
    print("Waiting for server to start listening...")
    server_ready = False
    for i in range(25):
        try:
            # Check the server health/root endpoint
            requests.get("http://127.0.0.1:8087/", timeout=1)
            server_ready = True
            print(f"✓ Server is up and running after {i+1} seconds!")
            break
        except requests.exceptions.ConnectionError:
            time.sleep(1)
            
    if not server_ready:
        print("✗ Failed: FastAPI server failed to start within 25 seconds.")
        # Retrieve logs before quitting
        server_process.terminate()
        stdout_data, stderr_data = server_process.communicate()
        print("\n--- Uvicorn Server Stdout ---")
        print(stdout_data)
        print("\n--- Uvicorn Server Stderr ---")
        print(stderr_data)
        return False

    try:
        # 2. Upload file via the API
        upload_url = "http://127.0.0.1:8087/api/documents/upload"
        print(f"\nUploading document via API: {upload_url}...")
        
        with open(pdf_filepath, "rb") as f:
            files = {"file": (pdf_filename, f, "application/pdf")}
            response = requests.post(upload_url, files=files)
            
        if response.status_code != 200:
            print(f"✗ Failed: Upload returned status {response.status_code}")
            print(response.text)
            return False
            
        doc_data = response.json()
        doc_id = doc_data["id"]
        print(f"✓ Upload successful! DB Document ID: {doc_id}")

        # 3. Poll document status until indexed
        status_url = "http://127.0.0.1:8087/api/documents/"
        indexed = False
        print("\nPolling document status until indexed...")
        for attempt in range(15):
            time.sleep(2)
            res = requests.get(status_url)
            if res.status_code == 200:
                docs = res.json()
                current_doc = next((d for d in docs if d["id"] == doc_id), None)
                if current_doc:
                    print(f"  Attempt {attempt+1}: Status = {current_doc['status']}")
                    if current_doc["status"] == "indexed":
                        indexed = True
                        break
                    elif current_doc["status"] == "failed":
                        print("✗ Failed: Document ingestion failed!")
                        return False
            else:
                print(f"  Attempt {attempt+1}: Failed to fetch documents (Status: {res.status_code})")
                
        if not indexed:
            print("✗ Failed: Ingestion timed out without status becoming 'indexed'")
            return False

        # 4. Verify chunks are created in chunks/ folder
        chunk_file = BACKEND_DIR / settings.CHUNK_DIR / f"{doc_id}.json"
        if chunk_file.exists():
            with open(chunk_file, "r", encoding="utf-8") as f:
                chunks = json.load(f)
            print(f"✓ Chunks JSON file successfully created at {chunk_file}")
            print(f"  - Count: {len(chunks)} chunk(s)")
            print(f"  - Content Snippet: '{chunks[0]['text'][:50]}...'")
        else:
            print(f"✗ Failed: Chunk JSON file {chunk_file} not found on disk!")
            return False

        # 5. Verify FAISS index is updated
        # Initialize VectorStore locally to check its contents
        from app.services.vector_store import vector_store
        # Reload vector store from disk
        vector_store._load()
        
        print(f"\nVerifying FAISS Index:")
        print(f"  - Total indexed vectors: {vector_store.index.ntotal}")
        print(f"  - Stored documents in vector store: {vector_store.get_all_documents()}")
        
        if str(doc_id) not in vector_store.get_all_documents():
            print(f"✗ Failed: Document ID {doc_id} not indexed in vector store metadata!")
            return False
        print("✓ FAISS index and metadata successfully updated.")

        # 6. Test Search Functionality via API
        query_url = "http://127.0.0.1:8087/api/documents/query"
        query_text = "Knowledge Guardian"
        print(f"\nStep 3: Performing Semantic Query via API: '{query_text}'...")
        
        query_payload = {"query": query_text, "top_k": 2}
        query_response = requests.post(query_url, json=query_payload)
        
        if query_response.status_code == 200:
            matches = query_response.json()
            print(f"✓ API Query successful! Matches returned: {len(matches)}")
            for i, match in enumerate(matches):
                print(f"  Match #{i+1}:")
                print(f"    - Source: {match['document_name']}")
                print(f"    - Score: {match['score']:.4f}")
                print(f"    - Content: '{match['chunk']}'")
        else:
            print(f"✗ Failed: Search API returned status {query_response.status_code}")
            return False

        # 7. Clean up document from Database
        delete_url = f"http://127.0.0.1:8087/api/documents/{doc_id}"
        print(f"\nCleaning up document ID {doc_id} via API...")
        del_res = requests.delete(delete_url)
        if del_res.status_code == 200:
            print("✓ Cleanup successful!")
        else:
            print(f"✗ Warning: Cleanup endpoint returned status {del_res.status_code}")

        return True

    except Exception as e:
        print(f"✗ Test run crashed with error: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        # Stop FastAPI server
        print("\nShutting down FastAPI background server...")
        server_process.terminate()
        try:
            stdout_data, stderr_data = server_process.communicate(timeout=5)
            print("\n--- Uvicorn Server Stdout ---")
            print(stdout_data)
            print("\n--- Uvicorn Server Stderr ---")
            print(stderr_data)
        except Exception as ce:
            print(f"Error capturing server outputs: {ce}")
        
        # Remove temporary PDF file
        if pdf_filepath.exists():
            os.remove(pdf_filepath)
            print(f"Removed temporary PDF: {pdf_filepath}")

if __name__ == "__main__":
    success = run_test()
    if success:
        print("\n🎉 ALL PIPELINE API TESTS PASSED SUCCESSFULLY!")
        sys.exit(0)
    else:
        print("\n✗ PIPELINE API TESTS FAILED.")
        sys.exit(1)
