"use client";

/**
 * Sources Sidebar - Left panel with uploaded documents
 * Checkbox = select for chat, Click title = view summary
 * Features async upload with progress tracking
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { useWorkspaceStore } from "@/store/workspaceStore";
import { useUploadProgress } from "@/hooks/useUploadProgress";

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
    } = useWorkspaceStore();

    const [uploadError, setUploadError] = useState<string | null>(null);
    const [uploadTaskId, setUploadTaskId] = useState<string | null>(null);

    const fileInputRef = useRef<HTMLInputElement>(null);

    // Use the upload progress hook
    const { status: uploadStatus, progress, error: uploadProgressError, isComplete, isFailed, reset: resetUpload } = useUploadProgress(uploadTaskId);

    // Fetch sources from API
    const fetchSources = useCallback(async () => {
        setLoadingSources(true);
        try {
            const response = await fetch("http://localhost:8000/api/v1/sources");
            if (response.ok) {
                const data = await response.json();
                setSources(data.sources || []);
            }
        } catch (error) {
            console.error("Failed to fetch sources:", error);
        } finally {
            setLoadingSources(false);
        }
    }, [setSources, setLoadingSources]);

    // Fetch sources on mount
    useEffect(() => {
        fetchSources();
    }, [fetchSources]);

    // When upload completes, refresh sources and reset
    useEffect(() => {
        if (isComplete) {
            fetchSources();
            // Reset after a brief delay to show 100% completion
            setTimeout(() => {
                setUploadTaskId(null);
                resetUpload();
            }, 1000);
        }
    }, [isComplete, fetchSources, resetUpload]);

    // Handle upload failure
    useEffect(() => {
        if (isFailed && uploadProgressError) {
            setUploadError(uploadProgressError);
            setUploadTaskId(null);
            resetUpload();
        }
    }, [isFailed, uploadProgressError, resetUpload]);

    // Handle clicking source title to view summary
    const handleViewSource = async (sourceId: string) => {
        setActiveSource(sourceId);

        // Try to fetch actual briefing from API
        setLoadingGuide(true);
        try {
            const response = await fetch(`http://localhost:8000/api/v1/sources/${sourceId}/briefing`);
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

    // Handle file upload - now returns immediately with task_id
    const handleFileUpload = async (file: File) => {
        setUploadError(null);
        setUploadTaskId(null);

        try {
            const formData = new FormData();
            formData.append("file", file);

            const response = await fetch("http://localhost:8000/api/v1/sources/upload", {
                method: "POST",
                body: formData,
            });

            if (!response.ok) {
                let errorMessage = `Upload failed: ${response.status}`;
                try {
                    const errorData = await response.json();
                    if (errorData.error && errorData.error.message) {
                        errorMessage = errorData.error.message;
                    } else if (errorData.detail) {
                        errorMessage = errorData.detail;
                    }
                } catch {
                    // Could not parse JSON, use default message
                }
                setUploadError(errorMessage);
                return;
            }

            // Get task_id and start polling
            const data = await response.json();
            if (data.task_id) {
                setUploadTaskId(data.task_id);
            }
        } catch (error) {
            console.error("Upload error:", error);
            setUploadError("Upload failed. Please try again.");
        }
    };

    const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
        setUploadError(null);
        const file = e.target.files?.[0];
        if (file) {
            handleFileUpload(file);
        }
        if (fileInputRef.current) {
            fileInputRef.current.value = "";
        }
    };

    const handleDeleteSource = async (sourceId: string, e: React.MouseEvent) => {
        e.stopPropagation();
        try {
            const response = await fetch(`http://localhost:8000/api/v1/sources/${sourceId}`, {
                method: "DELETE",
            });
            if (response.ok) {
                await fetchSources();
                if (activeSourceId === sourceId) {
                    setActiveSource(null);
                }
            }
        } catch (error) {
            console.error("Delete error:", error);
        }
    };

    return (
        <div className="flex flex-col h-full" data-testid="sources-sidebar">
            {/* Header */}
            <div className="panel-header flex items-center justify-between">
                <span>Sources</span>
                <button
                    onClick={() => fileInputRef.current?.click()}
                    className="text-xs text-cyber-blue hover:text-white transition-colors"
                    data-testid="add-source-btn"
                >
                    + Add
                </button>
                <input
                    ref={fileInputRef}
                    type="file"
                    accept=".pdf,.md,.txt,.docx"
                    onChange={handleFileSelect}
                    className="hidden"
                />
            </div>

            {/* Selection hint */}
            {sources.length > 0 && (
                <div className="px-3 py-2 text-xs theme-text-faint border-b border-glass">
                    ☑️ = Chat with • Click title = View summary
                </div>
            )}

            {/* Sources List */}
            <div className="flex-1 overflow-y-auto p-3 space-y-2">
                {/* Upload Progress Bar */}
                {uploadTaskId && (
                    <div className="p-3 bg-cyber-blue/10 border border-cyber-blue/20 rounded-xl mb-2" data-testid="upload-progress">
                        <div className="flex items-center justify-between mb-2">
                            <span className="text-xs text-cyber-blue">
                                {uploadStatus === "processing" ? "Processing..." : "Uploading..."}
                            </span>
                            <span className="text-xs theme-text-muted">{progress}%</span>
                        </div>
                        <div className="w-full h-2 bg-glass-100 rounded-full overflow-hidden">
                            <div
                                className="h-full bg-cyber-blue transition-all duration-300 rounded-full"
                                style={{ width: `${progress}%` }}
                            />
                        </div>
                    </div>
                )}
                {uploadError && (
                    <div className="p-3 bg-red-500/10 border border-red-500/20 rounded-xl text-xs text-red-400 mb-2 flex items-center justify-between">
                        <span>{uploadError}</span>
                        <button
                            onClick={() => setUploadError(null)}
                            className="ml-2 hover:text-red-300"
                            title="Dismiss"
                        >
                            ✕
                        </button>
                    </div>
                )}
                {isLoadingSources ? (
                    <div className="text-xs theme-text-muted text-center py-8">
                        Loading sources...
                    </div>
                ) : sources.length === 0 ? (
                    <div
                        className="text-center py-8 px-4 border-2 border-dashed border-glass rounded-xl cursor-pointer hover:border-cyber-blue/50 transition-colors"
                        onClick={() => fileInputRef.current?.click()}
                    >
                        <div className="text-3xl mb-2">📄</div>
                        <div className="text-sm theme-text-muted">Add your first source</div>
                        <div className="text-xs theme-text-faint mt-1">
                            PDF, Markdown, or TXT
                        </div>
                    </div>
                ) : (
                    sources.map((source) => {
                        const isSelected = selectedSourceIds.includes(source.id);
                        const isActive = activeSourceId === source.id;

                        return (
                            <div
                                key={source.id}
                                className={`source-file-card ${isActive ? 'active' : ''}`}
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

                                {/* Source icon */}
                                <div
                                    className="w-10 h-10 rounded-lg bg-cyber-purple/20 flex items-center justify-center shrink-0 cursor-pointer"
                                    onClick={() => handleViewSource(source.id)}
                                >
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
                                        <span>{source.status === "ready" ? "✓ Ready" : "⏳ Processing..."}</span>
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
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
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

