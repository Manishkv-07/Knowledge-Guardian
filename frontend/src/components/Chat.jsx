import React, { useState, useEffect, useRef } from 'react';
import ChatMessage from './ChatMessage';

export default function Chat({
  activeConversationId,
  messages,
  onSendMessage,
  isLoading,
}) {
  const [input, setInput] = useState('');
  const messagesEndRef = useRef(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  const handleSubmit = (e) => {
    if (e) e.preventDefault();
    if (!input.trim() || isLoading) return;
    onSendMessage(input.trim());
    setInput('');
  };

  const handleSuggestionClick = (suggestion) => {
    if (isLoading) return;
    onSendMessage(suggestion);
  };

  const suggestions = [
    "What is the attention mechanism in Transformers?",
    "How does RAG (Retrieval-Augmented Generation) work?",
    "Explain dense vs sparse retrieval systems.",
    "What role does FAISS play in memory storage?"
  ];

  return (
    <div className="flex-1 flex flex-col justify-between h-full bg-white overflow-hidden">
      
      {/* Messages Window */}
      <div className="flex-1 overflow-y-auto p-6 scroll-smooth">
        {messages.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-center px-4 max-w-xl mx-auto space-y-6">
            <div className="h-14 w-14 rounded-full bg-bg-warm flex items-center justify-center border border-accent-secondary text-2xl">
              🛡️
            </div>
            <div>
              <h3 className="font-serif font-bold text-lg text-text-primary">
                Personal Knowledge Chat
              </h3>
              <p className="text-xs text-text-secondary mt-1 leading-relaxed">
                Ask questions from your personal library. The Guardian will retrieve matching chunks from your indexed research materials, answer, and cite the exact references.
              </p>
            </div>
            
            {/* Quick Suggestions list */}
            <div className="w-full pt-4 space-y-2">
              <span className="text-[10px] text-text-muted uppercase font-bold tracking-wider block mb-2.5">
                Suggested Queries:
              </span>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {suggestions.map((sug, idx) => (
                  <button
                    key={idx}
                    onClick={() => handleSuggestionClick(sug)}
                    className="text-left text-xs bg-bg-warm hover:bg-accent-secondary/30 text-text-primary px-3 py-2.5 rounded-xl border border-accent-secondary/40 transition-colors cursor-pointer"
                  >
                    {sug}
                  </button>
                ))}
              </div>
            </div>
          </div>
        ) : (
          messages.map((msg, idx) => <ChatMessage key={msg.id || idx} message={msg} />)
        )}

        {/* Loading Indicator */}
        {isLoading && (
          <div className="flex justify-start mb-4">
            <div className="bg-white border border-accent-secondary/60 rounded-2xl rounded-tl-none px-5 py-3.5 shadow-xs flex flex-col gap-2 max-w-[75%]">
              <div className="text-[10px] uppercase font-bold tracking-wider opacity-60">
                Guardian AI
              </div>
              <div className="flex items-center gap-1.5 py-1">
                <span className="h-2 w-2 rounded-full bg-accent-primary animate-bounce" style={{ animationDelay: '0ms' }}></span>
                <span className="h-2 w-2 rounded-full bg-accent-primary animate-bounce" style={{ animationDelay: '150ms' }}></span>
                <span className="h-2 w-2 rounded-full bg-accent-primary animate-bounce" style={{ animationDelay: '300ms' }}></span>
                <span className="text-xs text-text-secondary ml-1 font-medium">Retrieving memory chunks & reasoning...</span>
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input controls form */}
      <div className="border-t border-accent-secondary/50 bg-bg-warm/25 p-4 shrink-0">
        <form onSubmit={handleSubmit} className="flex gap-2">
          <input
            type="text"
            placeholder={
              !activeConversationId 
                ? "Start typing to create a new study session thread..." 
                : "Ask a question about your indexed library..."
            }
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={isLoading}
            className="flex-1 bg-white border border-accent-secondary focus:border-accent-primary focus:ring-1 focus:ring-accent-primary rounded-xl px-4 py-3 text-sm outline-none transition-all placeholder-text-muted"
          />
          <button
            type="submit"
            disabled={isLoading || !input.trim()}
            className="bg-accent-primary hover:bg-accent-tertiary disabled:opacity-40 text-white font-semibold text-xs px-5 py-3 rounded-xl transition-all duration-200 shadow-sm flex items-center gap-1.5 shrink-0 cursor-pointer"
          >
            <span>Send</span>
            <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M14 5l7 7m0 0l-7 7m7-7H3" />
            </svg>
          </button>
        </form>
      </div>

    </div>
  );
}
