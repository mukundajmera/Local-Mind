"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ThemeSwitch } from "./ThemeSwitch";
import { cn } from "@/lib/utils";
import { useWorkspaceStore } from "@/store/workspaceStore";
import { useState, useEffect, useRef } from "react";
import { API_BASE_URL } from "@/lib/api";
import { ChevronDown } from "lucide-react";

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

    const [models, setModels] = useState<string[]>([]);
    const [currentModel, setCurrentModel] = useState<string>("Loading...");
    const [isModelDropdownOpen, setIsModelDropdownOpen] = useState(false);
    const dropdownRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        // Fetch available models
        fetch(`${API_BASE_URL}/api/v1/system/models/available`)
            .then(res => res.json())
            .then(data => setModels(Array.isArray(data) ? data : []))
            .catch(err => console.error("Failed to fetch available models", err));

        // Fetch current model
        fetch(`${API_BASE_URL}/api/v1/system/models/current`)
            .then(res => res.json())
            .then(data => setCurrentModel(data.current_model || "Ready"))
            .catch(err => {
                console.error("Failed to fetch current model", err);
                setCurrentModel("Ready");
            });

        // Close dropdown when clicking outside
        const handleClickOutside = (event: MouseEvent) => {
            if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
                setIsModelDropdownOpen(false);
            }
        };
        document.addEventListener("mousedown", handleClickOutside);
        return () => document.removeEventListener("mousedown", handleClickOutside);
    }, []);

    const handleModelSelect = async (model: string) => {
        setCurrentModel("Switching...");
        setIsModelDropdownOpen(false);
        try {
            const res = await fetch(`${API_BASE_URL}/api/v1/system/models/switch`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ model_name: model })
            });
            if (res.ok) {
                const data = await res.json();
                setCurrentModel(data.current_model);
            } else {
                setCurrentModel(model);
            }
        } catch (err) {
            console.error("Failed to switch model", err);
            setCurrentModel(model);
        }
    };

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

                {/* Dynamic Status / Model Selector */}
                <div
                    className="hidden sm:flex items-center gap-2 text-xs theme-text-muted relative group"
                    ref={dropdownRef}
                    onMouseEnter={() => setIsModelDropdownOpen(true)}
                    onMouseLeave={() => setIsModelDropdownOpen(false)}
                >
                    <span>Model:</span>
                    <button
                        className="flex items-center gap-1.5 text-cyber-blue hover:text-blue-400 bg-glass-100 px-2 py-1 rounded transition-colors"
                        title="Hover to change model"
                    >
                        {currentModel === "Switching..." || currentModel === "Loading..." ? (
                            <span className="w-2 h-2 rounded-full bg-cyber-blue animate-pulse" />
                        ) : (
                            <span className="w-2 h-2 rounded-full bg-cyber-green" />
                        )}
                        <span className="max-w-[150px] truncate">{currentModel}</span>
                        <ChevronDown className={`w-3 h-3 transition-transform group-hover:rotate-180`} />
                    </button>

                    <div className={`absolute top-full right-0 mt-2 w-48 bg-gray-900 border border-glass rounded-lg shadow-xl backdrop-blur-xl overflow-hidden z-50 transition-all duration-200 origin-top ${isModelDropdownOpen ? 'opacity-100 scale-y-100' : 'opacity-0 scale-y-0 pointer-events-none'}`}>
                        <div className="max-h-60 overflow-y-auto py-1">
                            {models.length === 0 ? (
                                <div className="px-3 py-2 text-xs text-gray-500">No models found</div>
                            ) : (
                                models.map(model => (
                                    <div
                                        key={model}
                                        onClick={() => handleModelSelect(model)}
                                        className={`px-3 py-2 cursor-pointer text-xs ${currentModel === model
                                            ? "bg-cyber-blue/20 text-cyber-blue"
                                            : "text-gray-300 hover:bg-white/10"
                                            }`}
                                    >
                                        <div className="truncate">{model}</div>
                                    </div>
                                ))
                            )}
                        </div>
                    </div>
                </div>
            </div>
        </header>
    );
}
