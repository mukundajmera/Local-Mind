"use client";

/**
 * Sources Sidebar - Left panel with uploaded documents
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { useWorkspaceStore } from "@/store/workspaceStore";

export function SourcesSidebar() {
    const {
        sources,
        isLoadingSources,
        activeSourceId,
        setActiveSource,
        setSources,
        setLoadingSources,
        setSourceGuide,
        setLoadingGuide,
    } = useWorkspaceStore();

    const [uploadError, setUploadError] = useState<string | null>(null);

    const fileInputRef = useRef<HTMLInputElement>(null);

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

    // Handle source selection
    const handleSelectSource = async (sourceId: string) => {
        setActiveSource(sourceId);

        // Mock source guide data for now
        // TODO: Replace with actual API call to /api/v1/sources/{id}/guide
        setLoadingGuide(true);
        await new Promise(resolve => setTimeout(resolve, 500)); // Simulate loading

        const source = sources.find(s => s.id === sourceId);
        setSourceGuide({
            summary: `This document "${source?.title || 'Untitled'}" contains valuable insights about the topic. The key themes include research findings, methodology, and conclusions drawn from the analysis.`,
            topics: ["Research Methods", "Key Findings", "Analysis", "Conclusions", "Future Work"],
            suggestedQuestions: [
                "What are the main conclusions of this document?",
                "How does the methodology compare to other approaches?",
                "What are the key findings and their implications?",
            ],
        });
        setLoadingGuide(false);
    };

    // Handle file upload
    const handleFileUpload = async (file: File) => {
        setUploadError(null);
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
                    }
                } catch (e) {
                    // Could not parse JSON, use default message
                }
                setUploadError(errorMessage);
                return;
            }

            // Refresh sources
            await fetchSources();
        } catch (error) {
            console.error("Upload error:", error);
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

            {/* Sources List */}
            <div className="flex-1 overflow-y-auto p-3 space-y-2">
                {uploadError && (
                    <div className="p-3 bg-red-500/10 border border-red-500/20 rounded-xl text-xs text-red-400 mb-2">
                        {uploadError}
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
                    sources.map((source) => (
                        <div
                            key={source.id}
                            onClick={() => handleSelectSource(source.id)}
                            className={`group flex items-start gap-3 p-3 rounded-xl cursor-pointer transition-all ${activeSourceId === source.id
                                ? "bg-cyber-blue/20 border border-cyber-blue/40"
                                : "hover:bg-glass-100 border border-transparent"
                                }`}
                            data-testid={`source-${source.id}`}
                        >
                            <div className="w-10 h-10 rounded-lg bg-cyber-purple/20 flex items-center justify-center shrink-0">
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
                            <div className="flex-1 min-w-0">
                                <div className="text-sm font-medium theme-text-primary truncate">
                                    {source.title}
                                </div>
                                <div className="text-xs theme-text-muted mt-0.5">
                                    {source.status === "ready" ? "✓ Ready" : "⏳ Processing..."}
                                </div>
                            </div>
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
                    ))
                )}
            </div>
        </div>
    );
}
