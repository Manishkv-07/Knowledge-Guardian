import React, { useState, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import { useDropzone } from 'react-dropzone';
import { api } from './services/api';
import Search from './components/Search';

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
  const [activeTab, setActiveTab] = useState('library'); // 'library' | 'search' | 'chat' | 'insights' | 'stats'
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
  const [errorMessage, setErrorMessage] = useState('');
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [chatHistory, setChatHistory] = useState([
    {
      role: 'assistant',
      content: 'Welcome to your digital study room. I am your Knowledge Guardian. Upload your research papers, notes, or textbooks, and ask questions. I will recall relevant passages and help connect the dots.',
      citations: []
    }
  ]);

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

  const handleSearchSubmit = async (e) => {
    if (e) e.preventDefault();
    if (!searchQuery.trim()) return;

    const queryText = searchQuery;
    setSearchQuery(''); // clear input field

    // Add user query to chat history
    setChatHistory(prev => [...prev, { role: 'user', content: queryText }]);

    const { items, total } = await executeSearch(
      queryText,
      1,
      selectedDocTypes,
      startDate,
      endDate,
      pageSize
    );

    // Formulate structured assistant response
    let replyContent = "";
    if (items.length === 0) {
      replyContent = "I searched through your knowledge base, but I couldn't find any relevant passages matching your query and active filters. Make sure your documents are fully indexed or try broadening your filters.";
    } else {
      replyContent = `Based on your library, here are relevant passages (found ${total} total match${total > 1 ? 'es' : ''}):\n\n` + 
        items.map((res) => `• **From ${res.document_name}**:\n  > ${res.chunk.trim()}`).join("\n\n");
    }

    setChatHistory(prev => [...prev, {
      role: 'assistant',
      content: replyContent,
      citations: items.map(r => r.document_name)
    }]);
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
              onClick={() => setActiveTab('search')}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all ${
                activeTab === 'search'
                  ? 'bg-accent-secondary/60 text-text-primary shadow-sm font-semibold'
                  : 'text-text-secondary hover:bg-accent-secondary/30 hover:text-text-primary'
              }`}
            >
              <span>🔍</span>
              <span>Search Knowledge</span>
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

        {/* 💬 Tab 2: Study Chat / Ask View with Advanced Search */}
        {activeTab === 'chat' && (
          <div className="flex-1 flex overflow-hidden gap-6">
            
            {/* Chat & Query Thread */}
            <div className="flex-1 flex flex-col justify-between bg-white border border-accent-secondary/50 rounded-2xl shadow-[0_4px_12px_rgba(0,0,0,0.02)] overflow-hidden">
              
              {/* Chat messages */}
              <div className="flex-1 overflow-y-auto p-6 space-y-5">
                {chatHistory.map((chat, idx) => (
                  <div
                    key={idx}
                    className={`flex ${chat.role === 'user' ? 'justify-end' : 'justify-start'}`}
                  >
                    <div
                      className={`max-w-[80%] rounded-2xl px-5 py-3.5 text-sm leading-relaxed shadow-sm ${
                        chat.role === 'user'
                          ? 'bg-sidebar-warm text-text-primary font-medium border border-accent-secondary/50 rounded-tr-none'
                          : 'bg-white border border-accent-secondary/60 text-text-primary rounded-tl-none'
                      }`}
                    >
                      <div className="markdown-body text-text-primary space-y-1 text-sm leading-relaxed">
                        <ReactMarkdown>{chat.content}</ReactMarkdown>
                      </div>
                      
                      {chat.citations && chat.citations.length > 0 && (
                        <div className="mt-3 pt-2.5 border-t border-bg-warm flex flex-wrap gap-1.5 items-center">
                          <span className="text-[10px] text-text-muted uppercase font-bold tracking-wider">Citations:</span>
                          {Array.from(new Set(chat.citations)).map((docName, i) => (
                            <span key={i} className="text-[10px] font-medium bg-bg-warm text-accent-tertiary px-2 py-0.5 rounded border border-accent-secondary/40 max-w-[170px] truncate" title={docName}>
                              📖 {docName}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                ))}
                {isSearching && (
                  <div className="flex justify-start">
                    <div className="bg-white border border-accent-secondary/60 rounded-2xl rounded-tl-none px-5 py-3.5 shadow-sm flex items-center gap-2 text-xs text-text-secondary">
                      <svg className="animate-spin h-4 w-4 text-accent-primary" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                      </svg>
                      Searching knowledge base with active filters...
                    </div>
                  </div>
                )}
              </div>

              {/* Chat Input & Filter Controls */}
              <div className="border-t border-accent-secondary/60 bg-sidebar-warm/20 p-4 space-y-3">
                
                {/* Search Filter Header / Quick Toggles */}
                <div className="flex items-center justify-between text-xs">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-[11px] font-bold text-text-secondary uppercase tracking-wider flex items-center gap-1">
                      <svg className="h-3.5 w-3.5 text-accent-primary" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z" />
                      </svg>
                      Doc Types:
                    </span>
                    <button
                      type="button"
                      onClick={() => { setSelectedDocTypes([]); if (activeSearchQuery) executeSearch(activeSearchQuery, 1, [], startDate, endDate, pageSize); }}
                      className={`px-2.5 py-1 rounded-md text-[11px] font-semibold transition-all cursor-pointer ${
                        selectedDocTypes.length === 0
                          ? 'bg-accent-primary text-white shadow-xs'
                          : 'bg-white text-text-secondary border border-accent-secondary/50 hover:bg-bg-warm'
                      }`}
                    >
                      All Types
                    </button>
                    {['pdf', 'txt', 'md'].map((type) => {
                      const isActive = selectedDocTypes.includes(type);
                      return (
                        <button
                          key={type}
                          type="button"
                          onClick={() => toggleDocTypeFilter(type)}
                          className={`px-2.5 py-1 rounded-md text-[11px] font-semibold uppercase transition-all cursor-pointer ${
                            isActive
                              ? 'bg-accent-primary text-white shadow-xs'
                              : 'bg-white text-text-secondary border border-accent-secondary/50 hover:bg-bg-warm'
                          }`}
                        >
                          {type}
                        </button>
                      );
                    })}
                  </div>

                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={() => setShowFilterPanel(!showFilterPanel)}
                      className="text-[11px] font-semibold text-accent-tertiary hover:text-accent-primary flex items-center gap-1 cursor-pointer"
                    >
                      <span>📅 Date Filters</span>
                      <span>{showFilterPanel ? '▲' : '▼'}</span>
                    </button>

                    {hasActiveFilters && (
                      <button
                        type="button"
                        onClick={resetFilters}
                        className="text-[10px] font-bold text-status-error hover:underline cursor-pointer ml-2"
                      >
                        Reset All
                      </button>
                    )}
                  </div>
                </div>

                {/* Expanded Date Range Filter Drawer */}
                {showFilterPanel && (
                  <div className="bg-white border border-accent-secondary/50 rounded-xl p-3 grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs shadow-xs">
                    <div className="space-y-1">
                      <label className="text-[10px] font-bold text-text-secondary uppercase tracking-wider block">From Date</label>
                      <input
                        type="date"
                        value={startDate}
                        onChange={(e) => {
                          setStartDate(e.target.value);
                          if (activeSearchQuery) executeSearch(activeSearchQuery, 1, selectedDocTypes, e.target.value, endDate, pageSize);
                        }}
                        className="w-full bg-bg-warm border border-accent-secondary/60 rounded-lg px-2.5 py-1.5 text-xs text-text-primary outline-none focus:border-accent-primary"
                      />
                    </div>
                    <div className="space-y-1">
                      <label className="text-[10px] font-bold text-text-secondary uppercase tracking-wider block">To Date</label>
                      <input
                        type="date"
                        value={endDate}
                        onChange={(e) => {
                          setEndDate(e.target.value);
                          if (activeSearchQuery) executeSearch(activeSearchQuery, 1, selectedDocTypes, startDate, e.target.value, pageSize);
                        }}
                        className="w-full bg-bg-warm border border-accent-secondary/60 rounded-lg px-2.5 py-1.5 text-xs text-text-primary outline-none focus:border-accent-primary"
                      />
                    </div>
                  </div>
                )}

                {/* Input Form */}
                <form onSubmit={handleSearchSubmit} className="flex gap-2">
                  <input
                    type="text"
                    placeholder="Ask a question or search for concepts (e.g. 'Transformer attention', 'FAISS vectors')..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="flex-1 bg-white border border-accent-secondary focus:border-accent-primary focus:ring-1 focus:ring-accent-primary rounded-xl px-4 py-3 text-sm outline-none transition-all placeholder-text-muted"
                  />
                  <button
                    type="submit"
                    disabled={isSearching || !searchQuery.trim()}
                    className="bg-accent-primary hover:bg-accent-tertiary disabled:opacity-40 text-white font-medium text-sm px-6 py-3 rounded-xl transition-all duration-200 shadow-sm flex items-center gap-1 shrink-0 cursor-pointer"
                  >
                    Search
                  </button>
                </form>
              </div>
            </div>

            {/* Context & Advanced Search Results Sidebar */}
            <div className="w-96 bg-white border border-accent-secondary/50 rounded-2xl p-5 shadow-[0_4px_12px_rgba(0,0,0,0.02)] flex flex-col shrink-0 overflow-hidden">
              
              {/* Header with Result Count */}
              <div className="flex items-center justify-between border-b border-bg-warm pb-3">
                <div>
                  <h3 className="font-serif text-sm font-bold text-text-primary">Retrieved Passages</h3>
                  <p className="text-[10px] text-text-secondary">
                    {totalResults > 0 ? `${totalResults} match${totalResults > 1 ? 'es' : ''} found` : 'Semantic vector matches'}
                  </p>
                </div>
                {activeSearchQuery && (
                  <span className="text-[10px] px-2 py-0.5 rounded bg-accent-secondary/50 text-accent-tertiary font-mono truncate max-w-[120px]" title={activeSearchQuery}>
                    "{activeSearchQuery}"
                  </span>
                )}
              </div>

              {/* Result List with Highlighting and Related Chunks */}
              <div className="flex-1 overflow-y-auto mt-4 space-y-4 pr-1">
                {searchResults.length === 0 ? (
                  <div className="h-full flex flex-col items-center justify-center text-center p-4 space-y-2">
                    <svg className="h-8 w-8 text-text-muted opacity-50" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                    </svg>
                    <p className="text-xs text-text-muted">Enter a query to retrieve highlighted passages with citations & related sections.</p>
                  </div>
                ) : (
                  searchResults.map((res, i) => {
                    const chunkId = res.chunk_id || `res_${i}`;
                    const isExpanded = !!expandedRelated[chunkId];
                    const docType = res.doc_type || res.document_name.split('.').pop()?.toLowerCase() || 'txt';
                    const hasRelated = res.related_chunks && res.related_chunks.length > 0;

                    return (
                      <div key={chunkId} className="bg-bg-warm/50 border border-accent-secondary/40 rounded-xl p-3.5 space-y-2.5 text-xs shadow-2xs">
                        
                        {/* Result Header */}
                        <div className="flex items-center justify-between text-[10px] text-text-secondary gap-1">
                          <div className="flex items-center gap-1.5 truncate">
                            <span className="px-1.5 py-0.5 rounded bg-accent-secondary/60 text-accent-tertiary font-mono uppercase font-bold text-[9px]">
                              {docType}
                            </span>
                            <span className="font-semibold text-text-primary truncate" title={res.document_name}>
                              {res.document_name}
                            </span>
                          </div>
                          <span className="bg-white px-2 py-0.5 rounded border border-accent-secondary/40 font-mono text-[10px] shrink-0 text-text-secondary">
                            Score: {(res.similarity ? res.similarity * 100 : (1.0 / (1.0 + res.score)) * 100).toFixed(1)}%
                          </span>
                        </div>

                        {/* Highlighted Chunk Text */}
                        <div className="text-text-primary leading-relaxed font-serif text-[11px] bg-white p-3 rounded-lg border border-accent-secondary/30">
                          <HighlightText text={res.chunk.trim()} query={activeSearchQuery} />
                        </div>

                        {/* Task 4: Related Chunks from Same Document */}
                        {hasRelated && (
                          <div className="pt-1">
                            <button
                              type="button"
                              onClick={() => toggleRelated(chunkId)}
                              className="w-full flex items-center justify-between text-[10px] font-semibold text-accent-tertiary hover:text-accent-primary py-1 px-1.5 rounded hover:bg-white/80 transition-colors cursor-pointer"
                            >
                              <span className="flex items-center gap-1">
                                <span>🔗</span>
                                <span>Related from this document ({res.related_chunks.length})</span>
                              </span>
                              <span>{isExpanded ? '▲ Hide' : '▼ View'}</span>
                            </button>

                            {isExpanded && (
                              <div className="mt-2 space-y-2 pl-2 border-l-2 border-accent-primary/40">
                                {res.related_chunks.map((rel, rIdx) => (
                                  <div key={rIdx} className="bg-white/90 p-2.5 rounded border border-accent-secondary/30 text-[10px] space-y-1">
                                    <div className="flex items-center justify-between text-text-muted font-mono text-[9px]">
                                      <span>Section #{rel.chunk_index + 1}</span>
                                      <span className="text-accent-tertiary">Context match</span>
                                    </div>
                                    <p className="text-text-primary font-serif italic line-clamp-3 leading-relaxed">
                                      <HighlightText text={rel.text.trim()} query={activeSearchQuery} />
                                    </p>
                                  </div>
                                ))}
                              </div>
                            )}
                          </div>
                        )}

                      </div>
                    );
                  })
                )}
              </div>

              {/* Task 3: Pagination Controls Bar */}
              {totalResults > 0 && totalPages > 1 && (
                <div className="mt-3 pt-3 border-t border-bg-warm flex items-center justify-between text-xs shrink-0">
                  <button
                    type="button"
                    onClick={() => handlePageChange(currentPage - 1)}
                    disabled={currentPage === 1 || isSearching}
                    className="px-2.5 py-1 rounded bg-bg-warm hover:bg-accent-secondary/40 disabled:opacity-30 border border-accent-secondary/50 text-[11px] font-semibold transition-all cursor-pointer"
                  >
                    ‹ Prev
                  </button>

                  <div className="flex items-center gap-1">
                    {Array.from({ length: totalPages }, (_, i) => i + 1).map((p) => (
                      <button
                        key={p}
                        type="button"
                        onClick={() => handlePageChange(p)}
                        className={`h-6 w-6 rounded text-[11px] font-bold transition-all cursor-pointer ${
                          currentPage === p
                            ? 'bg-accent-primary text-white shadow-xs'
                            : 'bg-bg-warm text-text-secondary hover:bg-accent-secondary/30'
                        }`}
                      >
                        {p}
                      </button>
                    ))}
                  </div>

                  <button
                    type="button"
                    onClick={() => handlePageChange(currentPage + 1)}
                    disabled={currentPage >= totalPages || isSearching}
                    className="px-2.5 py-1 rounded bg-bg-warm hover:bg-accent-secondary/40 disabled:opacity-30 border border-accent-secondary/50 text-[11px] font-semibold transition-all cursor-pointer"
                  >
                    Next ›
                  </button>
                </div>
              )}

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

        {/* 🔍 Tab 5: Search Knowledge View */}
        {activeTab === 'search' && (
          <Search />
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
