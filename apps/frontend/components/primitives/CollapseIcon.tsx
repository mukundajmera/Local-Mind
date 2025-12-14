"use client";

import { cn } from "@/lib/utils";

interface CollapseIconProps {
    collapsed?: boolean;
    className?: string;
}

export function CollapseIcon({ collapsed = false, className }: CollapseIconProps) {
    return (
        <svg
            className={cn("w-4 h-4 transition-transform", collapsed ? "rotate-180" : "", className)}
            viewBox="0 0 20 20"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
        >
            <path
                d="M5 7l5 5 5-5"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
                strokeLinejoin="round"
            />
        </svg>
    );
}

