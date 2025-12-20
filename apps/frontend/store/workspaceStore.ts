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

interface PinnedMessage {
    id: string;
    content: string;
    pinnedAt: Date;
}

interface WorkspaceState {
    // Sources
    sources: Source[];
    isLoadingSources: boolean;
    activeSourceId: string | null;
    selectedSourceIds: string[]; // Multiple sources can be selected for chat

    // View mode
    viewMode: "guide" | "chat";

    // Panels
    isNotesPanelOpen: boolean;
    isLeftSidebarOpen: boolean; // For mobile responsiveness
    isHelpModalOpen: boolean;

    // Source guide data (mocked for now)
    sourceGuide: SourceGuide | null;
    isLoadingGuide: boolean;

    // Pinned messages
    pinnedMessages: PinnedMessage[];
    pendingChatInput: string | null;

    // Project
    currentProjectId: string | null;

    // Actions
    setSources: (sources: Source[]) => void;
    setLoadingSources: (loading: boolean) => void;
    setActiveSource: (id: string | null) => void;
    toggleSourceSelection: (id: string) => void;
    setViewMode: (mode: "guide" | "chat") => void;
    toggleNotesPanel: () => void;
    toggleLeftSidebar: () => void;
    toggleHelpModal: () => void;
    setSourceGuide: (guide: SourceGuide | null) => void;
    setLoadingGuide: (loading: boolean) => void;
    pinMessage: (message: PinnedMessage) => void;
    unpinMessage: (id: string) => void;
    setPendingChatInput: (input: string | null) => void;
    setCurrentProject: (id: string | null) => void;
}

export const useWorkspaceStore = create<WorkspaceState>((set) => ({
    // Initial state
    sources: [],
    isLoadingSources: false,
    activeSourceId: null,
    selectedSourceIds: [],
    viewMode: "guide",
    isNotesPanelOpen: false,
    isLeftSidebarOpen: true,
    isHelpModalOpen: false,
    sourceGuide: null,
    isLoadingGuide: false,
    pinnedMessages: [],
    pendingChatInput: null,
    currentProjectId: null,

    // Actions
    setSources: (sources) => set({ sources }),
    setLoadingSources: (loading) => set({ isLoadingSources: loading }),
    setActiveSource: (id) => set({ activeSourceId: id, viewMode: "guide" }),
    toggleSourceSelection: (id) => set((state) => ({
        selectedSourceIds: state.selectedSourceIds.includes(id)
            ? state.selectedSourceIds.filter(sid => sid !== id)
            : [...state.selectedSourceIds, id]
    })),
    setViewMode: (mode) => set({ viewMode: mode }),
    toggleNotesPanel: () => set((state) => ({ isNotesPanelOpen: !state.isNotesPanelOpen })),
    toggleLeftSidebar: () => set((state) => ({ isLeftSidebarOpen: !state.isLeftSidebarOpen })),
    toggleHelpModal: () => set((state) => ({ isHelpModalOpen: !state.isHelpModalOpen })),
    setSourceGuide: (guide) => set({ sourceGuide: guide }),
    setLoadingGuide: (loading) => set({ isLoadingGuide: loading }),
    pinMessage: (message) => set((state) => ({
        pinnedMessages: [...state.pinnedMessages, message]
    })),
    unpinMessage: (id) => set((state) => ({
        pinnedMessages: state.pinnedMessages.filter(m => m.id !== id)
    })),
    setPendingChatInput: (input) => set({ pendingChatInput: input }),
    setCurrentProject: (id) => set({ currentProjectId: id }),
}));

