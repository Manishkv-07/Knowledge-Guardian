import axios from 'axios';

// Axios instance configured to use development proxy '/api'
const client = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json',
  },
});

export const api = {
  /**
   * Get all uploaded documents and their statuses
   */
  async getDocuments() {
    const response = await client.get('/documents/');
    return response.data;
  },

  /**
   * Upload a PDF file
   * @param {File} file - PDF file to upload
   */
  async uploadDocument(file) {
    const formData = new FormData();
    formData.append('file', file);
    const response = await client.post('/documents/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  },

  /**
   * Delete a document and its associated memories
   * @param {number} docId - ID of the document to delete
   */
  async deleteDocument(docId) {
    const response = await client.delete(`/documents/${docId}`);
    return response.data;
  },

  /**
   * Search knowledge base with natural language query, filters, and pagination
   * @param {string|object} options - The query string or query configuration object
   * @param {number} [topK] - Number of chunks to retrieve (when options is string)
   */
  async queryKnowledgeBase(options, topK = 10) {
    let payload = {};
    if (typeof options === 'string') {
      payload = { query: options, top_k: topK, page: 1, page_size: 5 };
    } else {
      payload = {
        query: options.query || '',
        doc_types: options.doc_types && options.doc_types.length > 0 ? options.doc_types : null,
        start_date: options.start_date || null,
        end_date: options.end_date || null,
        page: options.page || 1,
        page_size: options.page_size || 5,
        top_k: options.top_k || 20,
      };
    }
    const response = await client.post('/documents/query', payload);
    return response.data;
  },

  /**
   * Generate LLM insight/memory for a specific document
   * @param {number} docId - ID of the document
   * @param {string} insightType - type of insight ('summary', 'key_concept', 'custom')
   */
  async generateInsight(docId, insightType, customInstruction = '') {
    const response = await client.post(`/documents/${docId}/generate-insight`, {
      document_id: docId,
      insight_type: insightType,
      custom_instruction: customInstruction,
      content: '' // populated by server
    });
    return response.data;
  },

  /**
   * Stream natural language query answer with citations
   * @param {object} options - Query filters and details
   * @param {function} onCitations - callback when citations metadata is received
   * @param {function} onToken - callback when text token is received
   * @param {function} onDone - callback when generation is completed
   * @param {function} onError - callback on failure
   */
  async streamAnswer(options, onCitations, onToken, onDone, onError) {
    try {
      const payload = {
        query: options.query || '',
        doc_types: options.doc_types && options.doc_types.length > 0 ? options.doc_types : null,
        start_date: options.start_date || null,
        end_date: options.end_date || null,
        page: options.page || 1,
        page_size: options.page_size || 5,
        top_k: options.top_k || 20,
        conversation_id: options.conversation_id || null,
      };

      const response = await fetch('/api/documents/query-stream', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder('utf-8');
      let buffer = '';

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');

        // Save last incomplete line back to buffer
        buffer = lines.pop();

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed) continue;

          if (trimmed.startsWith('data:')) {
            const dataStr = trimmed.slice(5).trim();
            if (dataStr === '[DONE]') {
              if (onDone) onDone();
              return;
            }

            try {
              const parsed = JSON.parse(dataStr);
              if (parsed.type === 'citations' && onCitations) {
                onCitations(parsed.citations, parsed.conversation_id);
              } else if (parsed.type === 'token' && onToken) {
                onToken(parsed.token);
              } else if (parsed.type === 'error' && onError) {
                onError(parsed.message);
              }
            } catch (err) {
              console.error('Error parsing streaming line:', err);
            }
          }
        }
      }
    } catch (err) {
      if (onError) onError(err.message || 'Stream connection error');
    }
  },
};

// Aliasing client to API to match requested signatures
const API = client;

export const getConversations = () => API.get('/chat/conversations').then(res => res.data);
export const createConversation = (title) => API.post('/chat/conversations', { title }).then(res => res.data);
export const getMessages = (conversationId) => API.get(`/chat/conversations/${conversationId}`).then(res => res.data);
export const renameConversation = (id, title) => API.put(`/chat/conversations/${id}?title=${title}`).then(res => res.data);
export const deleteConversation = (id) => API.delete(`/chat/conversations/${id}`).then(res => res.data);
export const sendMessage = (conversationId, query) => API.post('/query', { query, conversation_id: conversationId }).then(res => res.data);

// Also add to the main api export object for compatibility
api.getConversations = getConversations;
api.createConversation = createConversation;
api.getMessages = getMessages;
api.renameConversation = renameConversation;
api.deleteConversation = deleteConversation;
api.sendMessage = sendMessage;



// ==================== Phase 2 API Extensions ====================

// Connections API
api.getConnections = async (params = {}) => {
  const res = await client.get('/connections/', { params });
  return res.data;
};

api.updateConnection = async (id, data) => {
  const res = await client.patch(`/connections/${id}`, data);
  return res.data;
};

api.deleteConnection = async (id) => {
  const res = await client.delete(`/connections/${id}`);
  return res.data;
};

api.discoverConnections = async (documentId = null) => {
  const res = await client.post('/connections/discover', { document_id: documentId });
  return res.data;
};

// Flashcards API
api.getFlashcards = async (params = {}) => {
  const res = await client.get('/flashcards/', { params });
  return res.data;
};

api.createFlashcard = async (data) => {
  const res = await client.post('/flashcards/', data);
  return res.data;
};

api.updateFlashcard = async (id, data) => {
  const res = await client.put(`/flashcards/${id}`, data);
  return res.data;
};

api.deleteFlashcard = async (id) => {
  const res = await client.delete(`/flashcards/${id}`);
  return res.data;
};

api.reviewFlashcard = async (id, action) => {
  const res = await client.post(`/flashcards/${id}/review`, { action });
  return res.data;
};

api.generateFlashcards = async (documentId, count = 3) => {
  const res = await client.post('/flashcards/generate', { document_id: documentId, count });
  return res.data;
};

// Pattern Memories API
api.getPatternMemories = async () => {
  const res = await client.get('/memories/patterns');
  return res.data;
};

api.dismissPatternMemory = async (id) => {
  const res = await client.delete(`/memories/patterns/${id}`);
  return res.data;
};

// ==================== Phase 3 API Extensions ====================

// System Stats & Metrics
api.getStats = async () => {
  const res = await client.get('/stats/');
  return res.data;
};

// Knowledge Graph
api.getKnowledgeGraph = async (params = {}) => {
  const res = await client.get('/connections/graph', { params });
  return res.data;
};

// Export Helpers
api.getExportDocumentUrl = (docId) => `/api/exports/document/${docId}/markdown`;
api.getExportConnectionsUrl = (status = '') => `/api/exports/connections/markdown${status ? `?status=${status}` : ''}`;
api.getExportFlashcardsCsvUrl = (docId = null) => `/api/exports/flashcards/csv${docId ? `?document_id=${docId}` : ''}`;
api.getExportResearchNotesUrl = () => `/api/exports/research-notes/markdown`;
