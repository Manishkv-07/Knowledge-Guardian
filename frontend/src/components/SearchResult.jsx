import React, { useState } from 'react';

export default function SearchResult({ result }) {
  const [expanded, setExpanded] = useState(false);

  // Normalize similarity score
  const normalizeScore = (score) => {
    if (score === undefined || score === null) return 0;
    let parsed = typeof score === 'string' ? parseFloat(score.replace('%', '')) : parseFloat(score);
    if (isNaN(parsed)) return 0;
    
    // Normalize fractional scores (e.g. 0.92 -> 92)
    if (parsed > 0 && parsed <= 1.0) {
      parsed = parsed * 100;
    }
    return Math.round(parsed);
  };

  const scoreVal = normalizeScore(result.similarity);

  // Score styling categories:
  // - 80–100% → positive/green-ish/terracotta accent (status-success or accent-primary)
  // - 60–79% → warm beige/yellow accent (accent-secondary/accent-tertiary)
  // - 40–59% → muted gray/warm-light accent
  let scoreClass = 'bg-bg-warm text-text-muted border-accent-secondary/30';
  if (scoreVal >= 80) {
    scoreClass = 'bg-status-success/15 text-status-success border-status-success/30';
  } else if (scoreVal >= 60) {
    scoreClass = 'bg-accent-secondary/50 text-accent-tertiary border-accent-secondary';
  } else if (scoreVal >= 40) {
    scoreClass = 'bg-bg-warm text-text-secondary border-accent-secondary/40';
  }

  const textContent = result.text || '';
  const shouldTruncate = textContent.length > 200;
  const displayText = expanded 
    ? textContent 
    : (shouldTruncate ? textContent.slice(0, 200) + '...' : textContent);

  // Construct metadata string
  const metadataParts = [];
  if (result.chunkNumber !== undefined && result.chunkNumber !== null) {
    const totalText = result.totalChunks ? ` of ${result.totalChunks}` : '';
    metadataParts.push(`📍 Chunk ${result.chunkNumber}${totalText}`);
  }
  if (result.date) {
    metadataParts.push(`📅 ${result.date}`);
  }
  if (result.documentId !== undefined && result.documentId !== null) {
    metadataParts.push(`🆔 ID: ${result.documentId}`);
  }

  return (
    <div 
      onClick={() => setExpanded(!expanded)}
      className="bg-white border border-accent-secondary/40 rounded-xl p-5 hover:shadow-md hover:border-accent-primary/60 transition-all duration-200 cursor-pointer space-y-3 focus:outline-none focus:ring-2 focus:ring-accent-primary"
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          setExpanded(!expanded);
        }
      }}
      aria-expanded={expanded}
    >
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-2 min-w-0">
          <span className="text-base shrink-0" aria-hidden="true">📄</span>
          <span className="text-xs font-semibold text-text-secondary truncate font-mono" title={result.filename}>
            From: {result.filename}
          </span>
        </div>
        <span 
          className={`text-xs font-bold font-mono px-2.5 py-1 rounded-full border shrink-0 ${scoreClass}`}
          aria-label={`Similarity score is ${scoreVal} percent`}
        >
          {scoreVal}%
        </span>
      </div>

      <div className="text-sm font-serif text-text-primary leading-relaxed bg-bg-warm/10 p-3 rounded-lg border border-accent-secondary/15 transition-all">
        "{displayText}"
        {shouldTruncate && (
          <span className="text-xs font-sans font-semibold text-accent-tertiary block mt-2 hover:underline">
            {expanded ? 'Show Less ↑' : 'Show More ↓'}
          </span>
        )}
      </div>

      {metadataParts.length > 0 && (
        <div className="text-[10px] text-text-muted font-semibold tracking-wider uppercase flex flex-wrap gap-2 items-center">
          {metadataParts.map((part, idx) => (
            <React.Fragment key={idx}>
              {idx > 0 && <span className="text-accent-secondary">•</span>}
              <span>{part}</span>
            </React.Fragment>
          ))}
        </div>
      )}
    </div>
  );
}
