import React, { useState, useEffect, useMemo } from 'react';
import { api } from '../services/api';

const RELATIONSHIP_COLORS = {
  SUPPORTS: '#059669',    // emerald-600
  CONTRADICTS: '#e11d48', // rose-600
  EXTENDS: '#4f46e5',     // indigo-600
  SIMILAR: '#0284c7',     // sky-600
  ANSWERS: '#9333ea',     // purple-600
  RELATED: '#d97706',     // amber-600
};

export default function KnowledgeGraphView({ typeFilter = '', statusFilter = '' }) {
  const [graphData, setGraphData] = useState({ nodes: [], edges: [] });
  const [isLoading, setIsLoading] = useState(false);
  const [selectedEdge, setSelectedEdge] = useState(null);
  const [selectedNodeId, setSelectedNodeId] = useState(null);

  const loadGraph = async () => {
    setIsLoading(true);
    try {
      const params = {};
      if (typeFilter) params.relationship_type = typeFilter;
      if (statusFilter) params.status = statusFilter;
      const data = await api.getKnowledgeGraph(params);
      setGraphData(data || { nodes: [], edges: [] });
    } catch (err) {
      console.error("Failed to load knowledge graph data:", err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadGraph();
  }, [typeFilter, statusFilter]);

  // Compute node coordinates on a 2D canvas circle layout with central distribution
  const layout = useMemo(() => {
    const nodes = graphData.nodes || [];
    const width = 760;
    const height = 480;
    const centerX = width / 2;
    const centerY = height / 2;
    const radius = Math.min(centerX, centerY) - 80;

    const coords = {};
    const n = nodes.length;

    if (n === 1) {
      coords[nodes[0].id] = { x: centerX, y: centerY };
    } else {
      nodes.forEach((node, i) => {
        const angle = (2 * Math.PI * i) / Math.max(n, 1);
        coords[node.id] = {
          x: centerX + radius * Math.cos(angle),
          y: centerY + radius * Math.sin(angle)
        };
      });
    }

    return { width, height, coords };
  }, [graphData.nodes]);

  if (isLoading) {
    return (
      <div className="h-96 rounded-2xl border border-accent-secondary/40 bg-white flex flex-col items-center justify-center gap-2">
        <svg className="animate-spin h-6 w-6 text-accent-primary" fill="none" viewBox="0 0 24 24">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
        </svg>
        <span className="text-xs text-text-secondary font-semibold">Generating relational document graph...</span>
      </div>
    );
  }

  if (graphData.nodes.length === 0) {
    return (
      <div className="h-80 rounded-2xl border border-dashed border-accent-secondary bg-white flex flex-col items-center justify-center p-6 text-center">
        <span className="text-3xl mb-2">🕸️</span>
        <p className="font-serif font-bold text-sm text-text-primary">No graph entities available</p>
        <p className="text-xs text-text-muted mt-1 max-w-sm">
          Upload research documents and trigger connection discovery to visualize relational networks.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Graph Visualizer SVG Canvas */}
      <div className="relative bg-white border border-accent-secondary/50 rounded-2xl shadow-[0_2px_12px_rgba(0,0,0,0.02)] overflow-hidden">
        
        {/* Graph Legend Overlay */}
        <div className="absolute top-3 left-3 bg-white/90 backdrop-blur-xs border border-accent-secondary/40 rounded-xl px-3 py-2 text-[10px] space-y-1 shadow-xs pointer-events-none z-10">
          <span className="font-bold text-text-primary block uppercase tracking-wider">Relationship Legend</span>
          <div className="flex flex-wrap gap-2">
            {Object.entries(RELATIONSHIP_COLORS).map(([type, color]) => (
              <div key={type} className="flex items-center gap-1">
                <span className="h-2 w-2 rounded-full" style={{ backgroundColor: color }}></span>
                <span className="font-medium text-text-secondary">{type}</span>
              </div>
            ))}
          </div>
        </div>

        <svg
          viewBox={`0 0 ${layout.width} ${layout.height}`}
          className="w-full h-[480px] cursor-grab active:cursor-grabbing select-none"
        >
          <defs>
            {Object.entries(RELATIONSHIP_COLORS).map(([type, color]) => (
              <marker
                key={type}
                id={`arrow-${type}`}
                viewBox="0 0 10 10"
                refX="24"
                refY="5"
                markerWidth="6"
                markerHeight="6"
                orient="auto-start-reverse"
              >
                <path d="M 0 1 L 10 5 L 0 9 z" fill={color} />
              </marker>
            ))}
          </defs>

          {/* Render Edges (Connections) */}
          {graphData.edges.map((edge) => {
            const p1 = layout.coords[edge.source];
            const p2 = layout.coords[edge.target];
            if (!p1 || !p2) return null;

            const isSelected = selectedEdge && selectedEdge.id === edge.id;
            const isConnectedToSelectedNode = selectedNodeId && (edge.source === selectedNodeId || edge.target === selectedNodeId);
            const color = RELATIONSHIP_COLORS[edge.relationship] || '#94a3b8';

            // Calculate midpoint for relationship badge
            const midX = (p1.x + p2.x) / 2;
            const midY = (p1.y + p2.y) / 2;

            return (
              <g key={edge.id} className="cursor-pointer group" onClick={() => setSelectedEdge(edge)}>
                <line
                  x1={p1.x}
                  y1={p1.y}
                  x2={p2.x}
                  y2={p2.y}
                  stroke={color}
                  strokeWidth={isSelected ? 3.5 : isConnectedToSelectedNode ? 2.5 : 1.8}
                  strokeOpacity={isSelected ? 1.0 : selectedEdge ? 0.3 : 0.8}
                  markerEnd={`url(#arrow-${edge.relationship})`}
                  className="transition-all"
                />
                {/* Midpoint Pill */}
                <rect
                  x={midX - 28}
                  y={midY - 8}
                  width="56"
                  height="16"
                  rx="4"
                  fill="white"
                  stroke={color}
                  strokeWidth="1"
                  className="opacity-90 group-hover:opacity-100 transition-opacity"
                />
                <text
                  x={midX}
                  y={midY + 3}
                  textAnchor="middle"
                  fontSize="7.5"
                  fontWeight="bold"
                  fill={color}
                  fontFamily="sans-serif"
                >
                  {edge.relationship}
                </text>
              </g>
            );
          })}

          {/* Render Nodes (Documents) */}
          {graphData.nodes.map((node) => {
            const pos = layout.coords[node.id];
            if (!pos) return null;

            const isSelected = selectedNodeId === node.id;
            const isEdgeEndpoint = selectedEdge && (selectedEdge.source === node.id || selectedEdge.target === node.id);

            return (
              <g
                key={node.id}
                transform={`translate(${pos.x}, ${pos.y})`}
                onClick={() => {
                  setSelectedNodeId(prev => prev === node.id ? null : node.id);
                  if (selectedEdge && selectedEdge.source !== node.id && selectedEdge.target !== node.id) {
                    setSelectedEdge(null);
                  }
                }}
                className="cursor-pointer group"
              >
                {/* Node Outer Glow */}
                <circle
                  r={isSelected || isEdgeEndpoint ? 22 : 18}
                  fill={isSelected || isEdgeEndpoint ? '#4338ca' : '#ffffff'}
                  stroke={isSelected || isEdgeEndpoint ? '#6366f1' : '#cbd5e1'}
                  strokeWidth={isSelected ? 3 : 2}
                  className="transition-all drop-shadow-sm group-hover:scale-105"
                />
                {/* Document Icon */}
                <text
                  textAnchor="middle"
                  dy=".3em"
                  fontSize={isSelected || isEdgeEndpoint ? "11" : "10"}
                  fill={isSelected || isEdgeEndpoint ? "#ffffff" : "#475569"}
                >
                  📄
                </text>
                {/* Document Filename Label */}
                <rect
                  x="-55"
                  y="22"
                  width="110"
                  height="16"
                  rx="4"
                  fill="white"
                  stroke="#e2e8f0"
                  strokeWidth="0.8"
                  className="opacity-95"
                />
                <text
                  textAnchor="middle"
                  y="33"
                  fontSize="8"
                  fontWeight="600"
                  fill="#1e293b"
                  fontFamily="sans-serif"
                  className="truncate"
                >
                  {node.label.length > 18 ? node.label.slice(0, 16) + '...' : node.label}
                </text>
              </g>
            );
          })}
        </svg>

        {/* Instructions banner at bottom */}
        <div className="bg-bg-warm/70 border-t border-accent-secondary/30 px-4 py-2 flex items-center justify-between text-[11px] text-text-secondary">
          <span>Click any line to inspect dual evidence citations • Click any node to highlight connections</span>
          <span className="font-mono text-text-muted">
            {graphData.nodes.length} documents • {graphData.edges.length} relationships
          </span>
        </div>
      </div>

      {/* Selected Edge Evidence Inspection Drawer */}
      {selectedEdge && (
        <div className="bg-white border-2 border-accent-primary/60 rounded-2xl p-5 shadow-lg space-y-4 animate-in fade-in slide-in-from-top-2 duration-200">
          <div className="flex items-center justify-between border-b border-bg-warm pb-3">
            <div className="flex items-center gap-2">
              <span
                className="px-2.5 py-1 rounded-full text-xs font-bold text-white uppercase flex items-center gap-1"
                style={{ backgroundColor: RELATIONSHIP_COLORS[selectedEdge.relationship] || '#6366f1' }}
              >
                <span>🔗</span>
                <span>{selectedEdge.relationship}</span>
              </span>
              <span className="text-xs font-serif font-bold text-text-primary">
                {selectedEdge.source_filename} ↔ {selectedEdge.target_filename}
              </span>
              <span className="text-[10px] text-text-muted font-mono" title="Heuristic confidence score">
                {Math.round((selectedEdge.confidence || 0.8) * 100)}% Confidence
              </span>
            </div>
            <button
              onClick={() => setSelectedEdge(null)}
              className="text-text-muted hover:text-text-primary text-base font-bold cursor-pointer"
            >
              &times;
            </button>
          </div>

          <p className="text-xs text-text-primary font-serif leading-relaxed">
            <strong>Relationship Insight:</strong> {selectedEdge.explanation}
          </p>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
            {/* Source Evidence */}
            <div className="bg-bg-warm/40 border border-accent-secondary/40 rounded-xl p-3 space-y-1">
              <span className="text-[10px] font-bold uppercase tracking-wider text-accent-tertiary block">
                Evidence in {selectedEdge.source_filename} {selectedEdge.source_page ? `(p. ${selectedEdge.source_page})` : ''}
              </span>
              <blockquote className="italic font-serif text-[11px] text-text-primary border-l-2 border-accent-primary pl-2">
                "{selectedEdge.evidence_source}"
              </blockquote>
            </div>

            {/* Target Evidence */}
            <div className="bg-bg-warm/40 border border-accent-secondary/40 rounded-xl p-3 space-y-1">
              <span className="text-[10px] font-bold uppercase tracking-wider text-accent-tertiary block">
                Evidence in {selectedEdge.target_filename} {selectedEdge.target_page ? `(p. ${selectedEdge.target_page})` : ''}
              </span>
              <blockquote className="italic font-serif text-[11px] text-text-primary border-l-2 border-accent-primary pl-2">
                "{selectedEdge.evidence_target}"
              </blockquote>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
