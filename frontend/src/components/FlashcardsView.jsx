import React, { useState, useEffect } from 'react';
import { api } from '../services/api';

export default function FlashcardsView({ documents = [] }) {
  const [flashcards, setFlashcards] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [dueOnly, setDueOnly] = useState(false);
  const [selectedDocFilter, setSelectedDocFilter] = useState('');
  
  // Study Session Mode State
  const [studyMode, setStudyMode] = useState(false);
  const [currentCardIndex, setCurrentCardIndex] = useState(0);
  const [showAnswer, setShowAnswer] = useState(false);

  // Modals
  const [showGenerateModal, setShowGenerateModal] = useState(false);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [generateDocId, setGenerateDocId] = useState('');
  const [generateCount, setGenerateCount] = useState(3);
  const [isGenerating, setIsGenerating] = useState(false);
  
  // Manual Create Fields
  const [manualQuestion, setManualQuestion] = useState('');
  const [manualAnswer, setManualAnswer] = useState('');
  const [manualSnippet, setManualSnippet] = useState('');
  const [manualDocId, setManualDocId] = useState('');
  
  const [message, setMessage] = useState('');

  const loadFlashcards = async () => {
    setIsLoading(true);
    try {
      const params = {};
      if (dueOnly) params.due_only = true;
      if (selectedDocFilter) params.document_id = selectedDocFilter;
      const data = await api.getFlashcards(params);
      setFlashcards(data || []);
    } catch (err) {
      console.error("Failed to load flashcards:", err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadFlashcards();
  }, [dueOnly, selectedDocFilter]);

  const handleReviewAction = async (cardId, action) => {
    try {
      await api.reviewFlashcard(cardId, action);
      // Move to next card in study session
      if (currentCardIndex + 1 < flashcards.length) {
        setCurrentCardIndex(prev => prev + 1);
        setShowAnswer(false);
      } else {
        setStudyMode(false);
        setMessage("🎉 Study session completed! Outstanding work reviewing your concepts.");
        setTimeout(() => setMessage(''), 5000);
      }
      await loadFlashcards();
    } catch (err) {
      console.error("Failed to submit review:", err);
    }
  };

  const handleDeleteCard = async (cardId) => {
    if (!window.confirm("Delete this flashcard?")) return;
    try {
      await api.deleteFlashcard(cardId);
      await loadFlashcards();
    } catch (err) {
      console.error("Failed to delete card:", err);
    }
  };

  const handleGenerate = async (e) => {
    e.preventDefault();
    if (!generateDocId) return;
    setIsGenerating(true);
    try {
      const cards = await api.generateFlashcards(parseInt(generateDocId), generateCount);
      setShowGenerateModal(false);
      await loadFlashcards();
      setMessage(`Generated ${cards.length} source-grounded flashcards successfully!`);
      setTimeout(() => setMessage(''), 5000);
    } catch (err) {
      setMessage("Failed to generate flashcards. Check Groq API configuration.");
    } finally {
      setIsGenerating(false);
    }
  };

  const handleManualCreate = async (e) => {
    e.preventDefault();
    if (!manualQuestion.trim() || !manualAnswer.trim() || !manualDocId) return;
    const doc = documents.find(d => d.id === parseInt(manualDocId));
    try {
      await api.createFlashcard({
        document_id: parseInt(manualDocId),
        question: manualQuestion.trim(),
        answer: manualAnswer.trim(),
        source_snippet: manualSnippet.trim() || null,
        filename: doc?.filename || 'Document',
      });
      setShowCreateModal(false);
      setManualQuestion('');
      setManualAnswer('');
      setManualSnippet('');
      await loadFlashcards();
      setMessage("Flashcard created successfully.");
      setTimeout(() => setMessage(''), 3000);
    } catch (err) {
      console.error("Failed to create card:", err);
    }
  };

  const startStudySession = () => {
    if (flashcards.length === 0) return;
    setCurrentCardIndex(0);
    setShowAnswer(false);
    setStudyMode(true);
  };

  const currentStudyCard = flashcards[currentCardIndex];

  return (
    <div className="flex-1 overflow-y-auto space-y-6 pr-1">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="font-serif text-2xl font-bold text-text-primary tracking-tight">Source-Grounded Flashcards</h1>
          <p className="text-xs text-text-secondary mt-1">
            Master research concepts with verifiable evidence citations and SM-2 deterministic spaced repetition.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <a
            href={api.getExportFlashcardsCsvUrl(selectedDocFilter || null)}
            download
            className="px-3 py-2 rounded-xl bg-white border border-accent-secondary/60 hover:bg-bg-warm text-text-primary text-xs font-semibold flex items-center gap-1.5 cursor-pointer transition-all shadow-2xs"
            title="Export flashcards to Anki-compatible CSV"
          >
            <span>📥</span>
            <span>Export CSV</span>
          </a>
          <button
            onClick={() => setShowCreateModal(true)}
            className="px-3.5 py-2 rounded-xl bg-white border border-accent-secondary/60 hover:bg-bg-warm text-text-primary text-xs font-semibold cursor-pointer transition-all"
          >
            + Create Card
          </button>
          <button
            onClick={() => setShowGenerateModal(true)}
            className="bg-accent-primary hover:bg-accent-tertiary text-white font-semibold text-xs px-4 py-2 rounded-xl transition-all shadow-sm flex items-center gap-1.5 cursor-pointer"
          >
            <span>✨</span>
            <span>Generate with AI</span>
          </button>
        </div>
      </div>

      {message && (
        <div className="bg-accent-primary/10 border border-accent-primary/30 text-accent-tertiary text-xs px-4 py-2.5 rounded-xl flex items-center justify-between">
          <span>{message}</span>
          <button onClick={() => setMessage('')} className="cursor-pointer">&times;</button>
        </div>
      )}

      {/* Study Session Active Modal/Card */}
      {studyMode && currentStudyCard ? (
        <div className="bg-white border-2 border-accent-primary/50 rounded-3xl p-8 shadow-xl max-w-2xl mx-auto space-y-6">
          <div className="flex items-center justify-between text-xs border-b border-bg-warm pb-3">
            <span className="text-text-muted font-mono font-semibold">
              Card {currentCardIndex + 1} of {flashcards.length}
            </span>
            <div className="flex items-center gap-2">
              <span className="text-accent-tertiary font-serif text-xs font-bold truncate max-w-[200px]">
                📄 {currentStudyCard.filename}
              </span>
              {currentStudyCard.page_number && (
                <span className="px-2 py-0.5 rounded bg-accent-secondary/30 text-[10px] font-mono">
                  p. {currentStudyCard.page_number}
                </span>
              )}
            </div>
            <button
              onClick={() => setStudyMode(false)}
              className="text-text-muted hover:text-text-primary text-sm font-semibold cursor-pointer"
            >
              Exit Session
            </button>
          </div>

          {/* Flashcard Front: Question */}
          <div className="space-y-2 py-4">
            <span className="text-[10px] font-bold uppercase tracking-wider text-text-muted block">Question</span>
            <h3 className="font-serif text-lg font-bold text-text-primary leading-snug">
              {currentStudyCard.question}
            </h3>
          </div>

          {/* Reveal Answer Button */}
          {!showAnswer ? (
            <button
              onClick={() => setShowAnswer(true)}
              className="w-full py-3 rounded-2xl bg-accent-secondary/40 hover:bg-accent-secondary/70 text-text-primary font-semibold text-xs tracking-wider uppercase transition-all cursor-pointer"
            >
              Show Answer & Grounding Evidence
            </button>
          ) : (
            <div className="space-y-5 pt-4 border-t border-bg-warm">
              {/* Answer */}
              <div className="space-y-1.5">
                <span className="text-[10px] font-bold uppercase tracking-wider text-status-success block">Answer</span>
                <p className="text-xs text-text-primary font-serif leading-relaxed bg-bg-warm/40 p-4 rounded-xl border border-accent-secondary/30">
                  {currentStudyCard.answer}
                </p>
              </div>

              {/* Verified Source Snippet */}
              {currentStudyCard.source_snippet && (
                <div className="space-y-1 bg-amber-50/60 border border-amber-200/60 rounded-xl p-3 text-xs">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-amber-800 block">
                    Source Grounding Quotation
                  </span>
                  <blockquote className="italic font-serif text-[11px] text-amber-900 border-l-2 border-amber-400 pl-2">
                    "{currentStudyCard.source_snippet}"
                  </blockquote>
                </div>
              )}

              {/* SM-2 Spaced Repetition Rating Buttons */}
              <div className="space-y-2 pt-2">
                <span className="text-[10px] font-bold uppercase tracking-wider text-text-muted block text-center">
                  Rate Recall Difficulty (SM-2 Interval)
                </span>
                <div className="grid grid-cols-4 gap-2">
                  <button
                    onClick={() => handleReviewAction(currentStudyCard.id, 'again')}
                    className="py-2.5 px-2 rounded-xl bg-rose-50 hover:bg-rose-100 text-rose-800 border border-rose-200 text-xs font-semibold flex flex-col items-center gap-0.5 cursor-pointer transition-all"
                  >
                    <span>🔴 Again</span>
                    <span className="text-[10px] opacity-75">1 day</span>
                  </button>
                  <button
                    onClick={() => handleReviewAction(currentStudyCard.id, 'hard')}
                    className="py-2.5 px-2 rounded-xl bg-amber-50 hover:bg-amber-100 text-amber-800 border border-amber-200 text-xs font-semibold flex flex-col items-center gap-0.5 cursor-pointer transition-all"
                  >
                    <span>🟠 Hard</span>
                    <span className="text-[10px] opacity-75">~2 days</span>
                  </button>
                  <button
                    onClick={() => handleReviewAction(currentStudyCard.id, 'good')}
                    className="py-2.5 px-2 rounded-xl bg-emerald-50 hover:bg-emerald-100 text-emerald-800 border border-emerald-200 text-xs font-semibold flex flex-col items-center gap-0.5 cursor-pointer transition-all"
                  >
                    <span>🟢 Good</span>
                    <span className="text-[10px] opacity-75">~6 days</span>
                  </button>
                  <button
                    onClick={() => handleReviewAction(currentStudyCard.id, 'easy')}
                    className="py-2.5 px-2 rounded-xl bg-sky-50 hover:bg-sky-100 text-sky-800 border border-sky-200 text-xs font-semibold flex flex-col items-center gap-0.5 cursor-pointer transition-all"
                  >
                    <span>🔵 Easy</span>
                    <span className="text-[10px] opacity-75">10+ days</span>
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      ) : null}

      {/* Filters & Study Mode Action Bar */}
      <div className="bg-white border border-accent-secondary/50 rounded-2xl p-4 shadow-[0_2px_8px_rgba(0,0,0,0.02)] flex flex-wrap items-center justify-between gap-3 text-xs">
        <div className="flex items-center gap-3">
          <button
            onClick={() => setDueOnly(false)}
            className={`px-3 py-1.5 rounded-lg font-semibold transition-all cursor-pointer ${
              !dueOnly ? 'bg-accent-primary text-white shadow-xs' : 'bg-bg-warm text-text-secondary hover:text-text-primary'
            }`}
          >
            All Cards ({flashcards.length})
          </button>
          <button
            onClick={() => setDueOnly(true)}
            className={`px-3 py-1.5 rounded-lg font-semibold transition-all cursor-pointer flex items-center gap-1.5 ${
              dueOnly ? 'bg-accent-primary text-white shadow-xs' : 'bg-bg-warm text-text-secondary hover:text-text-primary'
            }`}
          >
            <span>⏰ Due for Review</span>
          </button>
        </div>

        <div className="flex items-center gap-3">
          <select
            value={selectedDocFilter}
            onChange={(e) => setSelectedDocFilter(e.target.value)}
            className="bg-bg-warm border border-accent-secondary/60 rounded-lg px-2.5 py-1.5 text-xs text-text-primary outline-none cursor-pointer"
          >
            <option value="">All Documents</option>
            {documents.map((d) => (
              <option key={d.id} value={d.id}>{d.filename}</option>
            ))}
          </select>

          {flashcards.length > 0 && !studyMode && (
            <button
              onClick={startStudySession}
              className="bg-status-success hover:opacity-90 text-white font-semibold px-4 py-1.5 rounded-lg transition-all cursor-pointer shadow-xs"
            >
              ▶ Start Review Session
            </button>
          )}
        </div>
      </div>

      {/* Cards Deck Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {isLoading ? (
          <div className="col-span-2 h-40 rounded-2xl border border-accent-secondary/40 bg-white flex items-center justify-center">
            <span className="text-xs text-text-muted">Loading flashcards...</span>
          </div>
        ) : flashcards.length === 0 ? (
          <div className="col-span-2 h-52 rounded-2xl border border-dashed border-accent-secondary bg-white flex flex-col items-center justify-center p-6 text-center">
            <span className="text-3xl mb-2">🗂️</span>
            <p className="font-serif font-bold text-sm text-text-primary">No flashcards found</p>
            <p className="text-xs text-text-muted mt-1 max-w-sm">
              Generate flashcards from your uploaded research papers using Groq, or manually create one above.
            </p>
          </div>
        ) : (
          flashcards.map((card) => {
            const isDue = new Date(card.next_review_date) <= new Date();

            return (
              <div
                key={card.id}
                className="bg-white border border-accent-secondary/50 rounded-2xl p-5 shadow-[0_2px_8px_rgba(0,0,0,0.02)] flex flex-col justify-between space-y-4 hover:border-accent-primary/50 transition-all"
              >
                <div>
                  <div className="flex items-center justify-between text-[10px] text-text-muted mb-2">
                    <span className="font-semibold text-accent-tertiary truncate max-w-[200px]">
                      📄 {card.filename} {card.page_number ? `(p. ${card.page_number})` : ''}
                    </span>
                    <div className="flex items-center gap-1.5">
                      <span className={`px-2 py-0.5 rounded-full font-bold ${
                        isDue ? 'bg-rose-50 text-rose-700 border border-rose-200' : 'bg-bg-warm text-text-muted'
                      }`}>
                        {isDue ? 'Due' : `In ${card.interval_days}d`}
                      </span>
                      <button
                        onClick={() => handleDeleteCard(card.id)}
                        className="hover:text-status-error text-xs cursor-pointer ml-1"
                        title="Delete card"
                      >
                        &times;
                      </button>
                    </div>
                  </div>

                  <h4 className="font-serif font-bold text-sm text-text-primary leading-snug">
                    {card.question}
                  </h4>
                  <p className="text-xs text-text-secondary font-serif mt-2 line-clamp-3 bg-bg-warm/30 p-2.5 rounded-xl border border-accent-secondary/20">
                    {card.answer}
                  </p>
                </div>

                <div className="pt-2 border-t border-bg-warm flex items-center justify-between text-[10px] text-text-muted font-mono">
                  <span>Repetitions: {card.repetitions}</span>
                  <span>Ease: {card.ease_factor}</span>
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* AI Generate Modal */}
      {showGenerateModal && (
        <div className="fixed inset-0 bg-text-primary/20 backdrop-blur-xs flex items-center justify-center z-50">
          <div className="bg-white border border-accent-secondary rounded-2xl w-full max-w-md p-6 space-y-4 shadow-xl">
            <div className="flex items-center justify-between border-b border-bg-warm pb-3">
              <h3 className="font-serif font-bold text-base text-text-primary">Generate Flashcards with AI</h3>
              <button onClick={() => setShowGenerateModal(false)} className="text-text-muted hover:text-text-primary text-xl cursor-pointer">
                &times;
              </button>
            </div>

            <form onSubmit={handleGenerate} className="space-y-4 text-xs">
              <div className="space-y-1">
                <label className="text-[10px] font-bold uppercase tracking-wider text-text-secondary">Source Document</label>
                <select
                  value={generateDocId}
                  onChange={(e) => setGenerateDocId(e.target.value)}
                  required
                  className="w-full bg-bg-warm border border-accent-secondary rounded-lg px-3 py-2 text-xs text-text-primary outline-none cursor-pointer"
                >
                  <option value="">-- Choose an Indexed Document --</option>
                  {documents.filter(d => d.status === 'indexed').map((d) => (
                    <option key={d.id} value={d.id}>{d.filename}</option>
                  ))}
                </select>
              </div>

              <div className="space-y-1">
                <label className="text-[10px] font-bold uppercase tracking-wider text-text-secondary">Number of Flashcards</label>
                <select
                  value={generateCount}
                  onChange={(e) => setGenerateCount(parseInt(e.target.value))}
                  className="w-full bg-bg-warm border border-accent-secondary rounded-lg px-3 py-2 text-xs text-text-primary outline-none cursor-pointer"
                >
                  <option value="2">2 Cards</option>
                  <option value="3">3 Cards</option>
                  <option value="5">5 Cards</option>
                </select>
              </div>

              <div className="flex justify-end gap-2 pt-2 border-t border-bg-warm">
                <button
                  type="button"
                  onClick={() => setShowGenerateModal(false)}
                  className="px-4 py-2 rounded-lg bg-bg-warm text-text-secondary hover:text-text-primary font-semibold text-xs cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isGenerating || !generateDocId}
                  className="px-4 py-2 rounded-lg bg-accent-primary hover:bg-accent-tertiary disabled:opacity-50 text-white font-semibold text-xs cursor-pointer transition-all"
                >
                  {isGenerating ? 'Generating...' : 'Generate Flashcards'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Manual Create Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-text-primary/20 backdrop-blur-xs flex items-center justify-center z-50">
          <div className="bg-white border border-accent-secondary rounded-2xl w-full max-w-md p-6 space-y-4 shadow-xl">
            <div className="flex items-center justify-between border-b border-bg-warm pb-3">
              <h3 className="font-serif font-bold text-base text-text-primary">Create Flashcard</h3>
              <button onClick={() => setShowCreateModal(false)} className="text-text-muted hover:text-text-primary text-xl cursor-pointer">
                &times;
              </button>
            </div>

            <form onSubmit={handleManualCreate} className="space-y-4 text-xs">
              <div className="space-y-1">
                <label className="text-[10px] font-bold uppercase tracking-wider text-text-secondary">Linked Document</label>
                <select
                  value={manualDocId}
                  onChange={(e) => setManualDocId(e.target.value)}
                  required
                  className="w-full bg-bg-warm border border-accent-secondary rounded-lg px-3 py-2 text-xs text-text-primary outline-none cursor-pointer"
                >
                  <option value="">-- Choose Document --</option>
                  {documents.map((d) => (
                    <option key={d.id} value={d.id}>{d.filename}</option>
                  ))}
                </select>
              </div>

              <div className="space-y-1">
                <label className="text-[10px] font-bold uppercase tracking-wider text-text-secondary">Question</label>
                <input
                  type="text"
                  value={manualQuestion}
                  onChange={(e) => setManualQuestion(e.target.value)}
                  required
                  placeholder="e.g. What is the complexity of standard self-attention?"
                  className="w-full bg-bg-warm border border-accent-secondary rounded-lg px-3 py-2 text-xs text-text-primary outline-none"
                />
              </div>

              <div className="space-y-1">
                <label className="text-[10px] font-bold uppercase tracking-wider text-text-secondary">Answer</label>
                <textarea
                  value={manualAnswer}
                  onChange={(e) => setManualAnswer(e.target.value)}
                  required
                  rows={3}
                  placeholder="Grounded answer..."
                  className="w-full bg-bg-warm border border-accent-secondary rounded-lg px-3 py-2 text-xs text-text-primary outline-none"
                />
              </div>

              <div className="space-y-1">
                <label className="text-[10px] font-bold uppercase tracking-wider text-text-secondary">Source Citation (Optional)</label>
                <textarea
                  value={manualSnippet}
                  onChange={(e) => setManualSnippet(e.target.value)}
                  rows={2}
                  placeholder="Direct quotation from paper..."
                  className="w-full bg-bg-warm border border-accent-secondary rounded-lg px-3 py-2 text-xs text-text-primary outline-none"
                />
              </div>

              <div className="flex justify-end gap-2 pt-2 border-t border-bg-warm">
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="px-4 py-2 rounded-lg bg-bg-warm text-text-secondary hover:text-text-primary font-semibold text-xs cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 rounded-lg bg-accent-primary hover:bg-accent-tertiary text-white font-semibold text-xs cursor-pointer"
                >
                  Save Card
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
