import React, { useState, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import { api } from '../services/api';

export default function MemoryPatternsView({ documents = [], selectedDocId, setSelectedDocId, onGenerateInsight, isGenerating }) {
  const [patterns, setPatterns] = useState([]);
  const [insightType, setInsightType] = useState('summary');
  const [customInstruction, setCustomInstruction] = useState('');
  const [isLoadingPatterns, setIsLoadingPatterns] = useState(false);
  const [message, setMessage] = useState('');

  const loadPatterns = async () => {
    setIsLoadingPatterns(true);
    try {
      const data = await api.getPatternMemories();
      setPatterns(data || []);
    } catch (err) {
      console.error("Failed to load pattern memories:", err);
    } finally {
      setIsLoadingPatterns(false);
    }
  };

  useEffect(() => {
    loadPatterns();
  }, []);

  const handleDismissPattern = async (id) => {
    try {
      await api.dismissPatternMemory(id);
      await loadPatterns();
      setMessage("Pattern dismissed.");
      setTimeout(() => setMessage(''), 3000);
    } catch (err) {
      console.error("Failed to dismiss pattern:", err);
    }
  };

  const selectedDoc = documents.find(d => d.id === selectedDocId);

  return (
    <div className="flex-1 overflow-y-auto space-y-6 pr-1">
      {/* Header */}
      <div>
        <h1 className="font-serif text-2xl font-bold text-text-primary tracking-tight">Persistent Memory & Concept Synthesis</h1>
        <p className="text-xs text-text-secondary mt-1">
          Structured fact memories, episodic interaction contexts, and transparent observations about recurring research topics.
        </p>
      </div>

      {message && (
        <div className="bg-accent-primary/10 border border-accent-primary/30 text-accent-tertiary text-xs px-4 py-2 rounded-xl">
          {message}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* Left 2 Cols: Fact Memory & Document Insight Extraction */}
        <div className="lg:col-span-2 space-y-6">
          
          {/* Extraction Control Box */}
          <div className="bg-white border border-accent-secondary/50 rounded-2xl p-5 shadow-[0_2px_8px_rgba(0,0,0,0.02)] space-y-4">
            <h3 className="font-serif text-sm font-bold text-text-primary border-b border-bg-warm pb-2">
              Extract Document Fact Memory (Groq AI)
            </h3>
            
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
                <div className="flex flex-wrap gap-1">
                  {['summary', 'key_concept', 'definitions', 'study_questions', 'custom'].map((t) => (
                    <button
                      key={t}
                      type="button"
                      onClick={() => setInsightType(t)}
                      className={`px-2.5 py-1 rounded-lg text-xs font-semibold border capitalize transition-all cursor-pointer ${
                        insightType === t 
                          ? 'bg-accent-primary text-white border-accent-primary shadow-xs' 
                          : 'bg-bg-warm border-accent-secondary text-text-secondary hover:text-text-primary'
                      }`}
                    >
                      {t.replace('_', ' ')}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            {insightType === 'custom' && (
              <div className="space-y-1 pt-1">
                <label className="text-[10px] font-bold uppercase tracking-wider text-text-secondary">Custom Research Prompt</label>
                <input
                  type="text"
                  value={customInstruction}
                  onChange={(e) => setCustomInstruction(e.target.value)}
                  placeholder="e.g., Focus analysis on mathematical bounds in section 3..."
                  className="w-full bg-bg-warm border border-accent-secondary rounded-lg px-3 py-2 text-xs outline-none text-text-primary"
                />
              </div>
            )}

            <button
              onClick={() => onGenerateInsight(insightType, customInstruction)}
              disabled={isGenerating || !selectedDocId}
              className="w-full bg-accent-primary hover:bg-accent-tertiary disabled:opacity-40 text-white font-semibold text-xs py-2.5 rounded-xl transition-all duration-200 flex items-center justify-center gap-1.5 shadow-sm cursor-pointer"
            >
              {isGenerating ? (
                <>
                  <svg className="animate-spin h-3.5 w-3.5 text-white" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  Synthesizing Grounded Insight...
                </>
              ) : (
                'Extract & Store Grounded Insight'
              )}
            </button>
          </div>

          {/* Stored Memories List */}
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="font-serif text-lg font-bold text-text-primary">Stored Memory Units</h3>
              {selectedDoc && (
                <a
                  href={api.getExportDocumentUrl(selectedDoc.id)}
                  download
                  className="px-3 py-1 rounded-lg bg-white border border-accent-secondary/60 hover:bg-bg-warm text-text-primary text-xs font-semibold flex items-center gap-1 cursor-pointer transition-all shadow-2xs"
                  title="Export full document summary and citations as Markdown"
                >
                  <span>📥</span>
                  <span>Export Document Markdown</span>
                </a>
              )}
            </div>
            
            {!selectedDoc ? (
              <div className="rounded-2xl border border-accent-secondary/50 bg-white p-8 text-center text-text-muted text-xs">
                Select an indexed document above to inspect its stored memory units.
              </div>
            ) : (!selectedDoc.memories || selectedDoc.memories.length === 0) ? (
              <div className="rounded-2xl border border-accent-secondary/50 bg-white p-8 text-center text-text-muted text-xs">
                No memories generated for "{selectedDoc.filename}" yet. Tap "Extract & Store Fact Memory" to begin.
              </div>
            ) : (
              <div className="space-y-3">
                {(selectedDoc.memories || []).map((mem) => (
                  <div key={mem.id} className="bg-white border border-accent-secondary/40 rounded-2xl p-5 space-y-3">
                    <div className="flex items-center justify-between text-xs">
                      <span className={`px-2.5 py-0.5 rounded-full border text-[10px] font-bold uppercase tracking-wider ${
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
                    <div className="text-text-primary text-xs font-serif leading-relaxed bg-bg-warm/30 p-4 rounded-xl border border-accent-secondary/20 space-y-2">
                      <ReactMarkdown>{mem.content}</ReactMarkdown>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

        </div>

        {/* Right Col: Transparent Cognitive Pattern Memories */}
        <div className="space-y-6">
          <div>
            <h3 className="font-serif text-lg font-bold text-text-primary">Pattern Memories</h3>
            <p className="text-[11px] text-text-muted mt-0.5">Transparent, user-visible observations about recurring topics.</p>
          </div>

          <div className="space-y-3">
            {isLoadingPatterns ? (
              <div className="bg-white border border-accent-secondary/50 rounded-2xl p-6 text-center text-xs text-text-muted">
                Loading pattern observations...
              </div>
            ) : patterns.length === 0 ? (
              <div className="bg-white border border-accent-secondary/50 rounded-2xl p-6 text-center text-xs text-text-muted">
                No active recurring research patterns detected yet.
              </div>
            ) : (
              patterns.map((p) => (
                <div
                  key={p.id}
                  className="bg-white border border-accent-secondary/50 rounded-2xl p-4 shadow-[0_2px_8px_rgba(0,0,0,0.02)] space-y-2"
                >
                  <div className="flex items-start justify-between gap-2">
                    <h4 className="font-serif font-bold text-xs text-text-primary flex items-center gap-1.5">
                      <span>🔄</span> {p.topic}
                    </h4>
                    <button
                      onClick={() => handleDismissPattern(p.id)}
                      className="text-text-muted hover:text-status-error text-xs cursor-pointer"
                      title="Dismiss pattern observation"
                    >
                      &times;
                    </button>
                  </div>
                  <p className="text-[11px] text-text-secondary font-serif leading-relaxed">
                    {p.observation}
                  </p>
                  <div className="pt-2 border-t border-bg-warm flex items-center justify-between text-[10px] text-text-muted font-mono">
                    <span>Frequency: {p.frequency}x</span>
                    {Array.isArray(p.source_documents) && p.source_documents.length > 0 && (
                      <span className="truncate max-w-[150px]">
                        {p.source_documents.join(', ')}
                      </span>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

      </div>
    </div>
  );
}
