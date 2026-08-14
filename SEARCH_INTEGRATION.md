# Search Feature Integration Guide

I have implemented the **Search Knowledge** frontend interface. Since the backend search endpoint is still pending, this guide outlines the integration contract.

---

## 🛠️ What Was Completed

1. **Frontend UI**:
   - **`Search.jsx`**: Input form, search button, loading spinner, clean empty/error states.
   - **`SearchResult.jsx`**: Similarity score color codes (Terracotta/Beige/Gray), text expansion, and metadata display.
2. **Routing**: Added the `Search Knowledge` 🔍 tab to the sidebar navigation in `App.jsx`.
3. **API Service**: Added the `searchKnowledge` service method in `api.js` pointing to `POST /search`.

---

## 🔗 Teammate Backend Requirements

Your teammate needs to implement the following endpoint on the backend:

- **Endpoint**: `POST /search` (mapped via the proxy under `/api/search`)
- **Expected Request Payload**:
  ```json
  {
    "query": "search query text",
    "limit": 5
  }
  ```
- **Expected Response Payload (Concept)**:
  ```json
  {
    "results": [
      {
        "chunk_id": "c1",
        "text": "The matched passage text goes here...",
        "filename": "document_name.pdf",
        "similarity": 0.92,
        "chunk_number": 3,
        "total_chunks": 12,
        "date": "2 days ago"
      }
    ]
  }
  ```

---

## 🧪 Visual Testing

To test the visual design and interaction of the search interface without the backend:
1. Open `frontend/src/components/Search.jsx`.
2. Toggle `const USE_MOCK_SEARCH = true;` (on line 8).
3. Search for any term (e.g., "attention") to view high-fidelity mock results.
