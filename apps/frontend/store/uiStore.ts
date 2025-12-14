"use client";

import { create } from "zustand";

export type WorkspaceTheme = "system" | "light" | "dark";

interface UIState {
    isKnowledgePanelCollapsed: boolean;
    theme: WorkspaceTheme;
    setKnowledgePanelCollapsed: (collapsed: boolean) => void;
    toggleKnowledgePanel: () => void;
    setTheme: (theme: WorkspaceTheme) => void;
}

export const useUIStore = create<UIState>((set) => ({
    isKnowledgePanelCollapsed: false,
    theme: "system",
    setKnowledgePanelCollapsed: (collapsed) => set({ isKnowledgePanelCollapsed: collapsed }),
    toggleKnowledgePanel: () =>
        set((state) => ({ isKnowledgePanelCollapsed: !state.isKnowledgePanelCollapsed })),
    setTheme: (theme) => set({ theme }),
}));

