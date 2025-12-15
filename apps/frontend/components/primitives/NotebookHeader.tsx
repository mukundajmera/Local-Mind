"use client";

import { useState } from "react";
import { ThemeSwitch } from "./ThemeSwitch";
import { cn } from "@/lib/utils";

const MODES = [
    { key: "insight", label: "Insight Stream" },
    { key: "podcast", label: "Podcast Studio" },
    { key: "organize", label: "Notebook" },
] as const;

type ModeKey = typeof MODES[number]["key"];

interface NotebookHeaderProps {
    onToggleNotes?: () => void;
    isNotesOpen?: boolean;
}

export function NotebookHeader({ onToggleNotes, isNotesOpen }: NotebookHeaderProps) {
    const [activeMode, setActiveMode] = useState<ModeKey>("insight");

    return (
        <header className="glass-panel flex items-center justify-between px-6 py-3">
            <div className="flex items-center gap-4">
                <div className="flex items-center gap-3">
                    <span className="theme-badge">Local Mind</span>
                    <h1 className="text-lg font-semibold theme-text-primary">
                        Research Studio
                    </h1>
                </div>
                <nav className="hidden md:flex items-center gap-1">
                    {MODES.map((mode) => (
                        <button
                            key={mode.key}
                            onClick={() => setActiveMode(mode.key)}
                            className={cn(
                                "px-3 py-1.5 text-xs rounded-full transition-colors",
                                mode.key === activeMode
                                    ? "bg-cyber-blue/20 text-cyber-blue"
                                    : "theme-text-muted hover:text-white hover:bg-glass-100",
                            )}
                            type="button"
                        >
                            {mode.label}
                        </button>
                    ))}
                </nav>
            </div>
            <div className="flex items-center gap-4">
                <ThemeSwitch />
                {onToggleNotes && (
                    <button
                        onClick={onToggleNotes}
                        className={cn(
                            "p-2 rounded-lg transition-colors",
                            isNotesOpen
                                ? "bg-cyber-blue/20 text-cyber-blue"
                                : "theme-text-muted hover:text-white hover:bg-glass-100"
                        )}
                        title={isNotesOpen ? "Hide notes" : "Show notes"}
                    >
                        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                        </svg>
                    </button>
                )}
                <div className="hidden sm:flex items-center gap-2 text-xs theme-text-muted">
                    <span>Status:</span>
                    <span className="flex items-center gap-1 text-cyber-blue">
                        <span className="w-2 h-2 rounded-full bg-cyber-blue animate-pulse" />
                        Ready
                    </span>
                </div>
            </div>
        </header>
    );
}

