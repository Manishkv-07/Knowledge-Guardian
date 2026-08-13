import requests
import io
import time
import sys

try:
    sys.stdout.reconfigure(encoding='utf-8')
except AttributeError:
    pass

BASE = 'http://127.0.0.1:8087'

print("=== TESTING LIVE FASTAPI SERVER (http://127.0.0.1:8087) ===")

# 1. Health
r = requests.get(f'{BASE}/health')
print(f"1. Health check: status={r.status_code}, body={r.json()}")
assert r.status_code == 200

# 2. Upload test document
content = (
    "Transformer Attention Mechanisms and Scalability in FAISS Vector Stores. "
    "Modern multi-head self-attention enables token-level semantic encoding across wide context windows. "
    "FAISS provides fast dense vector search with inverted file indexes."
)
files = {'file': ('live_server_test_doc.txt', io.BytesIO(content.encode('utf-8')), 'text/plain')}
r = requests.post(f'{BASE}/api/documents/upload', files=files)
print(f"2. Upload response: status={r.status_code}, data={r.json()}")
assert r.status_code == 200
doc_id = r.json()['id']

# 3. Wait for indexed status
indexed = False
for _ in range(25):
    time.sleep(0.5)
    r = requests.get(f'{BASE}/api/documents/')
    docs = r.json()
    d = next((x for x in docs if x['id'] == doc_id), None)
    if d and d['status'] == 'indexed':
        print(f"3. Document {doc_id} indexed successfully! Chunk count: {d['chunk_count']}")
        indexed = True
        break

assert indexed, "Document failed to reach indexed status"

# 4. Search query
query = "How does Transformer Attention work with FAISS vector stores?"
r = requests.post(f'{BASE}/api/documents/query', json={'query': query, 'top_k': 3})
print(f"4. Search query: '{query}' -> Status: {r.status_code}")
results = r.json()
print(f"   Retrieved results: {len(results)} items")
assert len(results) > 0

for idx, res in enumerate(results):
    sim = res.get('similarity', 0.0)
    doc_name = res.get('document_name', '')
    score = res.get('score', 0.0)
    chunk = res.get('chunk', '')
    print(f"   Result #{idx+1}: doc='{doc_name}', score={score:.4f}, sim={sim:.4f}, text='{chunk[:60]}...'")

assert "Transformer Attention" in results[0]['chunk']

# 5. Search with special characters
spec_query = "Attention & FAISS: [v1.0] #test: neural vector index?"
r = requests.post(f'{BASE}/api/documents/query', json={'query': spec_query, 'top_k': 3})
print(f"5. Special chars query: '{spec_query}' -> Status: {r.status_code}, Results: {len(r.json())}")
assert r.status_code == 200

# 6. Delete cleanup
r = requests.delete(f'{BASE}/api/documents/{doc_id}')
print(f"6. Cleanup document {doc_id}: Status: {r.status_code}, body={r.json()}")
assert r.status_code == 200

print("\n=== ALL LIVE FASTAPI ENDPOINT CHECKS PASSED SUCCESSFULLY! ===")
