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
   * Search knowledge base with natural language query
   * @param {string} query - The query string
   * @param {number} topK - Number of chunks to retrieve
   */
  async queryKnowledgeBase(query, topK = 3) {
    const response = await client.post('/documents/query', { query, top_k: topK });
    return response.data;
  },

  /**
   * Generate LLM insight/memory for a specific document
   * @param {number} docId - ID of the document
   * @param {string} insightType - type of insight ('summary', 'key_concept', 'custom')
   */
  async generateInsight(docId, insightType) {
    const response = await client.post(`/documents/${docId}/generate-insight`, {
      document_id: docId,
      insight_type: insightType,
      content: '' // populated by server
    });
    return response.data;
  },
};
