"use client";

/**
 * Notes Sidebar - Collapsible right panel for saved notes
 */

import { useState } from "react";
import { useWorkspaceStore } from "@/store/workspaceStore";

interface Note {
    id: string;
    content: string;
    createdAt: Date;
    isPinned: boolean;
}

export function NotesSidebar() {
    const { toggleNotesPanel, pinnedMessages, unpinMessage } = useWorkspaceStore();
    const [notes, setNotes] = useState<Note[]>([]);
    const [newNote, setNewNote] = useState("");

    const handleAddNote = () => {
        if (!newNote.trim()) return;

        const note: Note = {
            id: Date.now().toString(),
            content: newNote.trim(),
            createdAt: new Date(),
            isPinned: false,
        };
        setNotes((prev) => [note, ...prev]);
        setNewNote("");
    };

    const handleDeleteNote = (id: string) => {
        setNotes((prev) => prev.filter((n) => n.id !== id));
    };

    const handleTogglePin = (id: string) => {
        setNotes((prev) =>
            prev.map((n) =>
                n.id === id ? { ...n, isPinned: !n.isPinned } : n
            ).sort((a, b) => (b.isPinned ? 1 : 0) - (a.isPinned ? 1 : 0))
        );
    };

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            handleAddNote();
        }
    };

    return (
        <div className="w-72 flex flex-col h-full border-l border-glass" data-testid="notes-sidebar">
            {/* Header */}
            <div className="panel-header flex items-center justify-between">
                <span>Notes</span>
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

            {/* Add Note */}
            <div className="p-3 border-b border-glass">
                <textarea
                    value={newNote}
                    onChange={(e) => setNewNote(e.target.value)}
                    onKeyDown={handleKeyDown}
                    placeholder="Add a note..."
                    className="glass-input text-sm resize-none"
                    rows={2}
                />
                <button
                    onClick={handleAddNote}
                    disabled={!newNote.trim()}
                    className="mt-2 w-full text-xs py-2 rounded-lg bg-cyber-blue/20 text-cyber-blue hover:bg-cyber-blue/30 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                    + Add Note
                </button>
            </div>

            {/* Notes List */}
            <div className="flex-1 overflow-y-auto p-3 space-y-3">
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
                                <p className="text-sm theme-text-primary whitespace-pre-wrap">
                                    {msg.content}
                                </p>
                                <div className="flex items-center justify-between mt-2">
                                    <span className="text-xs theme-text-faint">
                                        {msg.pinnedAt.toLocaleTimeString(undefined, {
                                            hour: "2-digit",
                                            minute: "2-digit",
                                        })}
                                    </span>
                                    <button
                                        onClick={() => unpinMessage(msg.id)}
                                        className="opacity-0 group-hover:opacity-100 p-1 rounded theme-text-faint hover:text-red-400 transition-all"
                                        title="Unpin"
                                        data-testid={`unpin-btn-${msg.id}`}
                                    >
                                        🗑️
                                    </button>
                                </div>
                            </div>
                        ))}
                        <div className="border-t border-glass my-3" />
                    </div>
                )}

                {/* Regular Notes Section */}
                <div className="space-y-2">
                    {notes.length > 0 && pinnedMessages.length > 0 && (
                        <div className="text-xs theme-text-muted font-semibold uppercase tracking-wide px-1">
                            📝 Notes
                        </div>
                    )}
                    {notes.length === 0 && pinnedMessages.length === 0 ? (
                        <div className="text-center py-8 theme-text-faint text-sm">
                            No notes yet. Add one above or pin messages from chat!
                        </div>
                    ) : (
                        notes.map((note) => (
                            <div
                                key={note.id}
                                className={`group p-3 rounded-lg border transition-colors ${note.isPinned
                                    ? "bg-cyber-blue/10 border-cyber-blue/30"
                                    : "bg-glass-100 border-transparent hover:border-glass"
                                    }`}
                            >
                                <p className="text-sm theme-text-primary whitespace-pre-wrap">
                                    {note.content}
                                </p>
                                <div className="flex items-center justify-between mt-2">
                                    <span className="text-xs theme-text-faint">
                                        {note.createdAt.toLocaleTimeString(undefined, {
                                            hour: "2-digit",
                                            minute: "2-digit",
                                        })}
                                    </span>
                                    <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                                        <button
                                            onClick={() => handleTogglePin(note.id)}
                                            className={`p-1 rounded transition-colors ${note.isPinned
                                                ? "text-cyber-blue"
                                                : "theme-text-faint hover:text-white"
                                                }`}
                                            title={note.isPinned ? "Unpin" : "Pin"}
                                        >
                                            📌
                                        </button>
                                        <button
                                            onClick={() => handleDeleteNote(note.id)}
                                            className="p-1 rounded theme-text-faint hover:text-red-400 transition-colors"
                                            title="Delete"
                                        >
                                            🗑️
                                        </button>
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
