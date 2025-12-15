"use client";

/**
 * Notebook - Coming Soon
 * 
 * Future feature: Saved notes and annotations view.
 */

import Link from "next/link";

export default function NotebookPage() {
    return (
        <div className="min-h-screen flex flex-col items-center justify-center p-8 bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
            <div className="glass-panel p-12 text-center max-w-lg">
                <div className="text-6xl mb-6">📓</div>
                <h1 className="text-3xl font-bold theme-text-primary mb-4">
                    Notebook
                </h1>
                <p className="theme-text-muted mb-8">
                    View and manage all your saved notes and annotations.
                    This feature is coming soon.
                </p>
                <Link
                    href="/"
                    className="glass-button px-6 py-3 inline-block hover:shadow-glow transition-all"
                >
                    ← Back to Research Studio
                </Link>
            </div>
        </div>
    );
}
