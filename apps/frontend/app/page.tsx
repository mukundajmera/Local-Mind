"use client";

import { useMemo } from "react";
import { KnowledgePanel } from "@/components/panels/KnowledgePanel";
import { ChatPanel } from "@/components/panels/ChatPanel";
import { AudioPanel } from "@/components/panels/AudioPanel";
import { NotebookHeader } from "@/components/primitives/NotebookHeader";
import { useUIStore } from "@/store/uiStore";

/**
 * Main workspace page inspired by NotebookLM with adaptive layout:
 * - Header provides global controls (theme, modes, health).
 * - Left rail hosts the knowledge graph (collapsible).
 * - Center stream hosts conversation + insight presets.
 * - Right rail stays dedicated to audio experiences.
 */
export default function WorkspacePage() {
    const { isKnowledgePanelCollapsed } = useUIStore();

    const gridTemplate = useMemo(() => {
        return isKnowledgePanelCollapsed
            ? "grid-cols-[72px_minmax(0,1fr)_24%]"
            : "grid-cols-[24%_52%_24%]";
    }, [isKnowledgePanelCollapsed]);

    return (
        <div className="h-full flex flex-col gap-4">
            <NotebookHeader />
            <div className={`flex-1 grid ${gridTemplate} gap-4 min-h-0`}>
                <aside className="glass-panel flex flex-col overflow-hidden">
                    <KnowledgePanel />
                </aside>
                <main className="glass-panel flex flex-col overflow-hidden">
                    <ChatPanel />
                </main>
                <aside className="glass-panel flex flex-col overflow-hidden">
                    <AudioPanel />
                </aside>
            </div>
        </div>
    );
}
