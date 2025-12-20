"use client";

/**
 * Notebook Store - State management for the Notebook feature
 * 
 * Manages notes state including:
 * - CRUD operations via API
 * - Search and tag filtering
 * - Pin/unpin functionality
 * - View mode (list/grid)
 */

import { create } from "zustand";
import { API_BASE_URL } from "@/lib/api";

// Types matching backend schemas
export interface Note {
    note_id: string;
    project_id: string | null;
    content: string;
    title: string | null;
    tags: string[];
    source_citation_id: string | null;
    source_filename: string | null;
    is_pinned: boolean;
    created_at: string;
    updated_at: string | null;
}

export interface CreateNoteRequest {
    content: string;
    title?: string;
    tags?: string[];
    source_citation_id?: string;
    source_filename?: string;
    project_id?: string;
}

export interface UpdateNoteRequest {
    content?: string;
    title?: string;
    tags?: string[];
    is_pinned?: boolean;
}

interface NotebookState {
    // Notes data
    notes: Note[];
    selectedNoteId: string | null;
    editingNote: Note | null;

    // Loading states
    isLoading: boolean;
    isSaving: boolean;
    error: string | null;

    // Filtering
    searchQuery: string;
    selectedTags: string[];
    allTags: string[];

    // View settings
    viewMode: "list" | "grid";
    isEditorOpen: boolean;

    // Actions
    fetchNotes: (projectId?: string) => Promise<void>;
    fetchTags: (projectId?: string) => Promise<void>;
    createNote: (note: CreateNoteRequest) => Promise<Note | null>;
    updateNote: (id: string, updates: UpdateNoteRequest) => Promise<Note | null>;
    deleteNote: (id: string) => Promise<boolean>;
    togglePin: (id: string) => Promise<void>;

    // Selection & editing
    selectNote: (id: string | null) => void;
    openEditor: (note?: Note) => void;
    closeEditor: () => void;

    // Filtering
    setSearchQuery: (query: string) => void;
    setSelectedTags: (tags: string[]) => void;
    toggleTag: (tag: string) => void;

    // View
    setViewMode: (mode: "list" | "grid") => void;

    // Computed - get filtered notes
    getFilteredNotes: () => Note[];
}

