import React, { useState, useEffect } from 'react';
import { useDropzone } from 'react-dropzone';
import { api } from './services/api';
import ChatHistorySidebar from './components/ChatHistorySidebar';
import Chat from './components/Chat';
import AdvancedSearch, { HighlightText } from './components/AdvancedSearch';
import ConnectionsView from './components/ConnectionsView';
import FlashcardsView from './components/FlashcardsView';
import MemoryPatternsView from './components/MemoryPatternsView';
import SystemMetricsView from './components/SystemMetricsView';

export default function App() {
  const [documents, setDocuments] = useState([]);
  const [selectedDocId, setSelectedDocId] = useState(null);
  const [activeTab, setActiveTab] = useState('library'); // 'library' | 'search' | 'chat' | 'connections' | 'flashcards' | 'insights' | 'stats'
  
  // Search & Filter States
  const [searchQuery, setSearchQuery] = useState('');
  const [activeSearchQuery, setActiveSearchQuery] = useState('');
  const [selectedDocTypes, setSelectedDocTypes] = useState([]);
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  
  // Pagination & Results States
  const [searchResults, setSearchResults] = useState([]);
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(5);
  const [totalPages, setTotalPages] = useState(1);
  const [totalResults, setTotalResults] = useState(0);
  const [expandedRelated, setExpandedRelated] = useState({});

  const [isUploading, setIsUploading] = useState(false);
  const [isSearching, setIsSearching] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [apiStatus, setApiStatus] = useState('checking');
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
      setConversations(data || []);
    } catch (err) {
      console.error("Failed to load conversations", err);
    }
  };

  // Load message history for active conversation
  const loadMessages = async (convId) => {
    setIsChatLoading(true);
    try {
      const data = await api.getMessages(convId);
      setMessages(data || []);
    } catch (err) {
      console.error("Failed to load messages", err);
    } finally {
      setIsChatLoading(false);
    }
  };

  useEffect(() => {
    if (activeTab === 'chat') {
      loadConversations();
    }
  }, [activeTab]);

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
    
    const tempUserMsg = {
      id: `temp-user-${Date.now()}`,
      role: 'user',
      content: queryText,
      created_at: new Date().toISOString(),
    };
    
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

    api.streamAnswer(
      {
        query: queryText,
        conversation_id: activeConversationId
      },
      (citations, conversationId) => {
        matchingCitations = citations || [];
        if (!activeConversationId && conversationId) {
          setActiveConversationId(conversationId);
        }

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
      async () => {
        setIsChatLoading(false);
        await loadConversations();
      },
      (errorMsg) => {
        console.error("Streaming error:", errorMsg);
        setIsChatLoading(false);
        setMessages(prev => {
          const updated = [...prev];
          const assistantIndex = updated.findIndex(m => m.id === tempAssistantId);
          if (assistantIndex !== -1) {
            updated[assistantIndex] = {
              ...updated[assistantIndex],
              content: `⚠️ LLM inference error: ${errorMsg}. Please verify your Groq API configuration in backend/.env.`
            };
          }
          return updated;
        });
      }
    );
  };

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
      setDocuments(docs || []);
      setApiStatus('online');
    } catch (err) {
      console.error("Failed to load documents", err);
    }
  };

  const onDrop = React.useCallback(async (acceptedFiles) => {
    const file = acceptedFiles[0];
    if (!file) return;
    
    const ext = file.name.split('.').pop()?.toLowerCase();
    if (!['pdf', 'txt', 'md', 'html', 'htm'].includes(ext)) {
      showError("Supported formats: PDF, TXT, Markdown (MD), and HTML files.");
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
      'text/markdown': ['.md'],
      'text/html': ['.html', '.htm']
    },
    multiple: false,
    disabled: isUploading
  });

  const handleDelete = async (docId, e) => {
    e.stopPropagation();
    if (!window.confirm("Delete this document and all its indexed vectors, connections, and memories?")) return;
    try {
      await api.deleteDocument(docId);
      if (selectedDocId === docId) setSelectedDocId(null);
      await loadDocuments();
    } catch (err) {
      showError("Failed to delete document.");
    }
  };

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

  const handlePageChange = (newPage) => {
    if (newPage < 1 || newPage > totalPages || newPage === currentPage) return;
    if (activeSearchQuery) {
      executeSearch(activeSearchQuery, newPage, selectedDocTypes, startDate, endDate, pageSize);
    }
  };

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

  const resetFilters = () => {
    setSelectedDocTypes([]);
    setStartDate('');
    setEndDate('');
    if (activeSearchQuery) {
      executeSearch(activeSearchQuery, 1, [], '', '', pageSize);
    }
  };

  const toggleRelated = (chunkId) => {
    setExpandedRelated(prev => ({
      ...prev,
      [chunkId]: !prev[chunkId]
    }));
  };

  const handleGenerateInsight = async (insightType, customInstruction = '') => {
    if (!selectedDocId) {
      showError("Please select a document from the library to analyze.");
      return;
    }

    setIsGenerating(true);
    setErrorMessage('');
    try {
      await api.generateInsight(selectedDocId, insightType, customInstruction);
      await loadDocuments();
    } catch (err) {
      showError(err.response?.data?.detail || "Failed to generate insight. Verify your Groq configurations.");
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
  const totalChunksCount = documents.reduce((acc, doc) => acc + (doc.chunk_count || 0), 0);
  const indexedDocs = documents.filter(d => d.status === 'indexed');
  const memoriesCount = documents.reduce((acc, doc) => acc + (doc.memories?.length || 0), 0);

  return (
    <div className="min-h-screen flex bg-bg-warm text-text-primary font-sans antialiased">
      
      {/* 📚 Left Sidebar */}
      <aside className="w-64 bg-sidebar-warm border-r border-accent-secondary p-6 flex flex-col justify-between shrink-0">
        <div className="space-y-8">
          
          {/* Logo Area */}
          <div className="flex items-center gap-3">
            <div className="h-9 w-9 rounded-xl bg-accent-primary flex items-center justify-center shadow-sm">
              <svg className="h-5 w-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
              </svg>
            </div>
            <div>
              <h2 className="font-serif font-bold text-base leading-tight text-text-primary">Guardian</h2>
              <p className="text-[10px] text-text-secondary tracking-widest uppercase">Personal Intelligence</p>
            </div>
          </div>

          {/* Navigation Items */}
          <nav className="space-y-1">
            <button
              onClick={() => setActiveTab('library')}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-xs font-semibold transition-all cursor-pointer ${
                activeTab === 'library'
                  ? 'bg-accent-secondary/60 text-text-primary shadow-xs'
                  : 'text-text-secondary hover:bg-accent-secondary/30 hover:text-text-primary'
              }`}
            >
              <span>📚</span>
              <span>Library</span>
            </button>
            <button
              onClick={() => setActiveTab('search')}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-xs font-semibold transition-all cursor-pointer ${
                activeTab === 'search'
                  ? 'bg-accent-secondary/60 text-text-primary shadow-xs'
                  : 'text-text-secondary hover:bg-accent-secondary/30 hover:text-text-primary'
              }`}
            >
              <span>🔍</span>
              <span>Advanced Search</span>
            </button>
            <button
              onClick={() => setActiveTab('chat')}
              className={`w-full flex items-center justify-between px-3 py-2.5 rounded-xl text-xs font-semibold transition-all cursor-pointer ${
                activeTab === 'chat'
                  ? 'bg-accent-secondary/60 text-text-primary shadow-xs'
                  : 'text-text-secondary hover:bg-accent-secondary/30 hover:text-text-primary'
              }`}
            >
              <div className="flex items-center gap-3">
                <span>💬</span>
                <span>Study Chat</span>
              </div>
            </button>
            <button
              onClick={() => setActiveTab('connections')}
              className={`w-full flex items-center justify-between px-3 py-2.5 rounded-xl text-xs font-semibold transition-all cursor-pointer ${
                activeTab === 'connections'
                  ? 'bg-accent-secondary/60 text-text-primary shadow-xs'
                  : 'text-text-secondary hover:bg-accent-secondary/30 hover:text-text-primary'
              }`}
            >
              <div className="flex items-center gap-3">
                <span>🔗</span>
                <span>Connections</span>
              </div>
              <span className="h-2 w-2 rounded-full bg-status-success" title="Cross-document relationships active"></span>
            </button>
            <button
              onClick={() => setActiveTab('flashcards')}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-xs font-semibold transition-all cursor-pointer ${
                activeTab === 'flashcards'
                  ? 'bg-accent-secondary/60 text-text-primary shadow-xs'
                  : 'text-text-secondary hover:bg-accent-secondary/30 hover:text-text-primary'
              }`}
            >
              <span>🗂️</span>
              <span>Flashcards</span>
            </button>
            <button
              onClick={() => setActiveTab('insights')}
              className={`w-full flex items-center justify-between px-3 py-2.5 rounded-xl text-xs font-semibold transition-all cursor-pointer ${
                activeTab === 'insights'
                  ? 'bg-accent-secondary/60 text-text-primary shadow-xs'
                  : 'text-text-secondary hover:bg-accent-secondary/30 hover:text-text-primary'
              }`}
            >
              <div className="flex items-center gap-3">
                <span>🔮</span>
                <span>Memory & Patterns</span>
              </div>
            </button>
            <button
              onClick={() => setActiveTab('stats')}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-xs font-semibold transition-all cursor-pointer ${
                activeTab === 'stats'
                  ? 'bg-accent-secondary/60 text-text-primary shadow-xs'
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
            <span className="text-text-secondary">Backend Engine</span>
            <div className="flex items-center gap-1.5">
              <span className={`h-2 w-2 rounded-full ${apiStatus === 'online' ? 'bg-status-success' : 'bg-status-error'}`}></span>
              <span className="text-[11px] font-medium capitalize text-text-secondary">{apiStatus}</span>
            </div>
          </div>
          <p className="text-[10px] text-text-muted">Hybrid: FAISS + BM25 (RRF)</p>
          <p className="text-[10px] text-text-muted">LLM: Groq (gpt-oss-120b)</p>
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
              {activeTab === 'search' && 'Advanced Hybrid Retrieval'}
              {activeTab === 'chat' && 'Conversational Study Chat'}
              {activeTab === 'connections' && 'Cross-Document Intelligence'}
              {activeTab === 'flashcards' && 'Source-Grounded Flashcards'}
              {activeTab === 'insights' && 'Persistent Memory & Patterns'}
              {activeTab === 'stats' && 'System Analytics & Metrics'}
            </h1>
          </div>

          <div className="flex items-center gap-2">
            <a
              href={api.getExportResearchNotesUrl()}
              download
              className="px-3.5 py-2.5 rounded-xl bg-white border border-accent-secondary/60 hover:bg-bg-warm text-text-primary text-xs font-semibold flex items-center gap-1.5 cursor-pointer transition-all shadow-2xs"
              title="Download full library research synthesis in Markdown format"
            >
              <span>📥</span>
              <span>Export Master Notes</span>
            </a>
            <button
              onClick={() => setShowUploadModal(true)}
              className="bg-accent-primary hover:bg-accent-tertiary text-white font-semibold text-xs px-4 py-2.5 rounded-xl transition-all shadow-sm flex items-center gap-2 cursor-pointer"
            >
              <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
              </svg>
              Ingest Document (PDF, TXT, MD, HTML)
            </button>
          </div>
        </header>

        {errorMessage && (
          <div className="mb-4 bg-status-error/10 border border-status-error/20 text-status-error text-xs px-4 py-2.5 rounded-xl flex items-center justify-between shrink-0">
            <span>{errorMessage}</span>
            <button onClick={() => setErrorMessage('')} className="hover:opacity-85 text-sm cursor-pointer">&times;</button>
          </div>
        )}

        {/* Tab 1: Library View */}
        {activeTab === 'library' && (
          <div className="flex-1 overflow-y-auto space-y-8 pr-1">
            <div>
              <h1 className="font-serif text-2xl font-bold text-text-primary tracking-tight">Your Research Library</h1>
              <p className="text-xs text-text-secondary mt-1">Uploaded papers are parsed, chunked, and indexed with hybrid FAISS and BM25.</p>
            </div>

            {/* Quick Metrics */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="bg-white border border-accent-secondary/50 rounded-2xl p-4 shadow-[0_2px_8px_rgba(0,0,0,0.02)]">
                <span className="text-[10px] text-text-muted uppercase tracking-wider block font-semibold">Total Documents</span>
                <span className="text-xl font-bold font-serif text-text-primary mt-1 block">{documents.length}</span>
              </div>
              <div className="bg-white border border-accent-secondary/50 rounded-2xl p-4 shadow-[0_2px_8px_rgba(0,0,0,0.02)]">
                <span className="text-[10px] text-text-muted uppercase tracking-wider block font-semibold">Connected Insights</span>
                <span className="text-xl font-bold font-serif text-text-primary mt-1 block">{memoriesCount}</span>
              </div>
              <div className="bg-white border border-accent-secondary/50 rounded-2xl p-4 shadow-[0_2px_8px_rgba(0,0,0,0.02)]">
                <span className="text-[10px] text-text-muted uppercase tracking-wider block font-semibold">Indexed Chunks</span>
                <span className="text-xl font-bold font-serif text-text-primary mt-1 block">{indexedDocs.length > 0 ? totalChunksCount : 0}</span>
              </div>
              <div className="bg-white border border-accent-secondary/50 rounded-2xl p-4 shadow-[0_2px_8px_rgba(0,0,0,0.02)]">
                <span className="text-[10px] text-text-muted uppercase tracking-wider block font-semibold">Active Memory</span>
                <span className="text-xl font-bold font-serif text-text-primary mt-1 block">
                  {memoriesCount > 0 ? `${memoriesCount} Units` : '0 Units'}
                </span>
              </div>
            </div>

            {/* Documents Grid */}
            <div className="space-y-4">
              <h3 className="font-serif text-lg font-bold text-text-primary">All Documents</h3>
              {documents.length === 0 ? (
                <div className="h-60 rounded-2xl border border-dashed border-accent-secondary bg-white flex flex-col items-center justify-center text-center p-6">
                  <span className="text-3xl mb-2">📚</span>
                  <p className="text-sm font-serif font-semibold text-text-primary">Your library is currently empty</p>
                  <p className="text-xs text-text-secondary mt-1">Upload research documents above to begin proactive indexing.</p>
                </div>
              ) : (
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
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
                        className="bg-white border border-accent-secondary/40 rounded-2xl p-5 flex flex-col justify-between hover:shadow-md hover:border-accent-primary/60 transition-all duration-200 group"
                      >
                        <div>
                          <div className="flex items-start justify-between gap-2 mb-2">
                            <span className="text-xs font-semibold px-2 py-0.5 rounded bg-bg-warm text-accent-tertiary font-mono">{ext}</span>
                            <button
                              onClick={(e) => handleDelete(doc.id, e)}
                              className="opacity-0 group-hover:opacity-100 text-text-muted hover:text-status-error transition-all p-1 rounded hover:bg-bg-warm cursor-pointer"
                              title="Delete document and purge vectors"
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
                          <span
                            className={`px-2 py-0.5 rounded-full border text-[10px] uppercase font-bold tracking-wider ${statusStyles[doc.status] || 'bg-bg-warm text-text-secondary'}`}
                            title={doc.error_detail || (doc.status === 'processing' ? `Current Stage: ${doc.processing_stage || 'processing'}` : '')}
                          >
                            {doc.status === 'processing' && doc.processing_stage
                              ? `${doc.processing_stage}...`
                              : doc.status === 'failed' && doc.error_detail
                              ? 'Failed (Inspect)'
                              : doc.status}
                          </span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        )}

        {/* Tab 2: Advanced Search View */}
        {activeTab === 'search' && (
          <AdvancedSearch
            searchQuery={searchQuery}
            setSearchQuery={setSearchQuery}
            activeSearchQuery={activeSearchQuery}
            selectedDocTypes={selectedDocTypes}
            toggleDocTypeFilter={toggleDocTypeFilter}
            startDate={startDate}
            setStartDate={setStartDate}
            endDate={endDate}
            setEndDate={setEndDate}
            resetFilters={resetFilters}
            searchResults={searchResults}
            totalResults={totalResults}
            currentPage={currentPage}
            pageSize={pageSize}
            setPageSize={setPageSize}
            totalPages={totalPages}
            handlePageChange={handlePageChange}
            isSearching={isSearching}
            expandedRelated={expandedRelated}
            toggleRelated={toggleRelated}
            onSearch={executeSearch}
          />
        )}

        {/* Tab 3: Study Chat View */}
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

        {/* Tab 4: Cross-Document Connections View */}
        {activeTab === 'connections' && (
          <ConnectionsView documents={documents} />
        )}

        {/* Tab 5: Flashcards View */}
        {activeTab === 'flashcards' && (
          <FlashcardsView documents={documents} />
        )}

        {/* Tab 6: Memory & Patterns View */}
        {activeTab === 'insights' && (
          <MemoryPatternsView
            documents={documents}
            selectedDocId={selectedDocId}
            setSelectedDocId={setSelectedDocId}
            onGenerateInsight={handleGenerateInsight}
            isGenerating={isGenerating}
          />
        )}

        {/* Tab 7: Statistics & Telemetry View */}
        {activeTab === 'stats' && (
          <SystemMetricsView />
        )}

      </div>

      {/* Upload Modal (PDF, TXT, MD) */}
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
                    <svg className="animate-spin h-6 w-6 text-accent-primary" fill="none" viewBox="0 0 24 24">
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
