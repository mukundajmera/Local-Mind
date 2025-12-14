"use client";

/**
 * Workspace Store - State for NotebookLM-style interface
 */

import { create } from "zustand";

interface Source {
    id: string;
    title: string;
    filename: string;
    uploaded_at: string;
    status: "ready" | "processing";
    chunk_count?: number;
}

interface SourceGuide {
    summary: string;
    topics: string[];
    suggestedQuestions: string[];
}

interface WorkspaceState {
    // Sources
    sources: Source[];
    isLoadingSources: boolean;
    activeSourceId: string | null;

    // View mode
    viewMode: "guide" | "chat";

    // Notes panel
    isNotesPanelOpen: boolean;

    // Source guide data (mocked for now)
    sourceGuide: SourceGuide | null;
    isLoadingGuide: boolean;

    // Actions
    setSources: (sources: Source[]) => void;
    setLoadingSources: (loading: boolean) => void;
    setActiveSource: (id: string | null) => void;
    setViewMode: (mode: "guide" | "chat") => void;
    toggleNotesPanel: () => void;
    setSourceGuide: (guide: SourceGuide | null) => void;
    setLoadingGuide: (loading: boolean) => void;
}

export const useWorkspaceStore = create<WorkspaceState>((set) => ({
    // Initial state
    sources: [],
    isLoadingSources: false,
    activeSourceId: null,
    viewMode: "guide",
    isNotesPanelOpen: false,
    sourceGuide: null,
    isLoadingGuide: false,

    // Actions
    setSources: (sources) => set({ sources }),
    setLoadingSources: (loading) => set({ isLoadingSources: loading }),
    setActiveSource: (id) => set({ activeSourceId: id, viewMode: "guide" }),
    setViewMode: (mode) => set({ viewMode: mode }),
    toggleNotesPanel: () => set((state) => ({ isNotesPanelOpen: !state.isNotesPanelOpen })),
    setSourceGuide: (guide) => set({ sourceGuide: guide }),
    setLoadingGuide: (loading) => set({ isLoadingGuide: loading }),
}));
