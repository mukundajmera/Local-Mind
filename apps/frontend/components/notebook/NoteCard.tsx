"use client";

/**
 * NoteCard - Individual note display component
 * 
 * Features:
 * - Title and content preview
 * - Tags display
 * - Pin indicator
 * - Source citation link
 * - Hover actions (edit, delete, pin)
 */

import { Note, useNotebookStore } from "@/store/notebookStore";
import { cn } from "@/lib/utils";

interface NoteCardProps {
    note: Note;
    isSelected?: boolean;
    onClick?: () => void;
    viewMode?: "list" | "grid";
}

export function NoteCard({ note, isSelected, onClick, viewMode = "list" }: NoteCardProps) {
    const { togglePin, deleteNote, openEditor, selectNote } = useNotebookStore();

    const handlePin = async (e: React.MouseEvent) => {
        e.stopPropagation();
        await togglePin(note.note_id);
    };

    const handleEdit = (e: React.MouseEvent) => {
        e.stopPropagation();
        openEditor(note);
    };

    const handleDelete = async (e: React.MouseEvent) => {
        e.stopPropagation();
        if (confirm("Are you sure you want to delete this note?")) {
            await deleteNote(note.note_id);
        }
    };

    const handleClick = () => {
        selectNote(note.note_id);
        onClick?.();
    };

    // Format date
    const formatDate = (dateString: string) => {
        const date = new Date(dateString);
        const now = new Date();
        const diffDays = Math.floor((now.getTime() - date.getTime()) / (1000 * 60 * 60 * 24));

        if (diffDays === 0) {
            return date.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
        } else if (diffDays === 1) {
            return "Yesterday";
        } else if (diffDays < 7) {
            return date.toLocaleDateString(undefined, { weekday: "short" });
        } else {
            return date.toLocaleDateString(undefined, { month: "short", day: "numeric" });
        }
    };

    // Truncate content for preview
    const getPreview = (content: string, maxLength: number = 120) => {
        if (content.length <= maxLength) return content;
        return content.substring(0, maxLength).trim() + "...";
    };

    const isGridMode = viewMode === "grid";

    return (
        <div
            onClick={handleClick}
            className={cn(
                "group relative cursor-pointer transition-all duration-200",
                isGridMode
                    ? "p-4 rounded-xl"
                    : "p-3 rounded-lg",
                note.is_pinned
                    ? "bg-cyber-blue/10 border border-cyber-blue/30"
                    : "bg-glass-100 border border-transparent hover:border-glass",
                isSelected && "ring-2 ring-cyber-blue/50"
            )}
            data-testid={`note-card-${note.note_id}`}
        >
            {/* Pin indicator */}
            {note.is_pinned && (
                <div className="absolute top-2 right-2 text-cyber-blue text-sm" title="Pinned">
                    📌
                </div>
            )}

            {/* Header */}
            <div className="flex items-start justify-between gap-2 mb-2">
                <div className="flex-1 min-w-0">
                    {note.title ? (
                        <h3 className="font-medium theme-text-primary truncate">
                            {note.title}
                        </h3>
                    ) : (
                        <h3 className="font-medium theme-text-muted italic truncate">
                            Untitled Note
                        </h3>
                    )}
                </div>
            </div>

            {/* Content preview */}
            <p className={cn(
                "text-sm theme-text-muted",
                isGridMode ? "line-clamp-4" : "line-clamp-2"
            )}>
                {getPreview(note.content, isGridMode ? 200 : 120)}
            </p>

            {/* Tags */}
            {note.tags.length > 0 && (
                <div className="flex flex-wrap gap-1 mt-2">
                    {note.tags.slice(0, 3).map((tag) => (
                        <span
                            key={tag}
                            className="px-2 py-0.5 rounded-full text-xs theme-chip"
                        >
                            {tag}
                        </span>
                    ))}
                    {note.tags.length > 3 && (
                        <span className="px-2 py-0.5 text-xs theme-text-faint">
                            +{note.tags.length - 3}
                        </span>
                    )}
                </div>
            )}

            {/* Footer: Source & Date */}
            <div className="flex items-center justify-between mt-3 text-xs theme-text-faint">
                <div className="flex items-center gap-2">
                    {note.source_filename && (
                        <span className="truncate max-w-[100px]" title={note.source_filename}>
                            📄 {note.source_filename}
                        </span>
                    )}
                </div>
                <span>{formatDate(note.created_at)}</span>
            </div>

            {/* Hover actions */}
            <div className="absolute bottom-2 right-2 flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                <button
                    onClick={handlePin}
                    className={cn(
                        "p-1.5 rounded-lg transition-colors",
                        note.is_pinned
                            ? "text-cyber-blue hover:bg-cyber-blue/20"
                            : "theme-text-faint hover:text-white hover:bg-glass-100"
                    )}
                    title={note.is_pinned ? "Unpin" : "Pin"}
                    data-testid={`pin-btn-${note.note_id}`}
                >
                    📌
                </button>
                <button
                    onClick={handleEdit}
                    className="p-1.5 rounded-lg theme-text-faint hover:text-white hover:bg-glass-100 transition-colors"
                    title="Edit"
                    data-testid={`edit-btn-${note.note_id}`}
                >
                    ✏️
                </button>
                <button
                    onClick={handleDelete}
                    className="p-1.5 rounded-lg theme-text-faint hover:text-red-400 hover:bg-red-400/10 transition-colors"
                    title="Delete"
                    data-testid={`delete-btn-${note.note_id}`}
                >
                    🗑️
                </button>
            </div>
        </div>
    );
}
