"use client";

import React, { useEffect, useState, useRef, useCallback } from "react";
import { createPortal } from "react-dom";
import { API_BASE_URL } from "@/lib/api";
import { useWorkspaceStore } from "@/store/workspaceStore";
import { ChevronDown, Cpu } from "lucide-react";

interface Model {
    id: string;
    name: string;
}

export default function ModelSelector() {
    const { selectedModel, setSelectedModel } = useWorkspaceStore();
    const [models, setModels] = useState<Model[]>([]);
    const [isOpen, setIsOpen] = useState(false);
    const [isLoading, setIsLoading] = useState(false);
    const [provider, setProvider] = useState<string>("ollama");
    const [dropdownPos, setDropdownPos] = useState({ top: 0, left: 0 });
    const buttonRef = useRef<HTMLButtonElement>(null);

    useEffect(() => {
        const fetchModels = async () => {
            setIsLoading(true);
            try {
                const res = await fetch(`${API_BASE_URL}/api/v1/models`);
                if (res.ok) {
                    const data = await res.json();
                    setModels(data.models || []);
                    setProvider(data.provider || "ollama");

                    if (!selectedModel && data.default) {
                        setSelectedModel(data.default);
                    }
                }
            } catch {
                // Silently handle backend offline state
            } finally {
                setIsLoading(false);
            }
        };

        fetchModels();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    const openDropdown = useCallback(() => {
        if (buttonRef.current) {
            const rect = buttonRef.current.getBoundingClientRect();
            setDropdownPos({
                top: rect.bottom + window.scrollY + 4,
                left: rect.left + window.scrollX,
            });
        }
        setIsOpen(true);
    }, []);

    // Close dropdown when clicking outside
    useEffect(() => {
        if (!isOpen) return;

        const handleOutsideClick = (e: MouseEvent) => {
            // Close any click not inside the dropdown portal
            const target = e.target as HTMLElement;
            if (!target.closest("[data-model-dropdown]") && !target.closest("[data-model-button]")) {
                setIsOpen(false);
            }
        };

        document.addEventListener("mousedown", handleOutsideClick);
        return () => document.removeEventListener("mousedown", handleOutsideClick);
    }, [isOpen]);

    const dropdown = isOpen ? (
        <div
            data-model-dropdown="true"
            style={{
                position: "fixed",
                top: dropdownPos.top,
                left: dropdownPos.left,
                zIndex: 9999,
                width: "224px",
            }}
            className="bg-gray-800 border border-gray-700 rounded-md shadow-2xl overflow-hidden animate-in fade-in slide-in-from-top-2 duration-100"
        >
            <div className="px-3 py-2 border-b border-gray-700 bg-gray-900/80">
                <div className="text-xs font-semibold text-gray-400 uppercase tracking-wider flex justify-between items-center">
                    <span>Available Models</span>
                    <span className="bg-gray-700 text-gray-300 px-1.5 py-0.5 rounded text-[10px]">{provider}</span>
                </div>
            </div>

            <div className="max-h-64 overflow-y-auto py-1">
                {models.length === 0 ? (
                    <div className="px-4 py-3 text-sm text-gray-500 text-center">
                        No models found
                    </div>
                ) : (
                    models.map((model) => (
                        <button
                            key={model.id}
                            onClick={() => {
                                setSelectedModel(model.id);
                                setIsOpen(false);
                            }}
                            className={`w-full text-left px-4 py-2.5 text-sm transition-colors hover:bg-gray-700 flex items-center gap-2 ${selectedModel === model.id
                                    ? "bg-indigo-600/20 text-indigo-300 font-medium"
                                    : "text-gray-300"
                                }`}
                        >
                            {selectedModel === model.id && (
                                <span className="text-indigo-400">✓</span>
                            )}
                            {model.name}
                        </button>
                    ))
                )}
            </div>
        </div>
    ) : null;

    return (
        <>
            <button
                ref={buttonRef}
                data-model-button="true"
                onClick={(e) => {
                    e.stopPropagation();
                    if (isOpen) {
                        setIsOpen(false);
                    } else {
                        openDropdown();
                    }
                }}
                disabled={isLoading && models.length === 0}
                className="flex items-center space-x-2 px-3 py-1.5 bg-gray-800 hover:bg-gray-700 text-white rounded-md text-sm transition-colors border border-gray-700 disabled:opacity-50 cursor-pointer"
            >
                <Cpu className="h-4 w-4 text-gray-400 shrink-0" />
                <span className="font-medium truncate max-w-[120px]">
                    {isLoading && models.length === 0
                        ? "Loading..."
                        : selectedModel || "Select Model"}
                </span>
                <ChevronDown className={`h-4 w-4 text-gray-400 shrink-0 transition-transform ${isOpen ? "rotate-180" : ""}`} />
            </button>

            {typeof window !== "undefined" && dropdown
                ? createPortal(dropdown, document.body)
                : null}
        </>
    );
}
