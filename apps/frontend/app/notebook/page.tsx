"use client";

/**
 * Notebook Page - Main view for managing notes
 * 
 * Features:
 * - 2-column layout: sidebar (notes list) + main (editor/detail)
 * - Search and filter functionality
 * - Note creation and editing
 * - Pin/unpin notes
 */

import { useEffect } from "react";
import { NotebookHeader } from "@/components/primitives/NotebookHeader";
import { NotebookSidebar } from "@/components/notebook/NotebookSidebar";
import { NoteEditor } from "@/components/notebook/NoteEditor";
import { useNotebookStore, Note } from "@/store/notebookStore";
import { useWorkspaceStore } from "@/store/workspaceStore";

export default function NotebookPage() {
    const {
        isEditorOpen,
        editingNote,
        closeEditor,
        selectedNoteId,
        notes,
        fetchNotes,
    } = useNotebookStore();

    const { currentProjectId } = useWorkspaceStore();

    // Get selected note
    const selectedNote = selectedNoteId
        ? notes.find((n) => n.note_id === selectedNoteId)
        : null;

    // Format date for display
    const formatFullDate = (dateString: string) => {
        return new Date(dateString).toLocaleString(undefined, {
            weekday: "short",
            year: "numeric",
            month: "short",
            day: "numeric",
            hour: "2-digit",
            minute: "2-digit",
        });
    };

    return (
        <div className="h-full flex flex-col gap-4">
            <NotebookHeader />

            <div className="flex-1 flex gap-4 min-h-0">
                {/* Left Sidebar - Notes List */}
                <aside className="glass-panel flex flex-col overflow-hidden shrink-0">
                    <NotebookSidebar projectId={currentProjectId || undefined} />
                </aside>

                {/* Main Content */}
                <main className="flex-1 glass-panel flex flex-col overflow-hidden">
                    {isEditorOpen ? (
                        // Editor view
                        <NoteEditor
                            note={editingNote}
                            onClose={closeEditor}
                            projectId={currentProjectId || undefined}
                        />
                    ) : selectedNote ? (
                        // Detail view
                        <NoteDetailView note={selectedNote} />
                    ) : (
                        // Empty state
                        <div className="flex-1 flex items-center justify-center">
                            <div className="text-center max-w-md px-8">
                                <div className="text-6xl mb-6">📓</div>
                                <h2 className="text-2xl font-semibold theme-text-primary mb-3">
                                    Welcome to Notebook
                                </h2>
                                <p className="theme-text-muted mb-6">
                                    Your personal knowledge base. Capture insights, save annotations,
                                    and organize your research notes in one place.
                                </p>
                                <button
                                    onClick={() => useNotebookStore.getState().openEditor()}
                                    className="px-6 py-3 rounded-xl text-sm font-medium bg-cyber-blue/20 text-cyber-blue hover:bg-cyber-blue/30 transition-colors"
                                    data-testid="create-first-note-btn"
                                >
                                    Create Your First Note
                                </button>
                            </div>
                        </div>
                    )}
                </main>
            </div>
        </div>
    );
}

// Note detail view component
function NoteDetailView({ note }: { note: Note }) {
    const { openEditor, togglePin, deleteNote } = useNotebookStore();

    const formatFullDate = (dateString: string) => {
        return new Date(dateString).toLocaleString(undefined, {
            weekday: "short",
            year: "numeric",
            month: "short",
            day: "numeric",
            hour: "2-digit",
            minute: "2-digit",
        });
    };

    const handleDelete = async () => {
        if (confirm("Are you sure you want to delete this note?")) {
            await deleteNote(note.note_id);
        }
    };

    return (
        <div className="flex flex-col h-full" data-testid="note-detail-view">
            {/* Header */}
            <div className="panel-header flex items-center justify-between">
                <div className="flex items-center gap-2">
                    {note.is_pinned && <span title="Pinned">📌</span>}
                    <span className="font-medium">
                        {note.title || "Untitled Note"}
                    </span>
                </div>
                <div className="flex items-center gap-1">
                    <button
                        onClick={() => togglePin(note.note_id)}
                        className={`p-1.5 rounded-lg transition-colors ${note.is_pinned
                                ? "text-cyber-blue hover:bg-cyber-blue/20"
                                : "theme-text-faint hover:text-white hover:bg-glass-100"
                            }`}
                        title={note.is_pinned ? "Unpin" : "Pin"}
                    >
                        📌
                    </button>
                    <button
                        onClick={() => openEditor(note)}
                        className="p-1.5 rounded-lg theme-text-faint hover:text-white hover:bg-glass-100 transition-colors"
                        title="Edit"
                    >
                        ✏️
                    </button>
                    <button
                        onClick={handleDelete}
                        className="p-1.5 rounded-lg theme-text-faint hover:text-red-400 hover:bg-red-400/10 transition-colors"
                        title="Delete"
                    >
                        🗑️
                    </button>
                </div>
            </div>

            {/* Content */}
            <div className="flex-1 overflow-y-auto p-6">
                {/* Title */}
                {note.title && (
                    <h1 className="text-2xl font-semibold theme-text-primary mb-4">
                        {note.title}
                    </h1>
                )}

                {/* Meta info */}
                <div className="flex flex-wrap items-center gap-4 mb-6 text-sm theme-text-muted">
                    <span>
                        Created: {formatFullDate(note.created_at)}
                    </span>
                    {note.updated_at && (
                        <span>
                            Updated: {formatFullDate(note.updated_at)}
                        </span>
                    )}
                    {note.source_filename && (
                        <span className="flex items-center gap-1">
                            📄 {note.source_filename}
                        </span>
                    )}
                </div>

                {/* Tags */}
                {note.tags.length > 0 && (
                    <div className="flex flex-wrap gap-1 mb-6">
                        {note.tags.map((tag) => (
                            <span
                                key={tag}
                                className="px-3 py-1 rounded-full text-sm theme-chip"
                            >
                                {tag}
                            </span>
                        ))}
                    </div>
                )}

                {/* Content */}
                <div className="prose prose-invert max-w-none">
                    <div className="whitespace-pre-wrap theme-text-primary leading-relaxed">
                        {note.content}
                    </div>
                </div>
            </div>
        </div>
    );
}
