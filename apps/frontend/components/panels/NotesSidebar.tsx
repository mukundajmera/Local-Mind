"use client";

/**
 * Notes Sidebar - Collapsible right panel for saved notes
 * 
 * Enhanced to integrate with backend API for persistent notes storage.
 * Shows both pinned chat messages and regular notes.
 */

import { useState, useEffect } from "react";
import { useWorkspaceStore } from "@/store/workspaceStore";
import { useNotebookStore, Note, CreateNoteRequest } from "@/store/notebookStore";
import Link from "next/link";

export function NotesSidebar() {
    const { toggleNotesPanel, pinnedMessages, unpinMessage, currentProjectId } = useWorkspaceStore();
    const {
        notes,
        isLoading,
        fetchNotes,
        createNote,
        deleteNote,
        togglePin,
        isSaving
    } = useNotebookStore();

    const [newNote, setNewNote] = useState("");

    // Fetch notes on mount
    useEffect(() => {
        fetchNotes(currentProjectId || undefined);
    }, [fetchNotes, currentProjectId]);

    const handleAddNote = async () => {
        if (!newNote.trim()) return;

        const noteRequest: CreateNoteRequest = {
            content: newNote.trim(),
            project_id: currentProjectId || undefined,
        };

        await createNote(noteRequest);
        setNewNote("");
    };

    const handleDeleteNote = async (id: string) => {
        await deleteNote(id);
    };

    const handleTogglePin = async (id: string) => {
        await togglePin(id);
    };

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            handleAddNote();
        }
    };

    // Convert pinned chat message to note
    const handleSavePinnedMessage = async (msgId: string, content: string) => {
        const noteRequest: CreateNoteRequest = {
            content,
            title: "From Chat",
            project_id: currentProjectId || undefined,
            tags: ["chat", "pinned"],
        };

        await createNote(noteRequest);
        unpinMessage(msgId);
    };

    // Filter notes - show pinned first, then by date
    const sortedNotes = [...notes].sort((a, b) => {
        if (a.is_pinned !== b.is_pinned) {
            return b.is_pinned ? 1 : -1;
        }
        return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
    });

    const pinnedNotes = sortedNotes.filter(n => n.is_pinned);
    const regularNotes = sortedNotes.filter(n => !n.is_pinned);

    return (
        <div className="w-72 flex flex-col h-full border-l border-glass" data-testid="notes-sidebar">
            {/* Header */}
            <div className="panel-header flex items-center justify-between">
                <span>Notes</span>
                <div className="flex items-center gap-2">
                    <Link
                        href="/notebook"
                        className="text-xs text-cyber-blue hover:underline"
                        title="Open full Notebook"
                    >
                        View All
                    </Link>
                    <button
                        onClick={toggleNotesPanel}
                        className="theme-text-faint hover:text-white transition-colors"
                        title="Close notes"
                    >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                        </svg>
                    </button>
                </div>
            </div>

            {/* Add Note */}
            <div className="p-3 border-b border-glass">
                <textarea
                    value={newNote}
                    onChange={(e) => setNewNote(e.target.value)}
                    onKeyDown={handleKeyDown}
                    placeholder="Add a quick note..."
                    className="glass-input text-sm resize-none"
                    rows={2}
                />
                <button
                    onClick={handleAddNote}
                    disabled={!newNote.trim() || isSaving}
                    className="mt-2 w-full text-xs py-2 rounded-lg bg-cyber-blue/20 text-cyber-blue hover:bg-cyber-blue/30 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                    {isSaving ? "Saving..." : "+ Add Note"}
                </button>
            </div>

            {/* Notes List */}
            <div className="flex-1 overflow-y-auto p-3 space-y-3">
                {/* Loading state */}
                {isLoading && (
                    <div className="flex items-center justify-center py-4">
                        <div className="w-5 h-5 border-2 border-cyber-blue/30 border-t-cyber-blue rounded-full animate-spin" />
                    </div>
                )}

                {/* Pinned Chat Messages Section */}
                {pinnedMessages.length > 0 && (
                    <div className="space-y-2">
                        <div className="text-xs theme-text-muted font-semibold uppercase tracking-wide px-1">
                            📌 Pinned from Chat
                        </div>
                        {pinnedMessages.map((msg) => (
                            <div
                                key={msg.id}
                                className="group p-3 rounded-lg bg-cyber-blue/10 border border-cyber-blue/30"
                                data-testid={`pinned-message-${msg.id}`}
                            >
                                <p className="text-sm theme-text-primary whitespace-pre-wrap line-clamp-4">
                                    {msg.content}
                                </p>
                                <div className="flex items-center justify-between mt-2">
                                    <span className="text-xs theme-text-faint">
                                        {msg.pinnedAt.toLocaleTimeString(undefined, {
                                            hour: "2-digit",
                                            minute: "2-digit",
                                        })}
                                    </span>
                                    <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                                        <button
                                            onClick={() => handleSavePinnedMessage(msg.id, msg.content)}
                                            className="p-1 rounded text-xs theme-text-faint hover:text-cyber-blue transition-colors"
                                            title="Save as note"
                                        >
                                            💾
                                        </button>
                                        <button
                                            onClick={() => unpinMessage(msg.id)}
                                            className="p-1 rounded theme-text-faint hover:text-red-400 transition-colors"
                                            title="Unpin"
                                        >
                                            🗑️
                                        </button>
                                    </div>
                                </div>
                            </div>
                        ))}
                        <div className="border-t border-glass my-3" />
                    </div>
                )}

                {/* Pinned Notes Section */}
                {pinnedNotes.length > 0 && (
                    <div className="space-y-2">
                        <div className="text-xs theme-text-muted font-semibold uppercase tracking-wide px-1">
                            📌 Pinned Notes
                        </div>
                        {pinnedNotes.map((note) => (
                            <NoteItem
                                key={note.note_id}
                                note={note}
                                onDelete={handleDeleteNote}
                                onTogglePin={handleTogglePin}
                            />
                        ))}
                        {regularNotes.length > 0 && (
                            <div className="border-t border-glass my-3" />
                        )}
                    </div>
                )}

                {/* Regular Notes Section */}
                <div className="space-y-2">
                    {regularNotes.length > 0 && (pinnedMessages.length > 0 || pinnedNotes.length > 0) && (
                        <div className="text-xs theme-text-muted font-semibold uppercase tracking-wide px-1">
                            📝 Notes
                        </div>
                    )}
                    {!isLoading && notes.length === 0 && pinnedMessages.length === 0 ? (
                        <div className="text-center py-8 theme-text-faint text-sm">
                            No notes yet. Add one above or pin messages from chat!
                        </div>
                    ) : (
                        regularNotes.map((note) => (
                            <NoteItem
                                key={note.note_id}
                                note={note}
                                onDelete={handleDeleteNote}
                                onTogglePin={handleTogglePin}
                            />
                        ))
                    )}
                </div>
            </div>
        </div>
    );
}

