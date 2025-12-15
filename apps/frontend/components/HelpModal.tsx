"use client";

/**
 * HelpModal - User guide modal explaining the 4-step workflow
 */

import { useWorkspaceStore } from "@/store/workspaceStore";

const HELP_STEPS = [
    {
        number: 1,
        title: "Upload",
        icon: "📤",
        description: "Add your documents by clicking '+ Add' in the Sources panel. Supports PDF, Markdown, and TXT files.",
    },
    {
        number: 2,
        title: "Select",
        icon: "☑️",
        description: "Use the checkbox to select sources for chat. Click the title to view the document summary.",
        tip: "Checkbox = 'Chat with this' | Click Title = 'Read Summary'",
    },
    {
        number: 3,
        title: "Chat",
        icon: "💬",
        description: "Ask questions across your selected sources. The AI will search and synthesize information from all checked documents.",
    },
    {
        number: 4,
        title: "Pin",
        icon: "📌",
        description: "Hover over AI responses and click Pin to save key insights to your Notes panel for later reference.",
    },
];

export function HelpModal() {
    const { isHelpModalOpen, toggleHelpModal } = useWorkspaceStore();

    if (!isHelpModalOpen) return null;

    return (
        <div
            className="help-modal-overlay"
            onClick={(e) => {
                if (e.target === e.currentTarget) toggleHelpModal();
            }}
        >
            <div className="help-modal" onClick={(e) => e.stopPropagation()}>
                {/* Header */}
                <div className="flex items-center justify-between px-6 py-4 border-b border-glass">
                    <h2 className="text-lg font-semibold theme-text-primary">
                        How to Use Local Mind
                    </h2>
                    <button
                        onClick={toggleHelpModal}
                        className="p-2 rounded-lg theme-text-muted hover:theme-text-primary hover:bg-glass-100 transition-colors"
                        aria-label="Close help modal"
                    >
                        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                        </svg>
                    </button>
                </div>

                {/* Content */}
                <div className="p-6 space-y-2">
                    <p className="theme-text-muted text-sm mb-4">
                        Local Mind helps you research and analyze documents with AI. Follow these 4 steps:
                    </p>

                    {HELP_STEPS.map((step) => (
                        <div key={step.number} className="help-step">
                            <div className="help-step-number">
                                {step.number}
                            </div>
                            <div className="flex-1">
                                <div className="flex items-center gap-2 mb-1">
                                    <span className="text-lg">{step.icon}</span>
                                    <h3 className="font-semibold theme-text-primary">
                                        {step.title}
                                    </h3>
                                </div>
                                <p className="text-sm theme-text-muted">
                                    {step.description}
                                </p>
                                {step.tip && (
                                    <p className="text-xs mt-1 px-2 py-1 rounded bg-glass-100 theme-text-faint inline-block">
                                        💡 {step.tip}
                                    </p>
                                )}
                            </div>
                        </div>
                    ))}
                </div>

                {/* Footer */}
                <div className="px-6 py-4 border-t border-glass">
                    <button
                        onClick={toggleHelpModal}
                        className="w-full py-2 rounded-lg bg-research-accent-blue text-white font-medium hover:bg-research-accent-blueLight transition-colors"
                        style={{ background: "var(--cyber-blue, #4f46e5)" }}
                    >
                        Got it!
                    </button>
                </div>
            </div>
        </div>
    );
}
