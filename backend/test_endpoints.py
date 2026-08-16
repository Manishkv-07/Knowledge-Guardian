import sys
from pathlib import Path
from fastapi.testclient import TestClient

# Add backend directory to PYTHONPATH
backend_dir = Path(__file__).resolve().parent
sys.path.append(str(backend_dir))

from app.main import app

client = TestClient(app)

def test_chat_endpoints():
    print("=== Testing FastAPI Chat Endpoints ===")
    
    # 1. Test create conversation
    print("\n1. POST /api/chat/conversations")
    response = client.post("/api/chat/conversations", json={"title": "Attention Test"})
    print(f"Status: {response.status_code}")
    print(f"JSON: {response.json()}")
    assert response.status_code == 200
    conv_id = response.json()["id"]
    
    # 2. Test query endpoint (which handles LLM chat)
    print("\n2. POST /api/query (with attention)")
    response = client.post("/api/query", json={"query": "What is the attention mechanism?", "conversation_id": conv_id})
    print(f"Status: {response.status_code}")
    print(f"JSON: {response.json()}")
    assert response.status_code == 200
    
    # 3. Test list conversations
    print("\n3. GET /api/chat/conversations")
    response = client.get("/api/chat/conversations")
    print(f"Status: {response.status_code}")
    print(f"JSON: {response.json()}")
    assert response.status_code == 200
    
    # 4. Test message history
    print(f"\n4. GET /api/chat/conversations/{conv_id}")
    response = client.get(f"/api/chat/conversations/{conv_id}")
    print(f"Status: {response.status_code}")
    print(f"JSON: {response.json()}")
    assert response.status_code == 200
    
    # 5. Test delete conversation
    print(f"\n5. DELETE /api/chat/conversations/{conv_id}")
    response = client.delete(f"/api/chat/conversations/{conv_id}")
    print(f"Status: {response.status_code}")
    print(f"JSON: {response.json()}")
    assert response.status_code == 200
    
    print("\n=== All Endpoint Tests Passed Successfully ===")

if __name__ == "__main__":
    test_chat_endpoints()
