"use client";

/**
 * Knowledge Panel - Left sidebar with graph and sources
 */

import { useMemo, useState } from "react";
import { GraphView } from "@/components/GraphView";
import { useGraphStore, useFocusedNode, useGraphData } from "@/store/graphStore";

// Sample sources for development
const SAMPLE_SOURCES = [
    { id: "1", title: "Quantum Computing Fundamentals.pdf", pages: 42 },
    { id: "2", title: "Google Sycamore Paper.pdf", pages: 18 },
    { id: "3", title: "IBM Quantum Research Notes.pdf", pages: 96 },
    { id: "4", title: "Nvidia QODA Launch.md", pages: 12 },
    { id: "5", title: "Microsoft Quantum Architecture.pdf", pages: 67 },
];

export function KnowledgePanel() {
    const focusedNode = useFocusedNode();
    const graphData = useGraphData();
    const { clearFocus, toggleNodeSelection, selectedNodeIds } = useGraphStore();
    const [systemNotice, setSystemNotice] = useState<string | null>(null);

    const summary = useMemo(() => {
        const totalNodes = graphData.nodes.length;
        const totalLinks = graphData.links.length;
        const selectedCount = selectedNodeIds.size;
        return { totalNodes, totalLinks, selectedCount };
    }, [graphData.nodes.length, graphData.links.length, selectedNodeIds]);

    const appendNotice = (message: string) => {
        setSystemNotice(message);
        setTimeout(() => setSystemNotice(null), 4000);
    };

    return (
        <div className="flex flex-col h-full" data-testid="knowledge-panel">
            {/* Header */}
            <div className="panel-header flex items-center justify-between" data-testid="knowledge-header">
                <span>Knowledge Graph</span>
                <div className="flex items-center gap-3">
                    <span className="text-xs text-white/50" data-testid="knowledge-summary">
                        {summary.totalNodes} nodes • {summary.totalLinks} edges • {summary.selectedCount} selected
                    </span>
                    {(focusedNode || summary.selectedCount > 0) && (
                        <button
                            onClick={clearFocus}
                            className="text-xs text-cyber-blue hover:text-white transition-colors"
                            data-testid="clear-focus"
                        >
                            Clear Focus
                        </button>
                    )}
                </div>
            </div>

            {/* Graph Visualization */}
            <div className="flex-1 min-h-0 relative" data-testid="graph-container">
                <GraphView />

                {/* Focused node info overlay */}
                {focusedNode && (
                    <div className="absolute bottom-4 left-4 right-4 glass-panel-elevated p-3" data-testid="focus-overlay">
                        <div className="flex items-center gap-2 mb-1">
                            <span className="text-xs px-2 py-0.5 rounded-full bg-cyber-blue/20 text-cyber-blue">
                                {focusedNode.type}
                            </span>
                            <span className="text-sm font-medium text-white">
                                {focusedNode.name}
                            </span>
                        </div>
                        {focusedNode.description && (
                            <p className="text-xs text-white/60 line-clamp-2">
                                {focusedNode.description}
                            </p>
                        )}
                        <div className="flex items-center gap-2 mt-3">
                            <button
                                onClick={() => focusedNode && toggleNodeSelection(focusedNode.id)}
                                className="text-xs px-3 py-1.5 rounded-full bg-glass-100 text-white/70 hover:text-white hover:bg-glass-200"
                                data-testid="focus-toggle-selection"
                            >
                                {focusedNode && selectedNodeIds.has(focusedNode.id) ? "Remove from Context" : "Add to Context"}
                            </button>
                            <button
                                onClick={() => appendNotice("Focus dismissed.")}
                                className="text-xs px-3 py-1.5 rounded-full bg-glass-100 text-white/70 hover:text-white hover:bg-glass-200"
                                data-testid="focus-dismiss"
                            >
                                Dismiss
                            </button>
                        </div>
                    </div>
                )}
            </div>

            {systemNotice && (
                <div className="px-3 py-2 text-xs text-cyber-blue bg-glass-100 border-t border-glass" data-testid="knowledge-notice">
                    {systemNotice}
                </div>
            )}

            {/* Sources section */}
            <div className="border-t border-glass" data-testid="sources-section">
                <div className="panel-header flex items-center justify-between">
                    <span>Sources</span>
                    <button
                        className="text-xs text-cyber-blue hover:text-white transition-colors"
                        onClick={() => appendNotice("Source management coming soon.")}
                        data-testid="sources-manage"
                    >
                        Manage
                    </button>
                </div>
                <div className="p-2 space-y-1 max-h-40 overflow-y-auto" data-testid="sources-list">
                    {SAMPLE_SOURCES.map((source) => (
                        <div
                            key={source.id}
                            className="flex items-center gap-2 p-2 rounded-lg hover:bg-glass-100 cursor-pointer transition-colors"
                            data-testid={`source-${source.id}`}
                            onClick={() => appendNotice(`Selected source: ${source.title}`)}
                        >
                            <div className="w-8 h-8 rounded bg-cyber-purple/20 flex items-center justify-center">
                                <svg
                                    className="w-4 h-4 text-cyber-purple"
                                    fill="none"
                                    stroke="currentColor"
                                    viewBox="0 0 24 24"
                                >
                                    <path
                                        strokeLinecap="round"
                                        strokeLinejoin="round"
                                        strokeWidth={2}
                                        d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                                    />
                                </svg>
                            </div>
                            <div className="flex-1 min-w-0">
                                <div className="text-sm text-white/90 truncate">
                                    {source.title}
                                </div>
                                <div className="text-xs text-white/50">
                                    {source.pages} pages
                                </div>
                            </div>
                        </div>
                    ))}
                </div>
            </div>
        </div>
    );
}
