"use client";

/**
 * Knowledge Panel - Left sidebar with graph and sources
 */

import { useMemo, useState, useEffect, useRef, useCallback } from "react";
import { GraphView } from "@/components/GraphView";
import { useGraphStore, useFocusedNode, useGraphData } from "@/store/graphStore";
import { useUIStore } from "@/store/uiStore";
import { CollapseIcon } from "../primitives/CollapseIcon";

interface Source {
    id: string;
    title: string;
    filename: string;
    pages?: number;
    uploaded_at: string;
    status: string;
}

export function KnowledgePanel() {
    const focusedNode = useFocusedNode();
    const graphData = useGraphData();
    const { clearFocus, toggleNodeSelection, selectedNodeIds, setGraphData } = useGraphStore();
    const [systemNotice, setSystemNotice] = useState<string | null>(null);

    // Sources state
    const [sources, setSources] = useState<Source[]>([]);
    const [isLoadingSources, setIsLoadingSources] = useState(false);
    const [isUploading, setIsUploading] = useState(false);
    const [showUploadModal, setShowUploadModal] = useState(false);
    const fileInputRef = useRef<HTMLInputElement>(null);

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

    // Fetch sources from API
    const fetchSources = useCallback(async () => {
        setIsLoadingSources(true);
        try {
            const response = await fetch("http://localhost:8000/api/v1/sources");
            if (response.ok) {
                const data = await response.json();
                setSources(data.sources || []);
            }
        } catch (error) {
            console.error("Failed to fetch sources:", error);
        } finally {
            setIsLoadingSources(false);
        }
    }, []);

    // Fetch graph data from API
    const fetchGraphData = useCallback(async () => {
        try {
            const response = await fetch("http://localhost:8000/api/v1/graph");
            if (response.ok) {
                const data = await response.json();
                if (data.nodes && data.nodes.length > 0) {
                    setGraphData(data);
                }
            }
        } catch (error) {
            console.error("Failed to fetch graph:", error);
        }
    }, [setGraphData]);

    // Fetch data on mount
    useEffect(() => {
        fetchSources();
        fetchGraphData();
    }, [fetchSources, fetchGraphData]);

    // Handle file upload
    const handleFileUpload = async (file: File) => {
        setIsUploading(true);
        appendNotice(`Uploading ${file.name}...`);

        try {
            const formData = new FormData();
            formData.append("file", file);

            const response = await fetch("http://localhost:8000/api/v1/sources/upload", {
                method: "POST",
                body: formData,
            });

            if (!response.ok) {
                const error = await response.json().catch(() => ({ detail: "Upload failed" }));
                throw new Error(error.detail || `HTTP ${response.status}`);
            }

            const result = await response.json();
            appendNotice(`✓ Uploaded ${file.name}: ${result.chunks_created} chunks, ${result.entities_extracted} entities`);

            // Refresh sources and graph
            await fetchSources();
            await fetchGraphData();
        } catch (error) {
            console.error("Upload error:", error);
            appendNotice(`✗ Upload failed: ${error instanceof Error ? error.message : "Unknown error"}`);
        } finally {
            setIsUploading(false);
            setShowUploadModal(false);
        }
    };

    const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (file) {
            handleFileUpload(file);
        }
        // Reset input
        if (fileInputRef.current) {
            fileInputRef.current.value = "";
        }
    };

    const handleDrop = (e: React.DragEvent) => {
        e.preventDefault();
        const file = e.dataTransfer.files?.[0];
        if (file) {
            handleFileUpload(file);
        }
    };

    const handleDragOver = (e: React.DragEvent) => {
        e.preventDefault();
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
                    <span>Sources ({sources.length})</span>
                    <button
                        className="text-xs text-cyber-blue hover:text-white transition-colors flex items-center gap-1"
                        onClick={() => fileInputRef.current?.click()}
                        disabled={isUploading}
                        data-testid="sources-add"
                    >
                        {isUploading ? "Uploading..." : "+ Add Source"}
                    </button>
                    <input
                        ref={fileInputRef}
                        type="file"
                        accept=".pdf,.md,.txt,.docx"
                        onChange={handleFileSelect}
                        className="hidden"
                        data-testid="file-input"
                    />
                </div>
                <div
                    className="p-2 space-y-1 max-h-40 overflow-y-auto"
                    data-testid="sources-list"
                    onDrop={handleDrop}
                    onDragOver={handleDragOver}
                >
                    {isLoadingSources ? (
                        <div className="text-xs text-white/50 text-center py-4">Loading sources...</div>
                    ) : sources.length === 0 ? (
                        <div
                            className="text-xs text-white/50 text-center py-4 border-2 border-dashed border-glass rounded-lg cursor-pointer hover:border-cyber-blue/50 transition-colors"
                            onClick={() => fileInputRef.current?.click()}
                        >
                            <div className="mb-1">📄</div>
                            <div>Drop files here or click to upload</div>
                            <div className="text-white/30 mt-1">PDF, Markdown, or TXT</div>
                        </div>
                    ) : (
                        sources.map((source) => (
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
                                        {source.status === "ready" ? "✓ Ready" : "⏳ Processing..."}
                                    </div>
                                </div>
                            </div>
                        ))
                    )}
                </div>
            </div>
        </div>
    );
}
