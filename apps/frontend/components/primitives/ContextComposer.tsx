"use client";

import { useMemo } from "react";
import { useGraphStore, useGraphData } from "@/store/graphStore";
import { cn } from "@/lib/utils";

export function ContextComposer() {
    const { selectedNodeIds, toggleNodeSelection, clearSelection } = useGraphStore();
    const graphData = useGraphData();

    const selectedNodes = useMemo(() => {
        return graphData.nodes.filter((node) => selectedNodeIds.has(node.id));
    }, [graphData.nodes, selectedNodeIds]);

    if (selectedNodes.length === 0) {
        return (
            <div className="flex items-center justify-between px-4 py-2 text-xs theme-text-muted">
                <span>Pick nodes in the graph to focus the assistant.</span>
            </div>
        );
    }

    return (
        <div className="flex flex-wrap items-center gap-2 px-4 py-2 border-b border-glass">
            {selectedNodes.map((node) => (
                <button
                    key={node.id}
                    onClick={() => toggleNodeSelection(node.id)}
                    className={cn(
                        "theme-chip",
                        "hover:bg-cyber-blue/30 hover:text-white transition-colors",
                    )}
                    type="button"
                >
                    <span className="text-[10px] uppercase tracking-widest opacity-60">{node.type}</span>
                    <span>{node.name}</span>
                    <span className="text-white/40 ml-1">×</span>
                </button>
            ))}
            <button
                onClick={clearSelection}
                className="ml-auto text-xs text-white/50 hover:text-white transition-colors"
                type="button"
            >
                Clear all
            </button>
        </div>
    );
}

