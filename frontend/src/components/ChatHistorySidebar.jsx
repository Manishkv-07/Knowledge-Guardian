import React, { useState } from 'react';

export default function ChatHistorySidebar({
  conversations,
  activeConversationId,
  onSelectConversation,
  onCreateConversation,
  onRenameConversation,
  onDeleteConversation,
}) {
  const [editingId, setEditingId] = useState(null);
  const [editTitle, setEditTitle] = useState('');

  const handleStartRename = (e, conv) => {
    e.stopPropagation();
    setEditingId(conv.id);
    setEditTitle(conv.title);
  };

  const handleSaveRename = (id) => {
    if (editTitle.trim() && editTitle.trim() !== '') {
      onRenameConversation(id, editTitle.trim());
    }
    setEditingId(null);
  };

  const handleKeyDown = (e, id) => {
    if (e.key === 'Enter') {
      handleSaveRename(id);
    } else if (e.key === 'Escape') {
      setEditingId(null);
    }
  };

  const handleDelete = (e, id) => {
    e.stopPropagation();
    if (window.confirm('Are you sure you want to delete this conversation and all its message history?')) {
      onDeleteConversation(id);
    }
  };

  return (
    <aside className="w-80 bg-sidebar-warm border-r border-accent-secondary p-5 flex flex-col justify-between shrink-0 h-full">
      <div className="flex flex-col h-full overflow-hidden">
        
        {/* Sidebar Header */}
        <div className="flex items-center justify-between pb-4 border-b border-accent-secondary/50 shrink-0">
          <h3 className="font-serif font-bold text-sm text-text-primary flex items-center gap-1.5">
            <span>💬</span> Chat Sessions
          </h3>
          <button
            onClick={() => onCreateConversation()}
            className="p-1.5 rounded-lg bg-accent-primary hover:bg-accent-tertiary text-white text-[11px] font-bold shadow-xs flex items-center gap-1 transition-all cursor-pointer"
            title="Create New Conversation"
          >
            <span>+</span> New Chat
          </button>
        </div>

        {/* Conversation List */}
        <div className="flex-1 overflow-y-auto py-4 space-y-2.5 pr-1">
          {conversations.length === 0 ? (
            <div className="text-center py-10 px-4 text-xs text-text-muted">
              No conversations yet. Click "New Chat" to begin.
            </div>
          ) : (
            conversations.map((conv) => {
              const isActive = conv.id === activeConversationId;
              const isEditing = conv.id === editingId;

              return (
                <div
                  key={conv.id}
                  onClick={() => !isEditing && onSelectConversation(conv.id)}
                  className={`group relative rounded-xl p-3.5 border transition-all duration-150 cursor-pointer ${
                    isActive
                      ? 'bg-white border-accent-primary shadow-xs font-semibold'
                      : 'bg-white/40 border-accent-secondary/30 hover:bg-white/70 hover:border-accent-primary/40'
                  }`}
                >
                  <div className="flex flex-col gap-1 pr-16">
                    {isEditing ? (
                      <input
                        type="text"
                        value={editTitle}
                        onChange={(e) => setEditTitle(e.target.value)}
                        onBlur={() => handleSaveRename(conv.id)}
                        onKeyDown={(e) => handleKeyDown(e, conv.id)}
                        className="w-full text-xs font-serif font-bold text-text-primary bg-bg-warm border border-accent-primary rounded px-2 py-0.5 outline-none"
                        autoFocus
                        onClick={(e) => e.stopPropagation()}
                      />
                    ) : (
                      <h4
                        className="text-xs font-serif font-bold text-text-primary truncate"
                        onDoubleClick={(e) => handleStartRename(e, conv)}
                        title="Double-click to rename"
                      >
                        {conv.title}
                      </h4>
                    )}
                    
                    {/* Message Preview */}
                    <p className="text-[10px] text-text-secondary line-clamp-1 leading-snug">
                      {conv.last_message || 'No messages yet'}
                    </p>
                  </div>

                  {/* Actions overlay */}
                  {!isEditing && (
                    <div className="absolute right-2.5 top-1/2 -translate-y-1/2 flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                      <button
                        onClick={(e) => handleStartRename(e, conv)}
                        className="p-1 rounded text-text-muted hover:text-accent-primary hover:bg-bg-warm transition-colors cursor-pointer"
                        title="Rename Chat"
                      >
                        <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
                        </svg>
                      </button>
                      <button
                        onClick={(e) => handleDelete(e, conv.id)}
                        className="p-1 rounded text-text-muted hover:text-status-error hover:bg-bg-warm transition-colors cursor-pointer"
                        title="Delete Chat"
                      >
                        <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                        </svg>
                      </button>
                    </div>
                  )}
                </div>
              );
            })
          )}
        </div>

        {/* Footer info inside sidebar */}
        <div className="pt-3 border-t border-accent-secondary/40 text-[10px] text-text-muted flex justify-between shrink-0">
          <span>Episodic Memory Cache</span>
          <span>SQLite DB</span>
        </div>
      </div>
    </aside>
  );
}
