import React, { useState, useEffect } from 'react';
import { api } from '../services/api';
import KnowledgeGraphView from './KnowledgeGraphView';

const RELATIONSHIP_BADGES = {
  SUPPORTS: {
    bg: 'bg-emerald-50 text-emerald-800 border-emerald-300',
    icon: '✅',
    label: 'SUPPORTS'
  },
  CONTRADICTS: {
    bg: 'bg-rose-50 text-rose-800 border-rose-300',
    icon: '⚡',
    label: 'CONTRADICTS'
  },
  EXTENDS: {
    bg: 'bg-indigo-50 text-indigo-800 border-indigo-300',
    icon: '📈',
    label: 'EXTENDS'
  },
  SIMILAR: {
    bg: 'bg-sky-50 text-sky-800 border-sky-300',
    icon: '🔄',
    label: 'SIMILAR TOPIC'
  },
  ANSWERS: {
    bg: 'bg-purple-50 text-purple-800 border-purple-300',
    icon: '💡',
    label: 'ANSWERS CLAIM'
  },
  RELATED: {
    bg: 'bg-amber-50 text-amber-800 border-amber-300',
    icon: '🔗',
    label: 'RELATED'
  }
};

export default function ConnectionsView({ documents = [] }) {
  const [connections, setConnections] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isDiscovering, setIsDiscovering] = useState(false);
  const [typeFilter, setTypeFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [selectedDocFilter, setSelectedDocFilter] = useState('');
  const [message, setMessage] = useState('');
  const [viewMode, setViewMode] = useState('list'); // 'list' | 'graph'

  const loadConnections = async () => {
    setIsLoading(true);
    try {
      const params = {};
      if (typeFilter) params.relationship_type = typeFilter;
      if (statusFilter) params.status = statusFilter;
      if (selectedDocFilter) params.document_id = selectedDocFilter;

      const data = await api.getConnections(params);
      setConnections(data || []);
    } catch (err) {
      console.error("Failed to load connections:", err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadConnections();
  }, [typeFilter, statusFilter, selectedDocFilter]);

  const handleUpdateStatus = async (connId, newStatus) => {
    try {
      await api.updateConnection(connId, { status: newStatus });
      await loadConnections();
      setMessage(`Connection marked as ${newStatus}.`);
      setTimeout(() => setMessage(''), 3000);
    } catch (err) {
      console.error("Failed to update status:", err);
    }
  };

  const handleDelete = async (connId) => {
    if (!window.confirm("Delete this connection?")) return;
    try {
      await api.deleteConnection(connId);
      await loadConnections();
    } catch (err) {
      console.error("Failed to delete connection:", err);
    }
  };

  const handleRunDiscovery = async () => {
    setIsDiscovering(true);
    setMessage('');
    try {
      const docId = selectedDocFilter ? parseInt(selectedDocFilter) : null;
      const discovered = await api.discoverConnections(docId);
      await loadConnections();
      setMessage(`Discovery complete: found ${discovered.length} connection(s).`);
      setTimeout(() => setMessage(''), 5000);
    } catch (err) {
      setMessage("Connection discovery failed. Verify Groq API key configuration.");
    } finally {
      setIsDiscovering(false);
    }
  };

  return (
    <div className="flex-1 overflow-y-auto space-y-6 pr-1">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="font-serif text-2xl font-bold text-text-primary tracking-tight">Cross-Document Intelligence</h1>
          <p className="text-xs text-text-secondary mt-1">
            Proactively discovering grounded relationships, supporting claims, and contradictions between your papers.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {/* View Mode Toggle: List vs Graph */}
          <div className="flex bg-white p-1 rounded-xl border border-accent-secondary/60 text-xs shadow-2xs">
            <button
              onClick={() => setViewMode('list')}
              className={`px-3 py-1.5 rounded-lg font-semibold transition-all cursor-pointer ${
                viewMode === 'list' ? 'bg-bg-warm text-text-primary shadow-xs' : 'text-text-secondary hover:text-text-primary'
              }`}
            >
              📄 List View
            </button>
            <button
              onClick={() => setViewMode('graph')}
              className={`px-3 py-1.5 rounded-lg font-semibold transition-all cursor-pointer flex items-center gap-1 ${
                viewMode === 'graph' ? 'bg-bg-warm text-text-primary shadow-xs' : 'text-text-secondary hover:text-text-primary'
              }`}
            >
              <span>🕸️</span>
              <span>Knowledge Graph</span>
            </button>
          </div>

          <a
            href={api.getExportConnectionsUrl(statusFilter)}
            download
            className="px-3.5 py-2 rounded-xl bg-white border border-accent-secondary/60 hover:bg-bg-warm text-text-primary text-xs font-semibold flex items-center gap-1.5 cursor-pointer transition-all shadow-2xs"
            title="Export all connections and citations as Markdown"
          >
            <span>📥</span>
            <span>Export Markdown</span>
          </a>

          <button
            onClick={handleRunDiscovery}
            disabled={isDiscovering}
            className="bg-accent-primary hover:bg-accent-tertiary disabled:opacity-50 text-white font-semibold text-xs px-4 py-2 rounded-xl transition-all shadow-sm flex items-center gap-2 cursor-pointer shrink-0"
          >
            {isDiscovering ? (
              <>
                <svg className="animate-spin h-3.5 w-3.5 text-white" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                Discovering with Groq...
              </>
            ) : (
              <>
                <span>⚡</span>
                <span>Discover New</span>
              </>
            )}
          </button>
        </div>
      </div>

      {message && (
        <div className="bg-accent-primary/10 border border-accent-primary/30 text-accent-tertiary text-xs px-4 py-2 rounded-xl flex items-center justify-between">
          <span>{message}</span>
          <button onClick={() => setMessage('')} className="cursor-pointer">&times;</button>
        </div>
      )}

      {/* Filter Row */}
      <div className="bg-white border border-accent-secondary/50 rounded-2xl p-4 shadow-[0_2px_8px_rgba(0,0,0,0.02)] grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
        <div>
          <label className="text-[10px] font-bold uppercase tracking-wider text-text-secondary block mb-1">Relationship</label>
          <select
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
            className="w-full bg-bg-warm border border-accent-secondary/60 rounded-lg px-2.5 py-1.5 text-xs text-text-primary outline-none cursor-pointer"
          >
            <option value="">All Relationships</option>
            <option value="SUPPORTS">SUPPORTS (Evidence confirms)</option>
            <option value="CONTRADICTS">CONTRADICTS (Evidence conflicts)</option>
            <option value="EXTENDS">EXTENDS (Adds depth/detail)</option>
            <option value="SIMILAR">SIMILAR (Similar topic)</option>
            <option value="ANSWERS">ANSWERS (Answers a question)</option>
            <option value="RELATED">RELATED (General relation)</option>
          </select>
        </div>

        <div>
          <label className="text-[10px] font-bold uppercase tracking-wider text-text-secondary block mb-1">Status</label>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="w-full bg-bg-warm border border-accent-secondary/60 rounded-lg px-2.5 py-1.5 text-xs text-text-primary outline-none cursor-pointer"
          >
            <option value="">Active (New & Saved)</option>
            <option value="new">New (Unreviewed)</option>
            <option value="saved">Saved (Verified)</option>
            <option value="dismissed">Dismissed</option>
          </select>
        </div>

        <div>
          <label className="text-[10px] font-bold uppercase tracking-wider text-text-secondary block mb-1">Filter by Document</label>
          <select
            value={selectedDocFilter}
            onChange={(e) => setSelectedDocFilter(e.target.value)}
            className="w-full bg-bg-warm border border-accent-secondary/60 rounded-lg px-2.5 py-1.5 text-xs text-text-primary outline-none cursor-pointer"
          >
            <option value="">All Documents</option>
            {documents.map((d) => (
              <option key={d.id} value={d.id}>{d.filename}</option>
            ))}
          </select>
        </div>
      </div>

      {/* View Content: Knowledge Graph vs List */}
      {viewMode === 'graph' ? (
        <KnowledgeGraphView typeFilter={typeFilter} statusFilter={statusFilter} />
      ) : (
        <div className="space-y-4">
          {isLoading ? (
            <div className="h-48 rounded-2xl border border-accent-secondary/40 bg-white flex flex-col items-center justify-center gap-2">
              <svg className="animate-spin h-6 w-6 text-accent-primary" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
              <span className="text-xs text-text-secondary font-semibold">Loading connections...</span>
            </div>
          ) : connections.length === 0 ? (
            <div className="h-56 rounded-2xl border border-dashed border-accent-secondary bg-white flex flex-col items-center justify-center p-6 text-center">
              <span className="text-3xl mb-2">🔗</span>
              <p className="font-serif font-bold text-sm text-text-primary">No cross-document connections found</p>
              <p className="text-xs text-text-muted mt-1 max-w-sm">
                Upload multiple research papers or click "Discover New Connections" to let Groq analyze semantic overlaps and factual grounding.
              </p>
            </div>
          ) : (
            connections.map((conn) => {
              const badge = RELATIONSHIP_BADGES[conn.relationship_type] || RELATIONSHIP_BADGES.RELATED;
              const confidencePercent = Math.round((conn.confidence || 0.8) * 100);

              return (
                <div
                  key={conn.id}
                  className="bg-white border border-accent-secondary/50 rounded-2xl p-5 shadow-[0_2px_8px_rgba(0,0,0,0.02)] space-y-4 hover:border-accent-primary/50 transition-all"
                >
                {/* Card Header */}
                <div className="flex flex-wrap items-center justify-between gap-2 border-b border-bg-warm pb-3">
                  <div className="flex items-center gap-2">
                    <span className={`px-2.5 py-1 rounded-full border text-[11px] font-bold flex items-center gap-1 ${badge.bg}`}>
                      <span>{badge.icon}</span>
                      <span>{badge.label}</span>
                    </span>
                    <span className="text-[10px] text-text-muted font-mono" title="Heuristic confidence score based on retrieval similarity and LLM evaluation (not an empirically calibrated probability)">
                      Confidence: {confidencePercent}%
                    </span>
                    <span className={`text-[9px] uppercase font-bold px-2 py-0.5 rounded-full ${
                      conn.status === 'saved' ? 'bg-status-success/15 text-status-success' : 'bg-bg-warm text-text-muted'
                    }`}>
                      {conn.status}
                    </span>
                  </div>

                  <div className="flex items-center gap-1.5 text-xs">
                    {conn.status !== 'saved' && (
                      <button
                        onClick={() => handleUpdateStatus(conn.id, 'saved')}
                        className="px-2.5 py-1 rounded-lg bg-bg-warm hover:bg-status-success/15 text-text-primary hover:text-status-success border border-accent-secondary/60 text-[11px] font-semibold cursor-pointer transition-all"
                      >
                        ★ Save
                      </button>
                    )}
                    {conn.status !== 'dismissed' && (
                      <button
                        onClick={() => handleUpdateStatus(conn.id, 'dismissed')}
                        className="px-2.5 py-1 rounded-lg bg-bg-warm hover:bg-accent-secondary/30 text-text-secondary text-[11px] font-medium border border-accent-secondary/60 cursor-pointer transition-all"
                      >
                        Dismiss
                      </button>
                    )}
                    <button
                      onClick={() => handleDelete(conn.id)}
                      className="px-2 py-1 rounded-lg text-text-muted hover:text-status-error text-[11px] cursor-pointer"
                      title="Delete connection"
                    >
                      &times;
                    </button>
                  </div>
                </div>

                {/* Explanation */}
                <p className="text-xs text-text-primary font-serif font-medium leading-relaxed">
                  {conn.explanation}
                </p>

                {/* Side-by-Side Evidence Snippets */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
                  {/* Source Evidence */}
                  <div className="bg-bg-warm/40 border border-accent-secondary/40 rounded-xl p-3.5 space-y-1.5">
                    <div className="flex items-center justify-between text-[10px] font-bold text-accent-tertiary">
                      <span className="truncate max-w-[200px]" title={conn.source_filename}>
                        📄 {conn.source_filename}
                      </span>
                      {conn.source_page_number && (
                        <span className="font-mono text-text-muted">p. {conn.source_page_number}</span>
                      )}
                    </div>
                    <blockquote className="text-[11px] font-serif text-text-primary italic border-l-2 border-accent-primary/60 pl-2 leading-relaxed">
                      "{conn.evidence_source || 'Evidence citation.'}"
                    </blockquote>
                  </div>

                  {/* Target Evidence */}
                  <div className="bg-bg-warm/40 border border-accent-secondary/40 rounded-xl p-3.5 space-y-1.5">
                    <div className="flex items-center justify-between text-[10px] font-bold text-accent-tertiary">
                      <span className="truncate max-w-[200px]" title={conn.target_filename}>
                        📄 {conn.target_filename}
                      </span>
                      {conn.target_page_number && (
                        <span className="font-mono text-text-muted">p. {conn.target_page_number}</span>
                      )}
                    </div>
                    <blockquote className="text-[11px] font-serif text-text-primary italic border-l-2 border-accent-primary/60 pl-2 leading-relaxed">
                      "{conn.evidence_target || 'Evidence citation.'}"
                    </blockquote>
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>
      )}
    </div>
  );
}
