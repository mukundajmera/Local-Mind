"use client";

/**
 * Source Guide - Card-based dashboard for document insights
 * Shows Summary, Key Topics, and Suggested Questions
 */

import { useWorkspaceStore } from "@/store/workspaceStore";

export function SourceGuide() {
    const {
        activeSourceId,
        sourceGuide,
        isLoadingGuide,
        sources,
        setViewMode,
    } = useWorkspaceStore();

    const activeSource = sources.find(s => s.id === activeSourceId);

    // Empty state when no source selected
    if (!activeSourceId) {
        return (
            <div className="empty-state" data-testid="empty-state">
                <div className="empty-state-icon">📚</div>
                <h2 className="empty-state-title">
                    Get Started with Local Mind
                </h2>
                <p className="empty-state-description">
                    Upload documents and start exploring with AI. Here&apos;s how:
                </p>

                <div className="w-full max-w-md space-y-3 text-left mb-6">
                    <div className="flex gap-3 items-start p-3 rounded-lg bg-glass-100">
                        <span className="text-lg">1️⃣</span>
                        <div>
                            <strong className="theme-text-primary">Upload a source</strong>
                            <p className="text-sm theme-text-muted">Click &quot;+ Add&quot; in the Sources panel</p>
                        </div>
                    </div>
                    <div className="flex gap-3 items-start p-3 rounded-lg bg-glass-100">
                        <span className="text-lg">2️⃣</span>
                        <div>
                            <strong className="theme-text-primary">Select for chat</strong>
                            <p className="text-sm theme-text-muted">☑️ Use checkbox to include in queries</p>
                        </div>
                    </div>
                    <div className="flex gap-3 items-start p-3 rounded-lg bg-glass-100">
                        <span className="text-lg">3️⃣</span>
                        <div>
                            <strong className="theme-text-primary">View summary</strong>
                            <p className="text-sm theme-text-muted">📄 Click the title to read insights</p>
                        </div>
                    </div>
                </div>

                <div className="flex justify-center gap-3">
                    <span className="theme-chip">📄 PDF</span>
                    <span className="theme-chip">📝 Markdown</span>
                    <span className="theme-chip">📑 TXT</span>
                </div>
            </div>
        );
    }

    // Loading state
    if (isLoadingGuide) {
        return (
            <div className="h-full flex items-center justify-center">
                <div className="text-center">
                    <div className="w-8 h-8 border-2 border-cyber-blue border-t-transparent rounded-full animate-spin mx-auto mb-4" />
                    <p className="theme-text-muted">Analyzing document...</p>
                </div>
            </div>
        );
    }

    return (
        <div className="h-full overflow-y-auto p-6" data-testid="source-guide">
            {/* Document Title */}
            <div className="mb-6">
                <h1 className="text-2xl font-semibold theme-text-primary">
                    {activeSource?.title || "Document"}
                </h1>
                <p className="text-sm theme-text-muted mt-1">
                    {activeSource?.filename}
                </p>
            </div>

            {/* Cards Grid */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                {/* Summary Card */}
                <div className="source-guide-card lg:col-span-2">
                    <div className="flex items-center gap-2 mb-4">
                        <span className="text-xl">📋</span>
                        <h3 className="text-lg font-semibold theme-text-primary">Summary</h3>
                    </div>
                    <p className="theme-text-primary leading-relaxed">
                        {sourceGuide?.summary || "No summary available."}
                    </p>
                </div>

                {/* Key Topics Card */}
                <div className="source-guide-card">
                    <div className="flex items-center gap-2 mb-4">
                        <span className="text-xl">🏷️</span>
                        <h3 className="text-lg font-semibold theme-text-primary">Key Topics</h3>
                    </div>
                    <div className="flex flex-wrap gap-2">
                        {sourceGuide?.topics?.map((topic, index) => (
                            <span key={index} className="topic-chip">
                                {topic}
                            </span>
                        )) || <span className="theme-text-muted">No topics extracted.</span>}
                    </div>
                </div>

                {/* Suggested Questions Card */}
                <div className="source-guide-card">
                    <div className="flex items-center gap-2 mb-4">
                        <span className="text-xl">💡</span>
                        <h3 className="text-lg font-semibold theme-text-primary">Suggested Questions</h3>
                    </div>
                    <div className="space-y-2">
                        {sourceGuide?.suggestedQuestions?.map((question, index) => (
                            <button
                                key={index}
                                onClick={() => setViewMode("chat")}
                                className="w-full text-left p-3 rounded-lg bg-glass-100 hover:bg-glass-200 theme-text-primary hover:text-white text-sm transition-colors"
                            >
                                {question}
                            </button>
                        )) || <span className="theme-text-muted">No questions available.</span>}
                    </div>
                </div>
            </div>

            {/* Start Chat Button */}
            <div className="mt-8 text-center">
                <button
                    onClick={() => setViewMode("chat")}
                    className="glass-button px-8 py-3 text-cyber-blue font-medium hover:shadow-glow"
                    data-testid="start-chat-btn"
                >
                    💬 Start Chat
                </button>
            </div>
        </div>
    );
}
