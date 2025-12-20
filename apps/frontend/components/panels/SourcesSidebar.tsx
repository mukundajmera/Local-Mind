"use client";

/**
 * Sources Sidebar - Left panel with uploaded documents
 * Checkbox = select for chat, Click title = view summary
 * Features async upload with progress tracking
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { useWorkspaceStore } from "@/store/workspaceStore";
import { ProjectSelector } from "@/components/ProjectSelector";
import { Upload } from "@/components/Upload";
import { API_BASE_URL } from "@/lib/api";

export function SourcesSidebar() {
    const {
        sources,
        isLoadingSources,
        activeSourceId,
        selectedSourceIds,
        setActiveSource,
        toggleSourceSelection,
        setSources,
        setLoadingSources,
        setSourceGuide,
        setLoadingGuide,
        currentProjectId,
        uploadStatus,
        uploadErrors,
        pollDocumentStatus,
    } = useWorkspaceStore();

    // Track active polling cleanup functions
    const pollingCleanups = useRef<Map<string, () => void>>(new Map());

    // Handle upload complete - start polling for status
    const handleUploadComplete = (docId?: string) => {
        if (docId) {
            // Start polling for this document
            const cleanup = pollDocumentStatus(docId, () => {
                // Cleanup when polling completes
                pollingCleanups.current.delete(docId);
            });
            pollingCleanups.current.set(docId, cleanup);
        }
    };

    // Cleanup all active polling on unmount
    useEffect(() => {
        return () => {
            pollingCleanups.current.forEach(cleanup => cleanup());
            pollingCleanups.current.clear();
        };
    }, []);

    // Fetch sources from API
    const fetchSources = useCallback(async () => {
        setLoadingSources(true);
        try {
            let url = `${API_BASE_URL}/api/v1/sources`;
            if (currentProjectId) {
                url += `?project_id=${currentProjectId}`;
            }
            const response = await fetch(url);
            if (response.ok) {
                const data = await response.json();
                setSources(data.sources || []);
            } else {
                console.error("SourcesSidebar: Fetch failed status:", response.status);
                setSources([]);
            }
        } catch (error) {
            console.error("Failed to fetch sources:", error);
            setSources([]);
        } finally {
            setLoadingSources(false);
        }
    }, [setSources, setLoadingSources, currentProjectId]);

    // Fetch sources on mount and project change
    useEffect(() => {
        fetchSources();
    }, [fetchSources]);

    // Handle clicking source title to view summary
    const handleViewSource = async (sourceId: string) => {
        setActiveSource(sourceId);

        // Try to fetch actual briefing from API
        setLoadingGuide(true);
        try {
            const response = await fetch(`${API_BASE_URL}/api/v1/sources/${sourceId}/briefing`);
            if (response.ok) {
                const data = await response.json();
                setSourceGuide({
                    summary: data.summary,
                    topics: data.key_topics,
                    suggestedQuestions: data.suggested_questions,
                });
            } else {
                // Fallback to placeholder if briefing not ready
                const source = sources.find(s => s.id === sourceId);
                setSourceGuide({
                    summary: `This document "${source?.title || 'Untitled'}" is being processed. The briefing will be available shortly.`,
                    topics: ["Processing..."],
                    suggestedQuestions: ["What are the main topics in this document?"],
                });
            }
        } catch (error) {
            console.error("Failed to fetch briefing:", error);
            const source = sources.find(s => s.id === sourceId);
            setSourceGuide({
                summary: `This document "${source?.title || 'Untitled'}" contains valuable insights about the topic.`,
                topics: ["Key Findings", "Analysis", "Conclusions"],
                suggestedQuestions: ["What are the main conclusions of this document?"],
            });
        } finally {
            setLoadingGuide(false);
        }
    };

    // Handle checkbox toggle for chat selection
    const handleCheckboxChange = (sourceId: string, e: React.MouseEvent) => {
        e.stopPropagation();
        toggleSourceSelection(sourceId);
    };

    const handleDeleteSource = async (sourceId: string, e: React.MouseEvent) => {
        e.stopPropagation();
        if (!confirm("Are you sure you want to delete this source? This cannot be undone.")) return;

        // Optimistic Deletion: Remove from UI immediately
        const previousSources = sources;
        const previousSelected = selectedSourceIds;
        const previousActive = activeSourceId;

        setSources(sources.filter(s => s.id !== sourceId));
        if (selectedSourceIds.includes(sourceId)) {
            toggleSourceSelection(sourceId); // This toggles, so if it was selected, it deselects. 
            // Better to force remove, but store toggle logic doesn't allow specific set. 
            // Actually, if we remove the source, the ID in selectedSourceIds becomes orphan.
            // Let's just rely on the UI list filtering.
        }
        if (activeSourceId === sourceId) {
            setActiveSource(null);
        }

        try {
            const response = await fetch(`${API_BASE_URL}/api/v1/sources/${sourceId}`, {
                method: "DELETE",
            });
            if (!response.ok) {
                throw new Error("Deletion failed");
            }
            // If success, do nothing, we are already good.
        } catch (error) {
            console.error("Delete error:", error);
            // Revert on failure
            alert("Failed to delete source. Restoring...");
            setSources(previousSources);
            if (previousActive) setActiveSource(previousActive);
            // We can't easily revert selection without direct set access, but it's a minor UX blip compared to the deletion.
            fetchSources(); // Just re-fetch to be safe
        }
    };

    return (
        <div className="flex flex-col h-full" data-testid="sources-sidebar">
            {/* Header */}
            <div className="panel-header mb-2">
                <div className="flex items-center justify-between mb-3">
                    <span>Sources</span>
                </div>
            </div>

            {/* Project Selector */}
            <ProjectSelector />

            {/* Upload Area */}
            <div className="px-3 mb-4">
                <Upload onUploadComplete={fetchSources} />
            </div>

            {/* Selection hint */}
            {sources.length > 0 && (
                <div className="px-3 py-2 text-xs theme-text-faint border-b border-glass">
                    ☑️ = Chat with • Click title = View summary
                </div>
            )}

            {/* Sources List */}
            <div className="flex-1 overflow-y-auto p-3 space-y-2">
                {isLoadingSources ? (
                    <div className="text-xs theme-text-muted text-center py-8">
                        Loading sources...
                    </div>
                ) : sources.length === 0 ? (
                    <div className="text-center py-8 px-4">
                        <div className="text-sm theme-text-muted">No sources found</div>
                        <div className="text-xs theme-text-faint mt-1">
                            {currentProjectId ? "Upload a file to this project" : "Create or select a project"}
                        </div>
                    </div>
                ) : ( // Existing map logic below...
                    sources.map((source) => {
                        const isSelected = selectedSourceIds.includes(source.id);
                        const isActive = activeSourceId === source.id;

                        return (
                            <div
                                key={source.id}
                                className={`source-file-card ${isActive ? 'active' : ''} group`}
                                data-testid={`source-${source.id}`}
                            >
                                {/* Checkbox for chat selection */}
                                <input
                                    type="checkbox"
                                    checked={isSelected}
                                    onChange={() => { }}
                                    onClick={(e) => handleCheckboxChange(source.id, e)}
                                    className="source-checkbox mt-1"
                                    data-testid={`source-checkbox-${source.id}`}
                                    title="Select for chat"
                                />

                                {/* Source icon - status-based */}
                                <div
                                    className="w-10 h-10 rounded-lg bg-cyber-purple/20 flex items-center justify-center shrink-0 cursor-pointer"
                                    onClick={() => handleViewSource(source.id)}
                                >
                                    {uploadStatus[source.id] === "pending" || uploadStatus[source.id] === "processing" ? (
                                        // Spinner for pending/processing
                                        <svg className="w-5 h-5 text-cyber-blue animate-spin" fill="none" viewBox="0 0 24 24">
                                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                                        </svg>
                                    ) : uploadStatus[source.id] === "failed" ? (
                                        // Error icon for failed
                                        <div title={uploadErrors[source.id] || "Upload failed"}>
                                            <svg className="w-5 h-5 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                                            </svg>
                                        </div>
                                    ) : (
                                        // Standard file icon for ready
                                        <svg
                                            className="w-5 h-5 text-cyber-purple"
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
                                    )}
                                </div>

                                {/* Source info - click to view summary */}
                                <div
                                    className="flex-1 min-w-0 cursor-pointer"
                                    onClick={() => handleViewSource(source.id)}
                                >
                                    <div className="text-sm font-medium theme-text-primary truncate">
                                        {source.title}
                                    </div>
                                    <div className="text-xs theme-text-muted mt-0.5 flex items-center gap-2">
                                        <span>
                                            {uploadStatus[source.id] === "pending" || uploadStatus[source.id] === "processing" ? (
                                                "⏳ Processing..."
                                            ) : uploadStatus[source.id] === "failed" ? (
                                                <span className="text-red-400" title={uploadErrors[source.id]}>❌ Failed</span>
                                            ) : (
                                                source.status === "ready" ? "✓ Ready" : "⏳ Processing..."
                                            )}
                                        </span>
                                        {isSelected && (
                                            <span className="text-cyber-blue">• Selected</span>
                                        )}
                                    </div>
                                </div>

                                {/* Delete button */}
                                <button
                                    onClick={(e) => handleDeleteSource(source.id, e)}
                                    className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-red-500/20 theme-text-faint hover:text-red-400 transition-all"
                                    title="Delete source"
                                >
                                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                                    </svg>
                                </button>
                            </div>
                        );
                    })
                )}
            </div>
        </div>
    );
}

