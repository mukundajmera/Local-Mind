"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ThemeSwitch } from "./ThemeSwitch";
import { cn } from "@/lib/utils";
import { useWorkspaceStore } from "@/store/workspaceStore";

const NAV_ITEMS = [
    { href: "/", label: "Research Studio" },
    { href: "/notebook", label: "Notebook" },
] as const;

interface NotebookHeaderProps {
    onToggleNotes?: () => void;
    isNotesOpen?: boolean;
}

export function NotebookHeader({ onToggleNotes, isNotesOpen }: NotebookHeaderProps) {
    const pathname = usePathname();
    const { toggleHelpModal } = useWorkspaceStore();

    return (
        <header className="glass-panel flex items-center justify-between px-6 py-3">
            <div className="flex items-center gap-4">
                <div className="flex items-center gap-3">
                    <span className="theme-badge">Local Mind</span>
                </div>
                <nav className="hidden md:flex items-center gap-1" data-testid="main-nav">
                    {NAV_ITEMS.map((item) => {
                        const isActive = pathname === item.href;
                        return (
                            <Link
                                key={item.href}
                                href={item.href}
                                className={cn(
                                    "px-3 py-1.5 text-xs rounded-full transition-colors",
                                    isActive
                                        ? "bg-cyber-blue/20 text-cyber-blue font-semibold border-b-2 border-cyber-blue"
                                        : "theme-text-muted hover:text-white hover:bg-glass-100",
                                )}
                                data-testid={`nav-${item.href.replace("/", "") || "home"}`}
                            >
                                {item.label}
                            </Link>
                        );
                    })}
                </nav>
            </div>
            <div className="flex items-center gap-3">
                {/* Help Button */}
                <button
                    onClick={toggleHelpModal}
                    className="p-2 rounded-lg theme-text-muted hover:theme-text-primary hover:bg-glass-100 transition-colors"
                    title="Help & Getting Started"
                    data-testid="help-btn"
                >
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                </button>

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
                        data-testid="toggle-notes-btn"
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