// Individual note item component
function NoteItem({
    note,
    onDelete,
    onTogglePin
}: {
    note: Note;
    onDelete: (id: string) => void;
    onTogglePin: (id: string) => void;
}) {
    const formatTime = (dateString: string) => {
        const date = new Date(dateString);
        const now = new Date();
        const diffDays = Math.floor((now.getTime() - date.getTime()) / (1000 * 60 * 60 * 24));

        if (diffDays === 0) {
            return date.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
        } else if (diffDays < 7) {
            return date.toLocaleDateString(undefined, { weekday: "short" });
        } else {
            return date.toLocaleDateString(undefined, { month: "short", day: "numeric" });
        }
    };

    return (
        <div
            className={`group p-3 rounded-lg border transition-colors ${note.is_pinned
                    ? "bg-cyber-blue/10 border-cyber-blue/30"
                    : "bg-glass-100 border-transparent hover:border-glass"
                }`}
            data-testid={`note-${note.note_id}`}
        >
            {note.title && (
                <p className="text-xs font-medium theme-text-primary mb-1 truncate">
                    {note.title}
                </p>
            )}
            <p className="text-sm theme-text-primary whitespace-pre-wrap line-clamp-3">
                {note.content}
            </p>
            {note.tags.length > 0 && (
                <div className="flex flex-wrap gap-1 mt-2">
                    {note.tags.slice(0, 2).map((tag) => (
                        <span key={tag} className="px-1.5 py-0.5 rounded text-[10px] theme-chip">
                            {tag}
                        </span>
                    ))}
                </div>
            )}
            <div className="flex items-center justify-between mt-2">
                <span className="text-xs theme-text-faint">
                    {formatTime(note.created_at)}
                </span>
                <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                    <button
                        onClick={() => onTogglePin(note.note_id)}
                        className={`p-1 rounded transition-colors ${note.is_pinned
                                ? "text-cyber-blue"
                                : "theme-text-faint hover:text-white"
                            }`}
                        title={note.is_pinned ? "Unpin" : "Pin"}
                    >
                        📌
                    </button>
                    <button
                        onClick={() => onDelete(note.note_id)}
                        className="p-1 rounded theme-text-faint hover:text-red-400 transition-colors"
                        title="Delete"
                    >
                        🗑️
                    </button>
                </div>
            </div>
        </div>
    );
}
