import React from 'react';
import ReactMarkdown from 'react-markdown';

export default function ChatMessage({ message }) {
  const { role, content, sources } = message;
  const isUser = role === 'user';

  return (
    <div className={`flex w-full ${isUser ? 'justify-end' : 'justify-start'} mb-4`}>
      <div
        className={`max-w-[75%] rounded-2xl px-5 py-3.5 text-sm leading-relaxed shadow-xs transition-all ${
          isUser
            ? 'bg-sidebar-warm text-text-primary border border-accent-secondary/50 rounded-tr-none'
            : 'bg-white border border-accent-secondary/60 text-text-primary rounded-tl-none'
        }`}
      >
        {/* Role Badge */}
        <div className="text-[10px] uppercase font-bold tracking-wider mb-1.5 opacity-60">
          {isUser ? 'You' : 'Guardian AI'}
        </div>

        {/* Content */}
        <div className="markdown-body space-y-1.5 break-words">
          <ReactMarkdown>{content}</ReactMarkdown>
        </div>

        {/* Sources / Citations */}
        {!isUser && sources && sources.length > 0 && (
          <div className="mt-3.5 pt-2 border-t border-bg-warm">
            <div className="text-[10px] text-text-muted uppercase font-bold tracking-wider mb-1.5">
              Citations & Sources:
            </div>
            <div className="flex flex-wrap gap-2">
              {sources.map((src, idx) => {
                const label = src.label || `[S${idx + 1}]`;
                const name = src.filename || 'Unknown Source';
                const page = src.page_number ? ` (p. ${src.page_number})` : '';
                const score = src.similarity ? (src.similarity * 100).toFixed(1) : null;
                return (
                  <div
                    key={idx}
                    className="inline-flex items-center gap-1.5 text-[10px] font-medium bg-bg-warm text-accent-tertiary px-2 py-1 rounded border border-accent-secondary/40 max-w-[260px] truncate"
                    title={`${label} ${name}${page} ${score ? `(${score}%)` : ''}\n\nPreview: "${src.text || ''}"`}
                  >
                    <span className="font-mono font-bold text-accent-primary">{label}</span>
                    <span className="truncate">{name}{page}</span>
                    {score && (
                      <span className="text-[8px] bg-accent-secondary/60 px-1 py-0.25 rounded text-accent-tertiary shrink-0 font-mono">
                        {score}%
                      </span>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
