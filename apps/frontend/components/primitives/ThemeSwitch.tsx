"use client";

import { useEffect, useState } from "react";
import { useUIStore } from "@/store/uiStore";

const THEME_OPTIONS = [
    { value: "system", label: "System" },
    { value: "dark", label: "Dark" },
    { value: "light", label: "Light" },
] as const;

export function ThemeSwitch() {
    const { theme, setTheme } = useUIStore();
    const [isMounted, setIsMounted] = useState(false);

    useEffect(() => {
        setIsMounted(true);
    }, []);

    useEffect(() => {
        if (!isMounted) return;

        const root = document.body;
        if (theme === "system") {
            const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
            root.dataset.theme = prefersDark ? "dark" : "light";
        } else {
            root.dataset.theme = theme;
        }
    }, [theme, isMounted]);

    if (!isMounted) {
        return (
            <div className="flex items-center gap-2 text-xs theme-text-faint">
                Theme
            </div>
        );
    }

    return (
        <div className="flex items-center gap-2 text-xs theme-text-muted">
            <span className="uppercase tracking-wide">Theme</span>
            <div className="flex rounded-full bg-glass-100 border border-glass overflow-hidden">
                {THEME_OPTIONS.map((option) => (
                    <button
                        key={option.value}
                        onClick={() => setTheme(option.value)}
                        className={`px-3 py-1 transition-colors text-xs font-medium ${theme === option.value
                                ? "bg-cyber-blue/20 text-cyber-blue"
                                : "theme-text-muted hover:text-white"
                            }`}
                        type="button"
                    >
                        {option.label}
                    </button>
                ))}
            </div>
        </div>
    );
}