export const useNotebookStore = create<NotebookState>((set, get) => ({
    // Initial state
    notes: [],
    selectedNoteId: null,
    editingNote: null,
    isLoading: false,
    isSaving: false,
    error: null,
    searchQuery: "",
    selectedTags: [],
    allTags: [],
    viewMode: "list",
    isEditorOpen: false,

    // Fetch all notes
    fetchNotes: async (projectId?: string) => {
        set({ isLoading: true, error: null });
        try {
            let url = `${API_BASE_URL}/api/v1/notes`;
            if (projectId) {
                url += `?project_id=${projectId}`;
            }

            const response = await fetch(url);
            if (!response.ok) {
                throw new Error(`Failed to fetch notes: ${response.status}`);
            }

            const data = await response.json();
            set({ notes: data.notes || [], isLoading: false });
        } catch (error) {
            console.error("Failed to fetch notes:", error);
            set({ error: String(error), isLoading: false });
        }
    },

    // Fetch all tags
    fetchTags: async (projectId?: string) => {
        try {
            let url = `${API_BASE_URL}/api/v1/notes/tags`;
            if (projectId) {
                url += `?project_id=${projectId}`;
            }

            const response = await fetch(url);
            if (!response.ok) {
                throw new Error(`Failed to fetch tags: ${response.status}`);
            }

            const tags = await response.json();
            set({ allTags: tags || [] });
        } catch (error) {
            console.error("Failed to fetch tags:", error);
        }
    },

    // Create a new note
    createNote: async (noteData: CreateNoteRequest) => {
        set({ isSaving: true, error: null });
        try {
            const response = await fetch(`${API_BASE_URL}/api/v1/notes`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(noteData),
            });

            if (!response.ok) {
                throw new Error(`Failed to create note: ${response.status}`);
            }

            const newNote = await response.json();

            // Add to state and refresh tags
            set((state) => ({
                notes: [newNote, ...state.notes],
                isSaving: false,
                isEditorOpen: false,
                editingNote: null,
            }));

            // Refresh tags
            get().fetchTags();

            return newNote;
        } catch (error) {
            console.error("Failed to create note:", error);
            set({ error: String(error), isSaving: false });
            return null;
        }
    },

    // Update an existing note
    updateNote: async (id: string, updates: UpdateNoteRequest) => {
        set({ isSaving: true, error: null });
        try {
            const response = await fetch(`${API_BASE_URL}/api/v1/notes/${id}`, {
                method: "PATCH",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(updates),
            });

            if (!response.ok) {
                throw new Error(`Failed to update note: ${response.status}`);
            }

            const updatedNote = await response.json();

            // Update in state
            set((state) => ({
                notes: state.notes.map((n) =>
                    n.note_id === id ? updatedNote : n
                ),
                isSaving: false,
                isEditorOpen: false,
                editingNote: null,
            }));

            // Refresh tags
            get().fetchTags();

            return updatedNote;
        } catch (error) {
            console.error("Failed to update note:", error);
            set({ error: String(error), isSaving: false });
            return null;
        }
    },

    // Delete a note
    deleteNote: async (id: string) => {
        try {
            const response = await fetch(`${API_BASE_URL}/api/v1/notes/${id}`, {
                method: "DELETE",
            });

            if (!response.ok) {
                throw new Error(`Failed to delete note: ${response.status}`);
            }

            // Remove from state
            set((state) => ({
                notes: state.notes.filter((n) => n.note_id !== id),
                selectedNoteId: state.selectedNoteId === id ? null : state.selectedNoteId,
            }));

            // Refresh tags
            get().fetchTags();

            return true;
        } catch (error) {
            console.error("Failed to delete note:", error);
            set({ error: String(error) });
            return false;
        }
    },

    // Toggle pin status
    togglePin: async (id: string) => {
        try {
            const response = await fetch(`${API_BASE_URL}/api/v1/notes/${id}/pin`, {
                method: "POST",
            });

            if (!response.ok) {
                throw new Error(`Failed to toggle pin: ${response.status}`);
            }

            const updatedNote = await response.json();

            // Update in state and re-sort (pinned first)
            set((state) => ({
                notes: state.notes
                    .map((n) => (n.note_id === id ? updatedNote : n))
                    .sort((a, b) => {
                        if (a.is_pinned !== b.is_pinned) {
                            return b.is_pinned ? 1 : -1;
                        }
                        return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
                    }),
            }));
        } catch (error) {
            console.error("Failed to toggle pin:", error);
            set({ error: String(error) });
        }
    },

    // Selection & editing
    selectNote: (id: string | null) => set({ selectedNoteId: id }),

    openEditor: (note?: Note) => set({
        isEditorOpen: true,
        editingNote: note || null
    }),

    closeEditor: () => set({
        isEditorOpen: false,
        editingNote: null
    }),

    // Filtering
    setSearchQuery: (query: string) => set({ searchQuery: query }),

    setSelectedTags: (tags: string[]) => set({ selectedTags: tags }),

    toggleTag: (tag: string) => set((state) => ({
        selectedTags: state.selectedTags.includes(tag)
            ? state.selectedTags.filter((t) => t !== tag)
            : [...state.selectedTags, tag],
    })),

    // View
    setViewMode: (mode: "list" | "grid") => set({ viewMode: mode }),

    // Computed - get filtered notes
    getFilteredNotes: () => {
        const { notes, searchQuery, selectedTags } = get();

        return notes.filter((note) => {
            // Search filter
            if (searchQuery) {
                const query = searchQuery.toLowerCase();
                const matchesContent = note.content.toLowerCase().includes(query);
                const matchesTitle = note.title?.toLowerCase().includes(query) || false;
                if (!matchesContent && !matchesTitle) {
                    return false;
                }
            }

            // Tag filter
            if (selectedTags.length > 0) {
                const hasMatchingTag = selectedTags.some((tag) => note.tags.includes(tag));
                if (!hasMatchingTag) {
                    return false;
                }
            }

            return true;
        });
    },
}));
