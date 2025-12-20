"use client";

/**
 * NotebookSidebar - Left sidebar for notes list
 * 
 * Features:
 * - Search input
 * - Tag filter chips
 * - Notes list (pinned first, then by date)
 * - View toggle (list/grid)
 * - New note button
 */

import { useEffect } from "react";
import { useNotebookStore } from "@/store/notebookStore";
import { NoteCard } from "./NoteCard";
import { cn } from "@/lib/utils";

interface NotebookSidebarProps {
    projectId?: string;
}

export function NotebookSidebar({ projectId }: NotebookSidebarProps) {
    const {
        isLoading,
        searchQuery,
        setSearchQuery,
        selectedTags,
        toggleTag,
        allTags,
        viewMode,
        setViewMode,
        openEditor,
        getFilteredNotes,
        fetchNotes,
        fetchTags,
    } = useNotebookStore();

    // Fetch notes on mount
    useEffect(() => {
        fetchNotes(projectId);
        fetchTags(projectId);
    }, [fetchNotes, fetchTags, projectId]);

    const filteredNotes = getFilteredNotes();
    const pinnedNotes = filteredNotes.filter((n) => n.is_pinned);
    const unpinnedNotes = filteredNotes.filter((n) => !n.is_pinned);

    return (
        <div className="w-80 flex flex-col h-full" data-testid="notebook-sidebar">
            {/* Header */}
            <div className="panel-header flex items-center justify-between">
                <span>📓 My Notes</span>
                <div className="flex items-center gap-1">
                    {/* View toggle */}
                    <button
                        onClick={() => setViewMode("list")}
                        className={cn(
                            "p-1.5 rounded transition-colors",
                            viewMode === "list"
                                ? "bg-cyber-blue/20 text-cyber-blue"
                                : "theme-text-faint hover:text-white"
                        )}
                        title="List view"
                    >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 10h16M4 14h16M4 18h16" />
                        </svg>
                    </button>
                    <button
                        onClick={() => setViewMode("grid")}
                        className={cn(
                            "p-1.5 rounded transition-colors",
                            viewMode === "grid"
                                ? "bg-cyber-blue/20 text-cyber-blue"
                                : "theme-text-faint hover:text-white"
                        )}
                        title="Grid view"
                    >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" />
                        </svg>
                    </button>
                </div>
            </div>

            {/* Search */}
            <div className="p-3 border-b border-glass">
                <div className="relative">
                    <svg
                        className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 theme-text-faint"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                    >
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                    </svg>
                    <input
                        type="text"
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        placeholder="Search notes..."
                        className="glass-input pl-10 py-2 text-sm"
                        data-testid="search-notes-input"
                    />
                </div>
            </div>

            {/* Tag filters */}
            {allTags.length > 0 && (
                <div className="p-3 border-b border-glass">
                    <div className="flex flex-wrap gap-1">
                        {allTags.slice(0, 8).map((tag) => (
                            <button
                                key={tag}
                                onClick={() => toggleTag(tag)}
                                className={cn(
                                    "px-2 py-1 rounded-full text-xs transition-colors",
                                    selectedTags.includes(tag)
                                        ? "bg-cyber-blue/20 text-cyber-blue border border-cyber-blue/30"
                                        : "bg-glass-100 theme-text-muted hover:theme-text-primary"
                                )}
                            >
                                {tag}
                            </button>
                        ))}
                        {allTags.length > 8 && (
                            <span className="px-2 py-1 text-xs theme-text-faint">
                                +{allTags.length - 8} more
                            </span>
                        )}
                    </div>
                </div>
            )}

            {/* New note button */}
            <div className="p-3 border-b border-glass">
                <button
                    onClick={() => openEditor()}
                    className="w-full py-2 rounded-lg text-sm font-medium bg-cyber-blue/20 text-cyber-blue hover:bg-cyber-blue/30 transition-colors flex items-center justify-center gap-2"
                    data-testid="new-note-btn"
                >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                    </svg>
                    New Note
                </button>
            </div>

            {/* Notes list */}
            <div className="flex-1 overflow-y-auto p-3">
                {isLoading ? (
                    <div className="flex items-center justify-center py-8">
                        <div className="w-6 h-6 border-2 border-cyber-blue/30 border-t-cyber-blue rounded-full animate-spin" />
                    </div>
                ) : filteredNotes.length === 0 ? (
                    <div className="text-center py-8 theme-text-faint">
                        {searchQuery || selectedTags.length > 0 ? (
                            <>
                                <p className="text-2xl mb-2">🔍</p>
                                <p className="text-sm">No notes match your search</p>
                            </>
                        ) : (
                            <>
                                <p className="text-2xl mb-2">📝</p>
                                <p className="text-sm">No notes yet</p>
                                <p className="text-xs mt-1">Click &quot;New Note&quot; to create one!</p>
                            </>
                        )}
                    </div>
                ) : (
                    <div className={cn(
                        "space-y-2",
                        viewMode === "grid" && "grid grid-cols-1 gap-2"
                    )}>
                        {/* Pinned section */}
                        {pinnedNotes.length > 0 && (
                            <>
                                <div className="text-xs theme-text-muted font-semibold uppercase tracking-wide px-1 mb-2">
                                    📌 Pinned
                                </div>
                                {pinnedNotes.map((note) => (
                                    <NoteCard
                                        key={note.note_id}
                                        note={note}
                                        viewMode={viewMode}
                                    />
                                ))}
                                {unpinnedNotes.length > 0 && (
                                    <div className="border-t border-glass my-3" />
                                )}
                            </>
                        )}

                        {/* All notes section */}
                        {unpinnedNotes.length > 0 && pinnedNotes.length > 0 && (
                            <div className="text-xs theme-text-muted font-semibold uppercase tracking-wide px-1 mb-2">
                                All Notes
                            </div>
                        )}
                        {unpinnedNotes.map((note) => (
                            <NoteCard
                                key={note.note_id}
                                note={note}
                                viewMode={viewMode}
                            />
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
}
