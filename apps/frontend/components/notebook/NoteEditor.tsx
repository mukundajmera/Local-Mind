"use client";

/**
 * NoteEditor - Note creation and editing component
 * 
 * Features:
 * - Title input
 * - Content textarea
 * - Tag input with autocomplete
 * - Source selection (optional)
 * - Save/cancel actions
 */

import { useState, useEffect, useRef } from "react";
import { Note, CreateNoteRequest, UpdateNoteRequest, useNotebookStore } from "@/store/notebookStore";
import { cn } from "@/lib/utils";

interface NoteEditorProps {
    note?: Note | null;
    onClose?: () => void;
    projectId?: string;
}

export function NoteEditor({ note, onClose, projectId }: NoteEditorProps) {
    const { createNote, updateNote, closeEditor, isSaving, allTags } = useNotebookStore();

    const [title, setTitle] = useState(note?.title || "");
    const [content, setContent] = useState(note?.content || "");
    const [tags, setTags] = useState<string[]>(note?.tags || []);
    const [tagInput, setTagInput] = useState("");
    const [showTagSuggestions, setShowTagSuggestions] = useState(false);

    const contentRef = useRef<HTMLTextAreaElement>(null);
    const tagInputRef = useRef<HTMLInputElement>(null);

    const isEditing = !!note;

    // Auto-focus content on open
    useEffect(() => {
        if (contentRef.current) {
            contentRef.current.focus();
        }
    }, []);

    // Handle save
    const handleSave = async () => {
        if (!content.trim()) {
            return; // Don't save empty notes
        }

        if (isEditing && note) {
            const updates: UpdateNoteRequest = {};
            if (title !== note.title) updates.title = title || undefined;
            if (content !== note.content) updates.content = content;
            if (JSON.stringify(tags) !== JSON.stringify(note.tags)) updates.tags = tags;

            await updateNote(note.note_id, updates);
        } else {
            const newNote: CreateNoteRequest = {
                content: content.trim(),
                title: title.trim() || undefined,
                tags: tags.length > 0 ? tags : undefined,
                project_id: projectId,
            };

            await createNote(newNote);
        }

        onClose?.();
    };

    // Handle cancel
    const handleCancel = () => {
        closeEditor();
        onClose?.();
    };

    // Handle adding a tag
    const handleAddTag = (tag: string) => {
        const normalizedTag = tag.trim().toLowerCase();
        if (normalizedTag && !tags.includes(normalizedTag)) {
            setTags([...tags, normalizedTag]);
        }
        setTagInput("");
        setShowTagSuggestions(false);
    };

    // Handle removing a tag
    const handleRemoveTag = (tagToRemove: string) => {
        setTags(tags.filter((t) => t !== tagToRemove));
    };

    // Handle tag input key events
    const handleTagKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === "Enter" || e.key === ",") {
            e.preventDefault();
            handleAddTag(tagInput);
        } else if (e.key === "Backspace" && !tagInput && tags.length > 0) {
            setTags(tags.slice(0, -1));
        }
    };

    // Filter tag suggestions
    const tagSuggestions = allTags.filter(
        (tag) =>
            tag.toLowerCase().includes(tagInput.toLowerCase()) &&
            !tags.includes(tag)
    ).slice(0, 5);

    // Handle content keyboard shortcuts
    const handleContentKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === "s" && (e.metaKey || e.ctrlKey)) {
            e.preventDefault();
            handleSave();
        } else if (e.key === "Escape") {
            handleCancel();
        }
    };

    return (
        <div className="flex flex-col h-full" data-testid="note-editor">
            {/* Header */}
            <div className="panel-header flex items-center justify-between">
                <span>{isEditing ? "Edit Note" : "New Note"}</span>
                <button
                    onClick={handleCancel}
                    className="theme-text-faint hover:text-white transition-colors"
                    title="Close (Esc)"
                >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                </button>
            </div>

            {/* Form */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
                {/* Title input */}
                <div>
                    <input
                        type="text"
                        value={title}
                        onChange={(e) => setTitle(e.target.value)}
                        placeholder="Note title (optional)"
                        className="w-full px-3 py-2 bg-transparent border-b border-glass focus:border-cyber-blue focus:outline-none text-lg font-medium theme-text-primary placeholder:theme-text-faint transition-colors"
                        data-testid="note-title-input"
                    />
                </div>

                {/* Content textarea */}
                <div className="flex-1">
                    <textarea
                        ref={contentRef}
                        value={content}
                        onChange={(e) => setContent(e.target.value)}
                        onKeyDown={handleContentKeyDown}
                        placeholder="Write your note here... (Ctrl+S to save)"
                        className="glass-input min-h-[200px] resize-none text-sm"
                        rows={10}
                        data-testid="note-content-input"
                    />
                </div>

                {/* Tags */}
                <div className="space-y-2">
                    <label className="text-xs theme-text-muted font-medium uppercase tracking-wide">
                        Tags
                    </label>

                    {/* Current tags */}
                    <div className="flex flex-wrap gap-1 mb-2">
                        {tags.map((tag) => (
                            <span
                                key={tag}
                                className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs theme-chip"
                            >
                                {tag}
                                <button
                                    onClick={() => handleRemoveTag(tag)}
                                    className="text-xs hover:text-red-400 transition-colors"
                                    data-testid={`remove-tag-${tag}`}
                                >
                                    ×
                                </button>
                            </span>
                        ))}
                    </div>

                    {/* Tag input */}
                    <div className="relative">
                        <input
                            ref={tagInputRef}
                            type="text"
                            value={tagInput}
                            onChange={(e) => {
                                setTagInput(e.target.value);
                                setShowTagSuggestions(e.target.value.length > 0);
                            }}
                            onKeyDown={handleTagKeyDown}
                            onFocus={() => setShowTagSuggestions(tagInput.length > 0)}
                            onBlur={() => setTimeout(() => setShowTagSuggestions(false), 200)}
                            placeholder="Add tags (press Enter)"
                            className="glass-input text-sm py-2"
                            data-testid="tag-input"
                        />

                        {/* Tag suggestions dropdown */}
                        {showTagSuggestions && tagSuggestions.length > 0 && (
                            <div className="absolute top-full left-0 right-0 mt-1 py-1 rounded-lg bg-glass-200 border border-glass shadow-lg z-10">
                                {tagSuggestions.map((tag) => (
                                    <button
                                        key={tag}
                                        onClick={() => handleAddTag(tag)}
                                        className="w-full px-3 py-1.5 text-left text-sm hover:bg-glass-100 theme-text-primary transition-colors"
                                    >
                                        {tag}
                                    </button>
                                ))}
                            </div>
                        )}
                    </div>
                </div>
            </div>

            {/* Footer actions */}
            <div className="p-4 border-t border-glass flex items-center justify-end gap-2">
                <button
                    onClick={handleCancel}
                    className="px-4 py-2 rounded-lg text-sm theme-text-muted hover:theme-text-primary hover:bg-glass-100 transition-colors"
                    disabled={isSaving}
                >
                    Cancel
                </button>
                <button
                    onClick={handleSave}
                    disabled={!content.trim() || isSaving}
                    className={cn(
                        "px-4 py-2 rounded-lg text-sm font-medium transition-colors",
                        content.trim()
                            ? "bg-cyber-blue/20 text-cyber-blue hover:bg-cyber-blue/30"
                            : "bg-glass-100 theme-text-faint cursor-not-allowed"
                    )}
                    data-testid="save-note-btn"
                >
                    {isSaving ? "Saving..." : isEditing ? "Update" : "Save Note"}
                </button>
            </div>
        </div>
    );
}
