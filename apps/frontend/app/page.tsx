"use client";

import { SourcesSidebar } from "@/components/panels/SourcesSidebar";
import { NotesSidebar } from "@/components/panels/NotesSidebar";
import { SourceGuide } from "@/components/SourceGuide";
import { ChatPanel } from "@/components/panels/ChatPanel";
import { NotebookHeader } from "@/components/primitives/NotebookHeader";
import { HelpModal } from "@/components/HelpModal";
import { useWorkspaceStore } from "@/store/workspaceStore";

/**
 * Main workspace page - NotebookLM-style 3-pane layout:
 * - Left: Sources sidebar (uploaded files)
 * - Center: Workspace (Source Guide or Chat)
 * - Right: Notes sidebar (collapsible)
 */
export default function WorkspacePage() {
    const { viewMode, isNotesPanelOpen, toggleNotesPanel, isLeftSidebarOpen } = useWorkspaceStore();

    return (
        <div className="h-full flex flex-col gap-4">
            <NotebookHeader onToggleNotes={toggleNotesPanel} isNotesOpen={isNotesPanelOpen} />

            <div className="flex-1 flex gap-4 min-h-0">
                {/* Left Sidebar - Sources */}
                <aside className={`w-72 glass-panel flex flex-col overflow-hidden shrink-0 sidebar-collapsible ${!isLeftSidebarOpen ? 'collapsed' : ''}`}>
                    <SourcesSidebar />
                </aside>

                {/* Center - Workspace (Guide or Chat) */}
                <main className="flex-1 glass-panel flex flex-col overflow-hidden">
                    {viewMode === "guide" ? <SourceGuide /> : <ChatPanel />}
                </main>

                {/* Right Sidebar - Notes (Collapsible) */}
                {isNotesPanelOpen && (
                    <aside className="glass-panel flex flex-col overflow-hidden shrink-0">
                        <NotesSidebar />
                    </aside>
                )}
            </div>

            {/* Help Modal */}
            <HelpModal />
        </div>
    );
}

