"use client";

import { ThemeSwitch } from "./ThemeSwitch";
import { useUIStore } from "@/store/uiStore";
import { cn } from "@/lib/utils";

const MODES = [
    { key: "insight", label: "Insight Stream" },
    { key: "podcast", label: "Podcast Studio" },
    { key: "organize", label: "Notebook" },
] as const;

export function NotebookHeader() {
    const { theme } = useUIStore();

    return (
        <header className="glass-panel flex items-center justify-between px-6 py-3 mb-4">
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
                            className={cn(
                                "px-3 py-1.5 text-xs rounded-full transition-colors",
                                mode.key === "insight"
                                    ? "bg-cyber-blue/20 text-cyber-blue"
                                    : "text-white/60 hover:text-white hover:bg-glass-100",
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
                <div className="hidden sm:flex items-center gap-2 text-xs text-white/60">
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
