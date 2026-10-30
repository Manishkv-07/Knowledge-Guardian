import React, { useState, useEffect } from 'react';
import { api } from '../services/api';

export default function SystemMetricsView() {
  const [metrics, setMetrics] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');

  const loadMetrics = async () => {
    setIsLoading(true);
    setError('');
    try {
      const data = await api.getStats();
      setMetrics(data);
    } catch (err) {
      console.error("Failed to load metrics:", err);
      setError("Unable to retrieve system runtime metrics.");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadMetrics();
  }, []);

  if (isLoading && !metrics) {
    return (
      <div className="h-64 flex flex-col items-center justify-center gap-3 bg-white border border-accent-secondary/40 rounded-2xl">
        <svg className="animate-spin h-6 w-6 text-accent-primary" fill="none" viewBox="0 0 24 24">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
        </svg>
        <span className="text-xs text-text-secondary font-semibold">Measuring system metrics and index consistency...</span>
      </div>
    );
  }

  if (error && !metrics) {
    return (
      <div className="bg-status-error/10 border border-status-error/30 text-status-error p-6 rounded-2xl text-xs space-y-2">
        <p className="font-bold">{error}</p>
        <button
          onClick={loadMetrics}
          className="px-3 py-1 bg-white border border-status-error/40 rounded-lg text-text-primary text-xs cursor-pointer"
        >
          Retry
        </button>
      </div>
    );
  }

  const docs = metrics?.documents || {};
  const vs = metrics?.vector_store || {};
  const intel = metrics?.intelligence || {};
  const llm = metrics?.llm_provider || {};
  const failures = metrics?.recent_failures || [];

  return (
    <div className="flex-1 overflow-y-auto space-y-6 pr-1">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-serif text-2xl font-bold text-text-primary tracking-tight">System Architecture & Index Telemetry</h1>
          <p className="text-xs text-text-secondary mt-1">
            Real observable properties from SQLite, FAISS CPU, BM25Okapi, and GroqCloud runtime.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={loadMetrics}
            disabled={isLoading}
            className="px-3 py-1.5 rounded-xl bg-white border border-accent-secondary/60 hover:bg-bg-warm text-xs font-semibold text-text-primary flex items-center gap-1.5 cursor-pointer transition-all"
          >
            <span>🔄</span>
            <span>Refresh Telemetry</span>
          </button>
          <a
            href={api.getExportResearchNotesUrl()}
            download
            className="px-3.5 py-1.5 rounded-xl bg-accent-primary hover:bg-accent-tertiary text-white text-xs font-semibold flex items-center gap-1.5 shadow-xs transition-all cursor-pointer"
            title="Download full research notes in Markdown format"
          >
            <span>📥</span>
            <span>Export Master Notes</span>
          </a>
        </div>
      </div>

      {/* Grid of Metric Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Total Documents */}
        <div className="bg-white border border-accent-secondary/50 rounded-2xl p-4 shadow-[0_2px_8px_rgba(0,0,0,0.02)] space-y-1">
          <span className="text-[10px] text-text-muted uppercase font-bold tracking-wider">Repository Documents</span>
          <div className="flex items-baseline gap-2">
            <span className="text-2xl font-bold font-serif text-text-primary">{docs.total ?? 0}</span>
            <span className="text-xs text-status-success font-medium">({docs.indexed ?? 0} indexed)</span>
          </div>
          <span className="text-[10px] text-text-muted block">
            {docs.processing > 0 ? `${docs.processing} processing` : 'All background queues idle'}
          </span>
        </div>

        {/* Vectors & Chunks */}
        <div className="bg-white border border-accent-secondary/50 rounded-2xl p-4 shadow-[0_2px_8px_rgba(0,0,0,0.02)] space-y-1">
          <span className="text-[10px] text-text-muted uppercase font-bold tracking-wider">Indexed Chunks</span>
          <div className="flex items-baseline gap-2">
            <span className="text-2xl font-bold font-serif text-text-primary">{docs.total_chunks ?? 0}</span>
            <span className="text-xs text-text-secondary font-mono">({vs.vector_count ?? 0} vectors)</span>
          </div>
          <div className="flex items-center gap-1">
            <span className={`h-1.5 w-1.5 rounded-full ${vs.is_consistent ? 'bg-status-success' : 'bg-status-error'}`}></span>
            <span className="text-[10px] text-text-muted font-medium">
              {vs.is_consistent ? 'FAISS & SQLite Synchronized' : 'Index Desynchronized'}
            </span>
          </div>
        </div>

        {/* Cross-Document Connections */}
        <div className="bg-white border border-accent-secondary/50 rounded-2xl p-4 shadow-[0_2px_8px_rgba(0,0,0,0.02)] space-y-1">
          <span className="text-[10px] text-text-muted uppercase font-bold tracking-wider">Connections Discovered</span>
          <div className="flex items-baseline gap-2">
            <span className="text-2xl font-bold font-serif text-text-primary">{intel.total_connections ?? 0}</span>
            <span className="text-xs text-status-success font-medium">({intel.saved_connections ?? 0} saved)</span>
          </div>
          <span className="text-[10px] text-text-muted block">
            {intel.dismissed_connections ?? 0} dismissed by user
          </span>
        </div>

        {/* Spaced Repetition Due */}
        <div className="bg-white border border-accent-secondary/50 rounded-2xl p-4 shadow-[0_2px_8px_rgba(0,0,0,0.02)] space-y-1">
          <span className="text-[10px] text-text-muted uppercase font-bold tracking-wider">Flashcard Deck</span>
          <div className="flex items-baseline gap-2">
            <span className="text-2xl font-bold font-serif text-text-primary">{intel.total_flashcards ?? 0}</span>
            <span className="text-xs text-amber-700 font-medium">({intel.due_flashcards ?? 0} due today)</span>
          </div>
          <span className="text-[10px] text-text-muted block">
            SM-2 deterministic intervals
          </span>
        </div>
      </div>

      {/* Detailed Technical Breakdowns */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        
        {/* Vector & Lexical Engine Inspection */}
        <div className="bg-white border border-accent-secondary/50 rounded-2xl p-5 space-y-4 shadow-[0_2px_8px_rgba(0,0,0,0.02)]">
          <div className="flex items-center justify-between border-b border-bg-warm pb-3">
            <h3 className="font-serif text-sm font-bold text-text-primary">Retrieval Engine Health & Verification</h3>
            <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase ${
              vs.is_consistent ? 'bg-status-success/15 text-status-success' : 'bg-status-error/15 text-status-error'
            }`}>
              {vs.is_consistent ? 'Verified Consistent' : 'Desync Detected'}
            </span>
          </div>

          <div className="space-y-2.5 text-xs">
            <div className="flex justify-between py-1 border-b border-bg-warm/60">
              <span className="text-text-secondary">Dense Index Architecture</span>
              <span className="font-mono font-semibold text-text-primary">FAISS IndexFlatL2 (384 Dimensions)</span>
            </div>
            <div className="flex justify-between py-1 border-b border-bg-warm/60">
              <span className="text-text-secondary">FAISS Total Registered Vectors</span>
              <span className="font-mono font-semibold text-text-primary">{vs.vector_count ?? 0}</span>
            </div>
            <div className="flex justify-between py-1 border-b border-bg-warm/60">
              <span className="text-text-secondary">Vector Store Metadata Records</span>
              <span className="font-mono font-semibold text-text-primary">{vs.metadata_count ?? 0}</span>
            </div>
            <div className="flex justify-between py-1 border-b border-bg-warm/60">
              <span className="text-text-secondary">Lexical BM25 Indexed Chunks</span>
              <span className="font-mono font-semibold text-text-primary">{vs.bm25_corpus_size ?? 0}</span>
            </div>
            <div className="flex justify-between py-1">
              <span className="text-text-secondary">Rank Fusion Algorithm</span>
              <span className="font-mono font-semibold text-text-primary">Reciprocal Rank Fusion (k=60)</span>
            </div>
          </div>
        </div>

        {/* Intelligence, Persistence & LLM Health */}
        <div className="bg-white border border-accent-secondary/50 rounded-2xl p-5 space-y-4 shadow-[0_2px_8px_rgba(0,0,0,0.02)]">
          <div className="flex items-center justify-between border-b border-bg-warm pb-3">
            <h3 className="font-serif text-sm font-bold text-text-primary">Intelligence & LLM Provider Status</h3>
            <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase ${
              llm.is_configured ? 'bg-status-success/15 text-status-success' : 'bg-amber-100 text-amber-800'
            }`}>
              {llm.is_configured ? 'Groq Active' : 'Unconfigured'}
            </span>
          </div>

          <div className="space-y-2.5 text-xs">
            <div className="flex justify-between py-1 border-b border-bg-warm/60">
              <span className="text-text-secondary">Primary LLM Provider</span>
              <span className="font-mono font-semibold text-text-primary">GroqCloud (LangChain ChatGroq)</span>
            </div>
            <div className="flex justify-between py-1 border-b border-bg-warm/60">
              <span className="text-text-secondary">Model ID</span>
              <span className="font-mono font-semibold text-text-primary">{llm.model || 'openai/gpt-oss-120b'}</span>
            </div>
            <div className="flex justify-between py-1 border-b border-bg-warm/60">
              <span className="text-text-secondary">API Key Configuration</span>
              <span className="font-mono font-semibold text-text-primary">
                {llm.is_configured ? (llm.masked_key || 'Configured (Masked)') : 'Missing in .env'}
              </span>
            </div>
            <div className="flex justify-between py-1 border-b border-bg-warm/60">
              <span className="text-text-secondary">Active Cognitive Patterns</span>
              <span className="font-mono font-semibold text-text-primary">{intel.active_pattern_memories ?? 0}</span>
            </div>
            <div className="flex justify-between py-1">
              <span className="text-text-secondary">Synthesized Fact Memories</span>
              <span className="font-mono font-semibold text-text-primary">{intel.stored_fact_memories ?? 0}</span>
            </div>
          </div>
        </div>

      </div>

      {/* Recent Ingestion Failures Table (if any) */}
      {failures.length > 0 && (
        <div className="bg-white border border-status-error/30 rounded-2xl p-5 space-y-3">
          <h3 className="font-serif text-sm font-bold text-status-error flex items-center gap-1.5">
            <span>⚠️</span>
            <span>Recent Ingestion Warnings & Failures</span>
          </h3>
          <div className="divide-y divide-bg-warm text-xs">
            {failures.map((f) => (
              <div key={f.id} className="py-2.5 flex items-center justify-between gap-4">
                <div>
                  <span className="font-serif font-bold text-text-primary block">{f.filename}</span>
                  <span className="text-status-error text-[11px] block">{f.error_detail}</span>
                </div>
                <span className="text-[10px] text-text-muted font-mono">{f.upload_time?.slice(0, 16)}</span>
              </div>
            ))}
          </div>
        </div>
      )}

    </div>
  );
}
