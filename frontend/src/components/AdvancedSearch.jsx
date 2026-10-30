import React, { useState } from 'react';

/**
 * Reusable component to highlight query keywords in text passages.
 */
export function HighlightText({ text, query, className = "" }) {
  if (!text) return null;
  if (!query || !query.trim()) {
    return <span className={className}>{text}</span>;
  }

  const terms = query
    .toLowerCase()
    .split(/\s+/)
    .map(w => w.replace(/[^a-zA-Z0-9_-]/g, ''))
    .filter(w => w.length > 0);

  if (terms.length === 0) {
    return <span className={className}>{text}</span>;
  }

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
            className="bg-accent-primary/25 text-accent-tertiary px-1 py-0.5 rounded font-medium border-b border-accent-primary/50"
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

export default function AdvancedSearch({
  searchQuery,
  setSearchQuery,
  activeSearchQuery,
  selectedDocTypes,
  toggleDocTypeFilter,
  startDate,
  setStartDate,
  endDate,
  setEndDate,
  resetFilters,
  searchResults,
  totalResults,
  currentPage,
  pageSize,
  setPageSize,
  totalPages,
  handlePageChange,
  isSearching,
  expandedRelated,
  toggleRelated,
  onSearch
}) {
  const [showFilters, setShowFilters] = useState(true);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (searchQuery.trim()) {
      onSearch(searchQuery, 1);
    }
  };

  const hasActiveFilters = selectedDocTypes.length > 0 || Boolean(startDate) || Boolean(endDate);

  return (
    <div className="flex-1 overflow-y-auto space-y-6 pr-1">
      {/* Search Header */}
      <div>
        <h1 className="font-serif text-2xl font-bold text-text-primary tracking-tight">Advanced Hybrid Search</h1>
        <p className="text-xs text-text-secondary mt-1">
          Dense FAISS vector similarity fused with BM25 lexical search (RRF) across all indexed documents.
        </p>
      </div>

      {/* Search Bar & Filters Card */}
      <div className="bg-white border border-accent-secondary/50 rounded-2xl p-5 shadow-[0_2px_12px_rgba(0,0,0,0.02)] space-y-4">
        <form onSubmit={handleSubmit} className="flex gap-2">
          <div className="relative flex-1">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search concepts, key phrases, or terms across papers..."
              className="w-full bg-bg-warm border border-accent-secondary/60 rounded-xl pl-10 pr-4 py-2.5 text-xs text-text-primary placeholder:text-text-muted focus:outline-none focus:border-accent-primary transition-all"
            />
            <svg
              className="absolute left-3.5 top-3 h-4 w-4 text-text-muted"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
          </div>
          <button
            type="submit"
            disabled={isSearching || !searchQuery.trim()}
            className="bg-accent-primary hover:bg-accent-tertiary disabled:opacity-50 text-white font-semibold text-xs px-5 py-2.5 rounded-xl transition-all shadow-sm flex items-center gap-1.5 cursor-pointer shrink-0"
          >
            {isSearching ? (
              <>
                <svg className="animate-spin h-3.5 w-3.5 text-white" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                Searching...
              </>
            ) : (
              'Search'
            )}
          </button>
          <button
            type="button"
            onClick={() => setShowFilters(!showFilters)}
            className={`px-3 py-2.5 rounded-xl border text-xs font-semibold flex items-center gap-1.5 cursor-pointer transition-all ${
              showFilters || hasActiveFilters
                ? 'bg-accent-secondary/40 border-accent-secondary text-text-primary'
                : 'bg-bg-warm border-accent-secondary/60 text-text-secondary hover:text-text-primary'
            }`}
            title="Toggle Filter Panel"
          >
            <span>⚙️ Filters</span>
            {hasActiveFilters && <span className="h-2 w-2 rounded-full bg-accent-primary"></span>}
          </button>
        </form>

        {/* Filter Controls Panel */}
        {showFilters && (
          <div className="pt-3 border-t border-bg-warm grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
            {/* Document Type Pills */}
            <div className="space-y-1.5">
              <span className="text-[10px] uppercase font-bold text-text-secondary tracking-wider block">File Format</span>
              <div className="flex gap-1.5">
                {['pdf', 'txt', 'md'].map((type) => {
                  const active = selectedDocTypes.includes(type);
                  return (
                    <button
                      key={type}
                      type="button"
                      onClick={() => toggleDocTypeFilter(type)}
                      className={`px-3 py-1 rounded-lg font-mono uppercase text-xs font-bold border transition-all cursor-pointer ${
                        active
                          ? 'bg-accent-primary text-white border-accent-primary shadow-xs'
                          : 'bg-bg-warm border-accent-secondary/60 text-text-secondary hover:text-text-primary'
                      }`}
                    >
                      {type}
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Date Range Start */}
            <div className="space-y-1.5">
              <span className="text-[10px] uppercase font-bold text-text-secondary tracking-wider block">Start Date</span>
              <input
                type="date"
                value={startDate}
                onChange={(e) => {
                  const val = e.target.value;
                  setStartDate(val);
                  if (activeSearchQuery) onSearch(activeSearchQuery, 1, selectedDocTypes, val, endDate, pageSize);
                }}
                className="w-full bg-bg-warm border border-accent-secondary/60 rounded-lg px-2.5 py-1 text-xs text-text-primary outline-none"
              />
            </div>

            {/* Date Range End & Reset */}
            <div className="space-y-1.5 flex flex-col justify-between">
              <div>
                <span className="text-[10px] uppercase font-bold text-text-secondary tracking-wider block">End Date</span>
                <input
                  type="date"
                  value={endDate}
                  onChange={(e) => {
                    const val = e.target.value;
                    setEndDate(val);
                    if (activeSearchQuery) onSearch(activeSearchQuery, 1, selectedDocTypes, startDate, val, pageSize);
                  }}
                  className="w-full bg-bg-warm border border-accent-secondary/60 rounded-lg px-2.5 py-1 text-xs text-text-primary outline-none"
                />
              </div>
            </div>

            {hasActiveFilters && (
              <div className="md:col-span-3 flex justify-end">
                <button
                  type="button"
                  onClick={resetFilters}
                  className="text-text-muted hover:text-status-error text-[11px] font-medium underline cursor-pointer"
                >
                  Clear all active filters
                </button>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Results Header */}
      {activeSearchQuery && (
        <div className="flex items-center justify-between text-xs px-1">
          <span className="text-text-secondary">
            Found <strong className="text-text-primary font-mono">{totalResults}</strong> passage{totalResults === 1 ? '' : 's'} matching{' '}
            <span className="font-serif italic font-semibold text-text-primary">"{activeSearchQuery}"</span>
          </span>
          <div className="flex items-center gap-2 text-text-muted text-[11px]">
            <span>Page size:</span>
            <select
              value={pageSize}
              onChange={(e) => {
                const s = parseInt(e.target.value);
                setPageSize(s);
                onSearch(activeSearchQuery, 1, selectedDocTypes, startDate, endDate, s);
              }}
              className="bg-white border border-accent-secondary/60 rounded px-2 py-0.5 text-xs text-text-primary outline-none cursor-pointer"
            >
              <option value="5">5</option>
              <option value="10">10</option>
              <option value="20">20</option>
            </select>
          </div>
        </div>
      )}

      {/* Results List */}
      <div className="space-y-4">
        {isSearching ? (
          <div className="h-48 rounded-2xl border border-accent-secondary/40 bg-white flex flex-col items-center justify-center gap-2">
            <svg className="animate-spin h-6 w-6 text-accent-primary" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            <span className="text-xs font-semibold text-text-secondary">Retrieving hybrid candidate passages...</span>
          </div>
        ) : activeSearchQuery && searchResults.length === 0 ? (
          <div className="h-48 rounded-2xl border border-dashed border-accent-secondary/60 bg-white flex flex-col items-center justify-center p-6 text-center">
            <span className="text-2xl mb-1">🔍</span>
            <p className="font-serif font-bold text-sm text-text-primary">No matching passages found</p>
            <p className="text-xs text-text-muted mt-1 max-w-sm">
              We couldn't find any passages matching "{activeSearchQuery}" with current filters. Try relaxing filters or using broader keywords.
            </p>
          </div>
        ) : (
          searchResults.map((item) => {
            const ext = (item.doc_type || item.document_name?.split('.').pop() || 'TXT').toUpperCase();
            const isExpanded = Boolean(expandedRelated[item.chunk_id]);
            const matchPercent = Math.round(item.similarity * 100);

            return (
              <div
                key={item.chunk_id}
                className="bg-white border border-accent-secondary/50 rounded-2xl p-5 shadow-[0_2px_8px_rgba(0,0,0,0.02)] space-y-3 hover:border-accent-primary/50 transition-all"
              >
                {/* Item Top Metadata */}
                <div className="flex items-center justify-between text-xs">
                  <div className="flex items-center gap-2">
                    <span className="px-2 py-0.5 rounded font-mono text-[10px] font-bold bg-bg-warm text-accent-tertiary">
                      {ext}
                    </span>
                    <h4 className="font-serif font-bold text-text-primary">
                      {item.document_name || 'Document'}
                    </h4>
                    {item.page_number && (
                      <span className="px-1.5 py-0.5 rounded bg-accent-secondary/30 text-text-secondary text-[10px] font-mono font-medium">
                        Page {item.page_number}
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    {item.rrf_score && (
                      <span className="text-[10px] text-text-muted font-mono" title="Reciprocal Rank Fusion score">
                        RRF: {item.rrf_score}
                      </span>
                    )}
                    <span
                      className={`px-2 py-0.5 rounded-full text-[10px] font-bold font-mono ${
                        matchPercent >= 70
                          ? 'bg-status-success/15 text-status-success'
                          : matchPercent >= 45
                          ? 'bg-accent-primary/15 text-accent-tertiary'
                          : 'bg-bg-warm text-text-muted'
                      }`}
                    >
                      {matchPercent}% match
                    </span>
                  </div>
                </div>

                {/* Highlighted Passage Text */}
                <div className="text-xs text-text-primary font-serif leading-relaxed bg-bg-warm/30 p-3.5 rounded-xl border border-accent-secondary/30">
                  <HighlightText text={item.chunk} query={activeSearchQuery} />
                </div>

                {/* Related Context Accordion */}
                {item.related_chunks && item.related_chunks.length > 0 && (
                  <div>
                    <button
                      type="button"
                      onClick={() => toggleRelated(item.chunk_id)}
                      className="text-[11px] font-semibold text-accent-primary hover:text-accent-tertiary flex items-center gap-1 cursor-pointer transition-colors"
                    >
                      <span>{isExpanded ? '▼ Hide' : '▶ View'} Adjacent Document Context ({item.related_chunks.length})</span>
                    </button>
                    {isExpanded && (
                      <div className="mt-2 pl-3 border-l-2 border-accent-secondary/60 space-y-2">
                        {item.related_chunks.map((rel) => (
                          <div key={rel.chunk_id} className="text-[11px] text-text-secondary font-serif bg-white p-2.5 rounded-lg border border-accent-secondary/30">
                            <span className="text-[9px] uppercase font-bold text-text-muted block mb-1">
                              Adjacent Chunk {rel.chunk_index}
                            </span>
                            <HighlightText text={rel.text} query={activeSearchQuery} />
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

      {/* Pagination Controls */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between pt-4 border-t border-accent-secondary/40 text-xs">
          <span className="text-text-muted text-[11px]">
            Page <strong className="text-text-primary font-mono">{currentPage}</strong> of{' '}
            <strong className="text-text-primary font-mono">{totalPages}</strong>
          </span>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => handlePageChange(currentPage - 1)}
              disabled={currentPage <= 1 || isSearching}
              className="px-3 py-1.5 rounded-lg border border-accent-secondary/60 bg-white text-text-primary disabled:opacity-40 hover:bg-bg-warm cursor-pointer font-medium transition-all"
            >
              Previous
            </button>
            <button
              type="button"
              onClick={() => handlePageChange(currentPage + 1)}
              disabled={currentPage >= totalPages || isSearching}
              className="px-3 py-1.5 rounded-lg border border-accent-secondary/60 bg-white text-text-primary disabled:opacity-40 hover:bg-bg-warm cursor-pointer font-medium transition-all"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
