import React, { useState, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import { useDropzone } from 'react-dropzone';
import { api } from './services/api';
import ChatHistorySidebar from './components/ChatHistorySidebar';
import Chat from './components/Chat';

/**
 * Reusable component to highlight query keywords in text passages.
 * Preserves text casing and handles multi-word query tokens cleanly.
 */
function HighlightText({ text, query, className = "" }) {
  if (!text) return null;
  if (!query || !query.trim()) {
    return <span className={className}>{text}</span>;
  }

  // Tokenize query words (length >= 2, or single alphanumeric character)
  const terms = query
    .toLowerCase()
    .split(/\s+/)
    .map(w => w.replace(/[^a-zA-Z0-9_-]/g, ''))
    .filter(w => w.length > 0);

  if (terms.length === 0) {
    return <span className={className}>{text}</span>;
  }

  // Build regex matching any of the query terms safely
  const escapedTerms = terms.map(t => t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'));
  const regex = new RegExp(`(${escapedTerms.join('|')})`, 'gi');
  const parts = text.split(regex);

  return (
    <span className={className}>
      {parts.map((part, i) => {
        const isMatch = terms.some(t => t.toLowerCase() === part.toLowerCase());
        return isMatch ? (
          <mark
            key={i}
            className="bg-accent-primary/30 text-text-primary px-1 py-0.5 rounded font-medium border-b border-accent-primary/60"
          >
            {part}
          </mark>
        ) : (
          <span key={i}>{part}</span>
        );
      })}
    </span>
  );
}

export default function App() {
  const [documents, setDocuments] = useState([]);
  const [selectedDocId, setSelectedDocId] = useState(null);
  const [activeTab, setActiveTab] = useState('library'); // 'library' | 'chat' | 'insights' | 'stats'
  
  // Search & Filter States
  const [searchQuery, setSearchQuery] = useState('');
  const [activeSearchQuery, setActiveSearchQuery] = useState('');
  const [selectedDocTypes, setSelectedDocTypes] = useState([]); // ['pdf', 'txt', 'md'] or [] for all
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [showFilterPanel, setShowFilterPanel] = useState(false);
  
  // Pagination & Results States
  const [searchResults, setSearchResults] = useState([]);
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(5);
  const [totalPages, setTotalPages] = useState(1);
  const [totalResults, setTotalResults] = useState(0);
  const [expandedRelated, setExpandedRelated] = useState({}); // { [chunk_id]: boolean }

  const [topK, setTopK] = useState(20);
  const [insightType, setInsightType] = useState('summary');
  const [isUploading, setIsUploading] = useState(false);
  const [isSearching, setIsSearching] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [apiStatus, setApiStatus] = useState('checking'); // 'online' | 'offline' | 'checking'
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');

  // Chat History / Episodic Memory States
  const [conversations, setConversations] = useState([]);
  const [activeConversationId, setActiveConversationId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [isChatLoading, setIsChatLoading] = useState(false);

  // Load conversations list
  const loadConversations = async () => {
    try {
      const data = await api.getConversations();
      setConversations(data);
    } catch (err) {
      console.error("Failed to load conversations", err);
    }
  };

  // Load message history for active conversation
  const loadMessages = async (convId) => {
    setIsChatLoading(true);
    try {
      const data = await api.getMessages(convId);
      setMessages(data);
    } catch (err) {
      console.error("Failed to load messages", err);
    } finally {
      setIsChatLoading(false);
    }
  };

  // Effect to load conversations list when switching to Chat tab
  useEffect(() => {
    if (activeTab === 'chat') {
      loadConversations();
    }
  }, [activeTab]);

  // Effect to load messages list when active conversation changes
  useEffect(() => {
    if (activeConversationId) {
      loadMessages(activeConversationId);
    } else {
      setMessages([]);
    }
  }, [activeConversationId]);

  const handleCreateConversation = async (title = "New Conversation") => {
    try {
      const res = await api.createConversation(title);
      await loadConversations();
      setActiveConversationId(res.id);
    } catch (err) {
      showError("Failed to create new conversation thread.");
    }
  };

  const handleRenameConversation = async (id, newTitle) => {
    try {
      await api.renameConversation(id, newTitle);
      await loadConversations();
    } catch (err) {
      showError("Failed to rename conversation.");
    }
  };

  const handleDeleteConversation = async (id) => {
    try {
      await api.deleteConversation(id);
      if (activeConversationId === id) {
        setActiveConversationId(null);
        setMessages([]);
      }
      await loadConversations();
    } catch (err) {
      showError("Failed to delete conversation.");
    }
  };

  const handleSendMessage = async (queryText) => {
    setIsChatLoading(true);
    
    // 1. Add user query immediately to the message display list for responsiveness
    const tempUserMsg = {
      id: `temp-user-${Date.now()}`,
      role: 'user',
      content: queryText,
      created_at: new Date().toISOString(),
    };
    
    // 2. Add placeholder assistant bubble with typing indicator
    const tempAssistantId = `temp-assistant-${Date.now()}`;
    const tempAssistantMsg = {
      id: tempAssistantId,
      role: 'assistant',
      content: '',
      sources: [],
      created_at: new Date().toISOString(),
    };

    setMessages(prev => [...prev, tempUserMsg, tempAssistantMsg]);

    let accumulatedText = "";
    let matchingCitations = [];

    // Call the streaming API
    api.streamAnswer(
      {
        query: queryText,
        conversation_id: activeConversationId
      },
      // onCitations callback
      (citations, conversationId) => {
        matchingCitations = citations || [];
        if (!activeConversationId && conversationId) {
          setActiveConversationId(conversationId);
        }

        // Update citations in the assistant's message bubble
        setMessages(prev => {
          const updated = [...prev];
          const assistantIndex = updated.findIndex(m => m.id === tempAssistantId);
          if (assistantIndex !== -1) {
            updated[assistantIndex] = {
              ...updated[assistantIndex],
              sources: matchingCitations
            };
          }
          return updated;
        });
      },
      // onToken callback
      (token) => {
        accumulatedText += token;
        setMessages(prev => {
          const updated = [...prev];
          const assistantIndex = updated.findIndex(m => m.id === tempAssistantId);
          if (assistantIndex !== -1) {
            updated[assistantIndex] = {
              ...updated[assistantIndex],
              content: accumulatedText
            };
          }
          return updated;
        });
      },
      // onDone callback
      async () => {
        setIsChatLoading(false);
        // Reload conversations to update last message preview in the sidebar
        await loadConversations();
      },
      // onError callback
      (errorMsg) => {
        console.error("Streaming error:", errorMsg);
        setIsChatLoading(false);
        setMessages(prev => {
          const updated = [...prev];
          const assistantIndex = updated.findIndex(m => m.id === tempAssistantId);
          if (assistantIndex !== -1) {
            updated[assistantIndex] = {
              ...updated[assistantIndex],
              content: `⚠️ Failed to connect to Ollama. Please check if your Google Colab instance is running and Ngrok tunnel is established. Error: ${errorMsg}`
            };
          }
          return updated;
        });
      }
    );
  };


  // Poll for document list on mount and every 4 seconds to catch processing status changes
  useEffect(() => {
    checkBackendHealth();
    loadDocuments();
    const interval = setInterval(loadDocuments, 4000);
    return () => clearInterval(interval);
  }, []);

  const checkBackendHealth = async () => {
    try {
      const response = await fetch('/api/health');
      if (response.ok) {
        setApiStatus('online');
      } else {
        setApiStatus('offline');
      }
    } catch {
      setApiStatus('offline');
    }
  };

  const loadDocuments = async () => {
    try {
      const docs = await api.getDocuments();
      setDocuments(docs);
      setApiStatus('online');
    } catch (err) {
      console.error("Failed to load documents", err);
    }
  };

  // Dropzone callback handling file drop (PDF, TXT, MD)
  const onDrop = React.useCallback(async (acceptedFiles) => {
    const file = acceptedFiles[0];
    if (!file) return;
    
    const ext = file.name.split('.').pop()?.toLowerCase();
    if (!['pdf', 'txt', 'md'].includes(ext)) {
      showError("Supported formats: PDF, TXT, and Markdown (MD) files.");
      return;
    }

    setIsUploading(true);
    setErrorMessage('');
    try {
      await api.uploadDocument(file);
      await loadDocuments();
      setShowUploadModal(false);
    } catch (err) {
      showError(err.response?.data?.detail || "Failed to upload document.");
    } finally {
      setIsUploading(false);
    }
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf'],
      'text/plain': ['.txt'],
      'text/markdown': ['.md']
    },
    multiple: false,
    disabled: isUploading
  });

  const handleDelete = async (docId, e) => {
    e.stopPropagation();
    if (!window.confirm("Are you sure you want to delete this document and its memory indices?")) return;
    try {
      await api.deleteDocument(docId);
      if (selectedDocId === docId) setSelectedDocId(null);
      await loadDocuments();
    } catch (err) {
      showError("Failed to delete document.");
    }
  };

  /**
   * Execute semantic search query with current filters and pagination
   */
  const executeSearch = async (
    queryText,
    page = 1,
    types = selectedDocTypes,
    sDate = startDate,
    eDate = endDate,
    pSize = pageSize
  ) => {
    if (!queryText || !queryText.trim()) return { items: [], total: 0 };

    setIsSearching(true);
    setErrorMessage('');

    try {
      const response = await api.queryKnowledgeBase({
        query: queryText,
        doc_types: types.length > 0 ? types : null,
        start_date: sDate || null,
        end_date: eDate || null,
        page: page,
        page_size: pSize,
        top_k: 30,
      });

      const items = response.items || (Array.isArray(response) ? response : []);
      const total = response.total !== undefined ? response.total : items.length;
      const totalP = response.total_pages !== undefined ? response.total_pages : 1;

      setSearchResults(items);
      setCurrentPage(page);
      setTotalPages(totalP);
      setTotalResults(total);
      setActiveSearchQuery(queryText);

      return { items, total };
    } catch (err) {
      showError("Search failed. Ensure your documents are processed and indexed.");
      return { items: [], total: 0 };
    } finally {
      setIsSearching(false);
    }
  };



  // Handle page change in pagination
  const handlePageChange = (newPage) => {
    if (newPage < 1 || newPage > totalPages || newPage === currentPage) return;
    if (activeSearchQuery) {
      executeSearch(activeSearchQuery, newPage, selectedDocTypes, startDate, endDate, pageSize);
    }
  };

  // Toggle document type filter pill
  const toggleDocTypeFilter = (type) => {
    let updated;
    if (selectedDocTypes.includes(type)) {
      updated = selectedDocTypes.filter(t => t !== type);
    } else {
      updated = [...selectedDocTypes, type];
    }
    setSelectedDocTypes(updated);
    if (activeSearchQuery) {
      executeSearch(activeSearchQuery, 1, updated, startDate, endDate, pageSize);
    }
  };

  // Reset all search filters
  const resetFilters = () => {
    setSelectedDocTypes([]);
    setStartDate('');
    setEndDate('');
    if (activeSearchQuery) {
      executeSearch(activeSearchQuery, 1, [], '', '', pageSize);
    }
  };

  // Toggle "Related Chunks" accordion for a given result
  const toggleRelated = (chunkId) => {
    setExpandedRelated(prev => ({
      ...prev,
      [chunkId]: !prev[chunkId]
    }));
  };

  const handleGenerateInsight = async () => {
    if (!selectedDocId) {
      showError("Please select a document from the library to analyze.");
      return;
    }

    setIsGenerating(true);
    setErrorMessage('');
    try {
      await api.generateInsight(selectedDocId, insightType);
      await loadDocuments(); // Reload to get updated memories list
    } catch (err) {
      showError("Failed to generate insight. Verify your Modal LLM configurations.");
    } finally {
      setIsGenerating(false);
    }
  };

  const showError = (msg) => {
    setErrorMessage(msg);
    setTimeout(() => setErrorMessage(''), 6000);
  };

  const formatSize = (bytes) => {
    if (!bytes || bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const selectedDoc = documents.find(d => d.id === selectedDocId);
  const totalChunksCount = documents.reduce((acc, doc) => acc + (doc.chunk_count || 15), 0);
  const indexedDocs = documents.filter(d => d.status === 'indexed');
  const memoriesCount = documents.reduce((acc, doc) => acc + (doc.memories?.length || 0), 0);
  const hasActiveFilters = selectedDocTypes.length > 0 || startDate !== '' || endDate !== '';

  return (
    <div className="min-h-screen flex bg-bg-warm text-text-primary font-sans antialiased">
      
      {/* 📚 Left Sidebar */}
      <aside className="w-64 bg-sidebar-warm border-r border-accent-secondary p-6 flex flex-col justify-between shrink-0">
        <div className="space-y-8">
          
          {/* Logo Area */}
          <div className="flex items-center gap-3">
            <div className="h-9 w-9 rounded-lg bg-accent-primary flex items-center justify-center shadow-sm">
              <svg className="h-5 w-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
              </svg>
            </div>
            <div>
              <h2 className="font-serif font-bold text-base leading-tight text-text-primary">Guardian</h2>
              <p className="text-[10px] text-text-secondary tracking-widest uppercase">Knowledge Space</p>
            </div>
          </div>

          {/* Navigation items */}
          <nav className="space-y-1">
            <button
              onClick={() => setActiveTab('library')}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all ${
                activeTab === 'library'
                  ? 'bg-accent-secondary/60 text-text-primary shadow-sm font-semibold'
                  : 'text-text-secondary hover:bg-accent-secondary/30 hover:text-text-primary'
              }`}
            >
              <span>📚</span>
              <span>Library</span>
            </button>
            <button
              onClick={() => setActiveTab('chat')}
              className={`w-full flex items-center justify-between px-3 py-2.5 rounded-lg text-sm font-medium transition-all ${
                activeTab === 'chat'
                  ? 'bg-accent-secondary/60 text-text-primary shadow-sm font-semibold'
                  : 'text-text-secondary hover:bg-accent-secondary/30 hover:text-text-primary'
              }`}
            >
              <div className="flex items-center gap-3">
                <span>💬</span>
                <span>Study Chat & Search</span>
              </div>
              {hasActiveFilters && (
                <span className="h-2 w-2 rounded-full bg-accent-primary" title="Filters Active"></span>
              )}
            </button>
            <button
              onClick={() => setActiveTab('insights')}
              className={`w-full flex items-center justify-between px-3 py-2.5 rounded-lg text-sm font-medium transition-all ${
                activeTab === 'insights'
                  ? 'bg-accent-secondary/60 text-text-primary shadow-sm font-semibold'
                  : 'text-text-secondary hover:bg-accent-secondary/30 hover:text-text-primary'
              }`}
            >
              <div className="flex items-center gap-3">
                <span>🔮</span>
                <span>Proactive Insights</span>
              </div>
              <span className="h-2 w-2 rounded-full bg-status-success" title="New Insights Available"></span>
            </button>
            <button
              onClick={() => setActiveTab('stats')}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all ${
                activeTab === 'stats'
                  ? 'bg-accent-secondary/60 text-text-primary shadow-sm font-semibold'
                  : 'text-text-secondary hover:bg-accent-secondary/30 hover:text-text-primary'
              }`}
            >
              <span>📊</span>
              <span>Statistics</span>
            </button>
          </nav>
        </div>

        {/* System Status Footnote */}
        <div className="pt-4 border-t border-accent-secondary/40 space-y-2">
          <div className="flex items-center justify-between text-xs">
            <span className="text-text-secondary">System Backend</span>
            <div className="flex items-center gap-1.5">
              <span className={`h-2 w-2 rounded-full ${apiStatus === 'online' ? 'bg-status-success' : apiStatus === 'checking' ? 'bg-accent-primary animate-pulse' : 'bg-status-error'}`}></span>
              <span className="text-[11px] font-medium capitalize text-text-secondary">{apiStatus}</span>
            </div>
          </div>
          <p className="text-[10px] text-text-muted">Embedding: 384-d FAISS</p>
        </div>
      </aside>

      {/* 📄 Main Content Area */}
      <div className="flex-1 flex flex-col h-screen overflow-hidden p-8">
        
        {/* Header Bar */}
        <header className="flex items-center justify-between pb-6 mb-6 border-b border-accent-secondary/40 shrink-0">
          <div>
            <span className="text-xs text-text-secondary uppercase tracking-wider font-semibold">Knowledge Guardian Workspace</span>
            <h1 className="font-serif text-xl font-bold text-text-primary">
              {activeTab === 'library' && 'Document Library & Ingestion'}
              {activeTab === 'chat' && 'Study Chat & Advanced Retrieval'}
              {activeTab === 'insights' && 'Proactive Memory & Concepts'}
              {activeTab === 'stats' && 'Analytics & Vector Index Metrics'}
            </h1>
          </div>

          <button
            onClick={() => setShowUploadModal(true)}
            className="bg-accent-primary hover:bg-accent-tertiary text-white font-medium text-xs px-4 py-2.5 rounded-lg transition-all duration-200 shadow-sm flex items-center gap-2 cursor-pointer"
          >
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
            </svg>
            Ingest Document (PDF, TXT, MD)
          </button>
        </header>

        {errorMessage && (
          <div className="mb-4 bg-status-error/10 border border-status-error/20 text-status-error text-xs px-4 py-2.5 rounded-lg flex items-center justify-between shrink-0">
            <span>{errorMessage}</span>
            <button onClick={() => setErrorMessage('')} className="hover:opacity-85 text-sm cursor-pointer">×</button>
          </div>
        )}

        {/* 📚 Tab 1: Library/Dashboard View */}
        {activeTab === 'library' && (
          <div className="flex-1 overflow-y-auto space-y-8 pr-1">
            <div>
              <h1 className="font-serif text-2xl font-bold text-text-primary tracking-tight">Welcome back 👋</h1>
              <p className="text-xs text-text-secondary mt-1">Your personal research guardian is active and indexing document knowledge.</p>
            </div>

            {/* Stats Row */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="bg-white border border-accent-secondary/50 rounded-xl p-4 shadow-[0_2px_8px_rgba(0,0,0,0.02)]">
                <span className="text-[10px] text-text-muted uppercase tracking-wider block font-semibold">Total Documents</span>
                <span className="text-xl font-bold font-serif text-text-primary mt-1 block">{documents.length}</span>
              </div>
              <div className="bg-white border border-accent-secondary/50 rounded-xl p-4 shadow-[0_2px_8px_rgba(0,0,0,0.02)]">
                <span className="text-[10px] text-text-muted uppercase tracking-wider block font-semibold">Connected Insights</span>
                <span className="text-xl font-bold font-serif text-text-primary mt-1 block">{memoriesCount}</span>
              </div>
              <div className="bg-white border border-accent-secondary/50 rounded-xl p-4 shadow-[0_2px_8px_rgba(0,0,0,0.02)]">
                <span className="text-[10px] text-text-muted uppercase tracking-wider block font-semibold">Indexed Chunks</span>
                <span className="text-xl font-bold font-serif text-text-primary mt-1 block">{indexedDocs.length > 0 ? totalChunksCount : 0}</span>
              </div>
              <div className="bg-white border border-accent-secondary/50 rounded-xl p-4 shadow-[0_2px_8px_rgba(0,0,0,0.02)]">
                <span className="text-[10px] text-text-muted uppercase tracking-wider block font-semibold">Study Streak</span>
                <span className="text-xl font-bold font-serif text-text-primary mt-1 block">5 Days 🔥</span>
              </div>
            </div>

            {/* Main Library Grid / Timeline split */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
              
              {/* Document Cards */}
              <div className="lg:col-span-2 space-y-4">
                <h3 className="font-serif text-lg font-bold text-text-primary">Your Study Library</h3>
                
                {documents.length === 0 ? (
                  <div className="h-60 rounded-xl border border-dashed border-accent-secondary bg-white flex flex-col items-center justify-center text-center p-6">
                    <svg className="h-10 w-10 text-accent-primary mb-2 opacity-60" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
                    </svg>
                    <p className="text-sm font-serif font-semibold text-text-primary">Your library is currently empty</p>
                    <p className="text-xs text-text-secondary mt-1">Upload a research PDF, TXT, or MD document above to begin semantic indexing.</p>
                  </div>
                ) : (
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    {documents.map((doc) => {
                      const ext = doc.filename.split('.').pop()?.toUpperCase() || 'DOC';
                      const statusStyles = {
                        uploaded: 'bg-accent-secondary/50 text-text-secondary border-accent-secondary',
                        processing: 'bg-accent-primary/20 text-accent-tertiary border-accent-primary/40 animate-pulse',
                        indexed: 'bg-status-success/15 text-status-success border-status-success/30',
                        failed: 'bg-status-error/15 text-status-error border-status-error/30',
                      };

                      return (
                        <div
                          key={doc.id}
                          className="bg-white border border-accent-secondary/40 rounded-xl p-4 flex flex-col justify-between hover:shadow-md hover:border-accent-primary/60 transition-all duration-200 group"
                        >
                          <div>
                            <div className="flex items-start justify-between gap-2 mb-2">
                              <span className="text-xs font-semibold px-2 py-0.5 rounded bg-bg-warm text-accent-tertiary font-mono">{ext}</span>
                              <button
                                onClick={(e) => handleDelete(doc.id, e)}
                                className="opacity-0 group-hover:opacity-100 text-text-muted hover:text-status-error transition-all p-0.5 rounded hover:bg-bg-warm cursor-pointer"
                                title="Remove File"
                              >
                                <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                                </svg>
                              </button>
                            </div>
                            <h4 className="font-serif text-sm font-bold text-text-primary line-clamp-2 leading-snug group-hover:text-accent-tertiary transition-colors" title={doc.filename}>
                              {doc.filename}
                            </h4>
                          </div>

                          <div className="mt-4 pt-3 border-t border-bg-warm flex items-center justify-between text-xs text-text-muted">
                            <span>{formatSize(doc.file_size)} • {doc.chunk_count || 0} chunks</span>
                            <span className={`px-2 py-0.5 rounded-full border text-[10px] uppercase font-bold tracking-wider ${statusStyles[doc.status] || 'bg-bg-warm text-text-secondary'}`}>
                              {doc.status}
                            </span>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>

              {/* Timeline feed */}
              <div className="space-y-4">
                <h3 className="font-serif text-lg font-bold text-text-primary">Recent Activity Feed</h3>
                <div className="bg-white border border-accent-secondary/50 rounded-xl p-5 shadow-[0_2px_8px_rgba(0,0,0,0.02)] space-y-4 text-xs">
                  <div className="relative pl-5 border-l-2 border-accent-secondary space-y-4">
                    
                    <div className="relative">
                      <span className="absolute -left-[26px] top-0 bg-accent-primary h-2 w-2 rounded-full ring-4 ring-white"></span>
                      <p className="font-semibold text-text-primary">Ingestion pipeline active</p>
                      <p className="text-text-muted mt-0.5">Automated parsing & FAISS embedding generation ready.</p>
                      <span className="text-[10px] text-text-muted block mt-1">Today</span>
                    </div>

                    <div className="relative">
                      <span className="absolute -left-[26px] top-0 bg-accent-tertiary h-2 w-2 rounded-full ring-4 ring-white"></span>
                      <p className="font-semibold text-text-primary">Advanced search enabled</p>
                      <p className="text-text-muted mt-0.5">Filtering by doc type, dates, highlighting & related chunks online.</p>
                      <span className="text-[10px] text-text-muted block mt-1">Active</span>
                    </div>
                  </div>
                </div>
              </div>

            </div>
          </div>
        )}

        {/* 💬 Tab 2: Study Chat / Ask View with Chat History & Sidebar */}
        {activeTab === 'chat' && (
          <div className="flex-1 flex overflow-hidden gap-6">
            <ChatHistorySidebar
              conversations={conversations}
              activeConversationId={activeConversationId}
              onSelectConversation={setActiveConversationId}
              onCreateConversation={handleCreateConversation}
              onRenameConversation={handleRenameConversation}
              onDeleteConversation={handleDeleteConversation}
            />
            <div className="flex-1 flex flex-col justify-between bg-white border border-accent-secondary/50 rounded-2xl shadow-[0_4px_12px_rgba(0,0,0,0.02)] overflow-hidden">
              <Chat
                activeConversationId={activeConversationId}
                messages={messages}
                onSendMessage={handleSendMessage}
                isLoading={isChatLoading}
              />
            </div>
          </div>
        )}

        {/* 🔮 Tab 3: Proactive Insights View */}
        {activeTab === 'insights' && (
          <div className="flex-1 overflow-y-auto space-y-6 pr-1">
            <div>
              <h1 className="font-serif text-2xl font-bold text-text-primary tracking-tight">Proactive Guardian Insights</h1>
              <p className="text-xs text-text-secondary mt-1">Cross-referencing papers & notes to surface concepts and summaries.</p>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              
              {/* Insight Controls & List */}
              <div className="lg:col-span-2 space-y-6">
                
                {/* Generation Control Card */}
                <div className="bg-white border border-accent-secondary/50 rounded-xl p-5 shadow-[0_2px_8px_rgba(0,0,0,0.02)] space-y-4">
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div className="space-y-1">
                      <label className="text-[10px] font-bold uppercase tracking-wider text-text-secondary">Target Document</label>
                      <select 
                        value={selectedDocId || ''} 
                        onChange={(e) => setSelectedDocId(e.target.value ? parseInt(e.target.value) : null)}
                        className="w-full bg-bg-warm border border-accent-secondary rounded-lg px-3 py-2 text-xs outline-none text-text-primary cursor-pointer"
                      >
                        <option value="">-- Choose an Indexed Document --</option>
                        {documents.filter(d => d.status === 'indexed').map(d => (
                          <option key={d.id} value={d.id}>{d.filename}</option>
                        ))}
                      </select>
                    </div>

                    <div className="space-y-1">
                      <label className="text-[10px] font-bold uppercase tracking-wider text-text-secondary">Insight Type</label>
                      <div className="flex gap-1.5">
                        {['summary', 'key_concept', 'custom'].map((t) => (
                          <button
                            key={t}
                            type="button"
                            onClick={() => setInsightType(t)}
                            className={`flex-1 py-1.5 rounded-lg text-xs font-semibold border capitalize transition-all cursor-pointer ${
                              insightType === t 
                                ? 'bg-accent-primary text-white border-accent-primary' 
                                : 'bg-bg-warm border-accent-secondary text-text-secondary hover:text-text-primary'
                            }`}
                          >
                            {t.replace('_', ' ')}
                          </button>
                        ))}
                      </div>
                    </div>
                  </div>

                  <button
                    onClick={handleGenerateInsight}
                    disabled={isGenerating || !selectedDocId}
                    className="w-full bg-accent-primary hover:bg-accent-tertiary disabled:opacity-40 text-white font-semibold text-xs py-2.5 rounded-lg transition-all duration-200 flex items-center justify-center gap-1.5 shadow-sm cursor-pointer"
                  >
                    {isGenerating ? (
                      <>
                        <svg className="animate-spin h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                        </svg>
                        Deploying Modal Inference...
                      </>
                    ) : (
                      'Extract & Store Insight'
                    )}
                  </button>
                </div>

                {/* Insight list */}
                <div className="space-y-4">
                  <h3 className="font-serif text-lg font-bold text-text-primary">Stored Memory Units</h3>
                  
                  {!selectedDoc ? (
                    <div className="rounded-xl border border-accent-secondary/50 bg-white p-8 text-center text-text-muted text-xs">
                      Please select an indexed document above to inspect its memory units.
                    </div>
                  ) : selectedDoc.memories.length === 0 ? (
                    <div className="rounded-xl border border-accent-secondary/50 bg-white p-8 text-center text-text-muted text-xs">
                      No memories generated for "{selectedDoc.filename}" yet. Tap "Extract & Store Insight" to begin.
                    </div>
                  ) : (
                    <div className="space-y-3">
                      {selectedDoc.memories.map((mem) => (
                        <div key={mem.id} className="bg-white border border-accent-secondary/40 rounded-xl p-5 space-y-3">
                          <div className="flex items-center justify-between text-xs">
                            <span className={`px-2 py-0.5 rounded-full border text-[10px] font-bold uppercase tracking-wider ${
                              mem.insight_type === 'summary' 
                                ? 'bg-accent-primary/10 text-accent-tertiary border-accent-primary/20' 
                                : 'bg-status-success/10 text-status-success border-status-success/20'
                            }`}>
                              {mem.insight_type.replace('_', ' ')}
                            </span>
                            <span className="text-text-muted text-[10px] font-mono">
                              {new Date(mem.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                            </span>
                          </div>
                          <div className="markdown-body text-text-primary text-sm font-serif leading-relaxed bg-bg-warm/30 p-4 rounded-lg border border-accent-secondary/20 space-y-2">
                            <ReactMarkdown>{mem.content}</ReactMarkdown>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

              </div>

              {/* Learning Patterns panel */}
              <div className="space-y-6">
                <h3 className="font-serif text-lg font-bold text-text-primary">Cognitive Cycles</h3>
                <div className="bg-white border border-accent-secondary/50 rounded-xl p-5 shadow-[0_2px_8px_rgba(0,0,0,0.02)] space-y-4">
                  
                  <div className="space-y-1 pb-3 border-b border-bg-warm">
                    <h4 className="text-xs font-bold text-text-primary flex items-center gap-1.5">
                      <span>🌅</span> Peak Learning Hours
                    </h4>
                    <p className="text-[11px] text-text-secondary">9:00 AM - 11:30 AM (Highest concentration index matches)</p>
                  </div>

                  <div className="space-y-1 pb-3 border-b border-bg-warm">
                    <h4 className="text-xs font-bold text-text-primary flex items-center gap-1.5">
                      <span>🔄</span> Topic Cycles
                    </h4>
                    <p className="text-[11px] text-text-secondary">Transformers & Semantic Indexes (3x repeats this week)</p>
                  </div>

                  <div className="space-y-1">
                    <h4 className="text-xs font-bold text-text-primary flex items-center gap-1.5">
                      <span>💡</span> Breakthrough Conditions
                    </h4>
                    <p className="text-[11px] text-text-secondary">Quiet night reading sessions with high page counts</p>
                  </div>

                </div>
              </div>

            </div>
          </div>
        )}

        {/* 📊 Tab 4: Statistics View */}
        {activeTab === 'stats' && (
          <div className="flex-1 overflow-y-auto space-y-6 pr-1">
            <div>
              <h1 className="font-serif text-2xl font-bold text-text-primary tracking-tight">Your Learning Metrics</h1>
              <p className="text-xs text-text-secondary mt-1">Analytics on your document library, chunks, and index density.</p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              
              {/* Box 1: Vector Store Status */}
              <div className="bg-white border border-accent-secondary/50 rounded-xl p-5 space-y-4">
                <h3 className="font-serif text-sm font-bold text-text-primary border-b border-bg-warm pb-2">Vector Index Metrics</h3>
                <div className="space-y-3 text-xs">
                  <div className="flex justify-between">
                    <span className="text-text-secondary">FAISS Index Dimension</span>
                    <span className="font-mono font-semibold text-text-primary">384 (all-MiniLM-L6-v2)</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-text-secondary">Total Embedded Vectors</span>
                    <span className="font-mono font-semibold text-text-primary">{indexedDocs.length > 0 ? totalChunksCount : 0}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-text-secondary">Vector Store Location</span>
                    <span className="font-mono font-semibold text-text-primary">data/vector_store/</span>
                  </div>
                </div>
              </div>

              {/* Box 2: Memory Database Status */}
              <div className="bg-white border border-accent-secondary/50 rounded-xl p-5 space-y-4">
                <h3 className="font-serif text-sm font-bold text-text-primary border-b border-bg-warm pb-2">Database Metadata</h3>
                <div className="space-y-3 text-xs">
                  <div className="flex justify-between">
                    <span className="text-text-secondary">Database Engine</span>
                    <span className="font-mono font-semibold text-text-primary">SQLite 3</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-text-secondary">Stored Insight Records</span>
                    <span className="font-mono font-semibold text-text-primary">{memoriesCount}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-text-secondary">SQLite Location</span>
                    <span className="font-mono font-semibold text-text-primary">data/memory/guardian.db</span>
                  </div>
                </div>
              </div>

            </div>
          </div>
        )}

      </div>

      {/* 📁 Upload Modal (PDF, TXT, MD) */}
      {showUploadModal && (
        <div className="fixed inset-0 bg-text-primary/20 backdrop-blur-xs flex items-center justify-center z-50">
          <div className="bg-white border border-accent-secondary rounded-2xl w-full max-w-md p-6 space-y-4 shadow-xl">
            
            <div className="flex items-center justify-between border-b border-bg-warm pb-3">
              <h3 className="font-serif font-bold text-base text-text-primary">Ingest Document</h3>
              <button 
                onClick={() => setShowUploadModal(false)} 
                className="text-text-muted hover:text-text-primary text-xl font-medium cursor-pointer"
              >
                &times;
              </button>
            </div>

            <div className="space-y-4">
              <div
                {...getRootProps()}
                className={`py-10 px-4 rounded-xl border-2 border-dashed transition-all duration-200 flex flex-col items-center justify-center gap-2 cursor-pointer outline-none ${
                  isDragActive || isUploading 
                    ? 'border-accent-primary bg-bg-warm text-accent-tertiary' 
                    : 'border-accent-secondary bg-bg-warm/50 hover:bg-bg-warm hover:border-accent-primary text-text-secondary'
                }`}
              >
                <input {...getInputProps()} />
                {isUploading ? (
                  <>
                    <svg className="animate-spin h-6 w-6 text-accent-primary" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    <span className="text-xs font-semibold text-accent-tertiary">Ingesting, splitting and indexing...</span>
                  </>
                ) : (
                  <>
                    <svg className="h-8 w-8 text-accent-primary opacity-70" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M9 13h6m-3-3v6m-9 1V4a2 2 0 012-2h6l2 2h6a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2z" />
                    </svg>
                    <span className="text-xs font-semibold text-text-primary">
                      {isDragActive ? "Drop the file here..." : "Drag & drop or click to select file"}
                    </span>
                    <span className="text-[10px] text-text-muted">Supports PDF, TXT, and Markdown (MD) documents</span>
                  </>
                )}
              </div>
            </div>

            <div className="flex justify-end gap-2 border-t border-bg-warm pt-3">
              <button
                onClick={() => setShowUploadModal(false)}
                className="px-4 py-2 bg-bg-warm hover:bg-accent-secondary/30 rounded-lg text-xs font-semibold text-text-secondary border border-accent-secondary/60 cursor-pointer"
              >
                Cancel
              </button>
            </div>

          </div>
        </div>
      )}

    </div>
  );
}
