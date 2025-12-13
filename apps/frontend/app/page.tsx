import { KnowledgePanel } from "@/components/panels/KnowledgePanel";
import { ChatPanel } from "@/components/panels/ChatPanel";
import { AudioPanel } from "@/components/panels/AudioPanel";

/**
 * Main workspace page with 3-column layout:
 * - Left (20%): Knowledge Graph & Sources
 * - Center (55%): Cognitive Stream (Chat)
 * - Right (25%): Acoustic Control (Podcast Player)
 */
export default function WorkspacePage() {
    return (
        <div className="h-full grid grid-cols-[20%_55%_25%] gap-4">
            {/* Left Panel - Knowledge Graph */}
            <aside className="glass-panel flex flex-col overflow-hidden">
                <KnowledgePanel />
            </aside>

            {/* Center Panel - Cognitive Stream */}
            <main className="glass-panel flex flex-col overflow-hidden">
                <ChatPanel />
            </main>

            {/* Right Panel - Acoustic Control */}
            <aside className="glass-panel flex flex-col overflow-hidden">
                <AudioPanel />
            </aside>
        </div>
    );
}
