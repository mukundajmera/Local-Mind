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
    status: "pending" | "processing" | "ready" | "failed";
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

    // Upload status tracking
    uploadStatus: Record<string, "pending" | "processing" | "ready" | "failed">;
    uploadErrors: Record<string, string>;

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
    setUploadStatus: (docId: string, status: "pending" | "processing" | "ready" | "failed") => void;
    setUploadError: (docId: string, error: string) => void;
    clearUploadStatus: (docId: string) => void;
    pollDocumentStatus: (docId: string, onComplete?: () => void) => () => void;
}

export const useWorkspaceStore = create<WorkspaceState>((set, get) => ({
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
    uploadStatus: {},
    uploadErrors: {},

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

    // Upload status tracking actions
    setUploadStatus: (docId, status) => set((state) => ({
        uploadStatus: { ...state.uploadStatus, [docId]: status }
    })),

    setUploadError: (docId, error) => set((state) => ({
        uploadErrors: { ...state.uploadErrors, [docId]: error }
    })),

    clearUploadStatus: (docId) => set((state) => {
        const { [docId]: _, ...restStatus } = state.uploadStatus;
        const { [docId]: __, ...restErrors } = state.uploadErrors;
        return {
            uploadStatus: restStatus,
            uploadErrors: restErrors
        };
    }),

    pollDocumentStatus: (docId, onComplete) => {
        const { setUploadStatus, setUploadError, setSources, setLoadingSources, currentProjectId } = get();

        let intervalId: NodeJS.Timeout | null = null;
        let isPolling = true;

        const poll = async () => {
            if (!isPolling) return;

            try {
                const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/sources/${docId}/status`);

                if (!response.ok) {
                    throw new Error(`Status check failed: ${response.status}`);
                }

                const data = await response.json();
                const status = data.status as "pending" | "processing" | "ready" | "failed";

                // Update status
                setUploadStatus(docId, status);

                // Handle terminal states
                if (status === "ready") {
                    // Stop polling
                    if (intervalId) {
                        clearInterval(intervalId);
                        intervalId = null;
                    }
                    isPolling = false;

                    // Refresh sources list
                    try {
                        setLoadingSources(true);
                        let url = `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/sources`;
                        if (currentProjectId) {
                            url += `?project_id=${currentProjectId}`;
                        }
                        const sourcesResponse = await fetch(url);
                        if (sourcesResponse.ok) {
                            const sourcesData = await sourcesResponse.json();
                            setSources(sourcesData.sources || []);
                        }
                    } catch (error) {
                        console.error("Failed to refresh sources:", error);
                    } finally {
                        setLoadingSources(false);
                    }

                    // Call completion callback
                    if (onComplete) onComplete();

                } else if (status === "failed") {
                    // Stop polling
                    if (intervalId) {
                        clearInterval(intervalId);
                        intervalId = null;
                    }
                    isPolling = false;

                    // Store error message
                    if (data.error_message) {
                        setUploadError(docId, data.error_message);
                    }

                    // Call completion callback
                    if (onComplete) onComplete();
                }

            } catch (error) {
                console.error(`Polling error for ${docId}:`, error);
                // Don't stop polling on network errors, just log them
            }
        };

        // Start polling immediately
        poll();

        // Then poll every 2 seconds
        intervalId = setInterval(poll, 2000);

        // Return cleanup function
        return () => {
            isPolling = false;
            if (intervalId) {
                clearInterval(intervalId);
            }
        };
    },
}));

