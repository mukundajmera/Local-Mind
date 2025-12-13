/**
 * Sovereign Cognitive Engine - Graph Store
 * =========================================
 * Zustand store for knowledge graph state and focus context.
 */

import { create } from "zustand";

interface GraphNode {
    id: string;
    name: string;
    type: string;
    description?: string;
    val?: number; // Size for force graph
}

interface GraphLink {
    source: string;
    target: string;
    type: string;
    weight?: number;
}

interface GraphData {
    nodes: GraphNode[];
    links: GraphLink[];
}

interface GraphState {
    // Graph data
    graphData: GraphData;
    isLoading: boolean;
    error: string | null;

    // Focus context
    focusedNodeId: string | null;
    hoveredNodeId: string | null;

    // Actions
    setGraphData: (data: GraphData) => void;
    setLoading: (loading: boolean) => void;
    setError: (error: string | null) => void;

    // Focus management
    setFocusContext: (nodeId: string | null) => void;
    setHoveredNode: (nodeId: string | null) => void;
    clearFocus: () => void;

    // Node selection for chat context
    selectedNodeIds: Set<string>;
    toggleNodeSelection: (nodeId: string) => void;
    clearSelection: () => void;
}

// Sample graph data for development
const SAMPLE_GRAPH_DATA: GraphData = {
    nodes: [
        { id: "1", name: "Quantum Computing", type: "CONCEPT", val: 20 },
        { id: "2", name: "Qubits", type: "CONCEPT", val: 15 },
        { id: "3", name: "Superposition", type: "CONCEPT", val: 12 },
        { id: "4", name: "IBM", type: "ORGANIZATION", val: 18 },
        { id: "5", name: "Google", type: "ORGANIZATION", val: 18 },
        { id: "6", name: "Sycamore", type: "TECHNOLOGY", val: 14 },
        { id: "7", name: "Quantum Supremacy", type: "EVENT", val: 16 },
    ],
    links: [
        { source: "1", target: "2", type: "USES", weight: 1.0 },
        { source: "2", target: "3", type: "EXHIBITS", weight: 0.9 },
        { source: "4", target: "1", type: "RESEARCHES", weight: 0.8 },
        { source: "5", target: "1", type: "RESEARCHES", weight: 0.8 },
        { source: "5", target: "6", type: "DEVELOPED", weight: 1.0 },
        { source: "6", target: "7", type: "ACHIEVED", weight: 1.0 },
        { source: "7", target: "1", type: "MILESTONE_FOR", weight: 0.9 },
    ],
};

export const useGraphStore = create<GraphState>((set) => ({
    // Initial state
    graphData: SAMPLE_GRAPH_DATA,
    isLoading: false,
    error: null,
    focusedNodeId: null,
    hoveredNodeId: null,
    selectedNodeIds: new Set(),

    // Data actions
    setGraphData: (data) => set({ graphData: data, error: null }),
    setLoading: (loading) => set({ isLoading: loading }),
    setError: (error) => set({ error }),

    // Focus actions
    setFocusContext: (nodeId) => set({ focusedNodeId: nodeId }),
    setHoveredNode: (nodeId) => set({ hoveredNodeId: nodeId }),
    clearFocus: () => set({ focusedNodeId: null, hoveredNodeId: null }),

    // Selection actions
    toggleNodeSelection: (nodeId) => set((state) => {
        const newSelection = new Set(state.selectedNodeIds);
        if (newSelection.has(nodeId)) {
            newSelection.delete(nodeId);
        } else {
            newSelection.add(nodeId);
        }
        return { selectedNodeIds: newSelection };
    }),
    clearSelection: () => set({ selectedNodeIds: new Set() }),
}));

// Selector hooks
export const useFocusedNode = () => useGraphStore((state) => {
    if (!state.focusedNodeId) return null;
    return state.graphData.nodes.find((n) => n.id === state.focusedNodeId) ?? null;
});

export const useGraphData = () => useGraphStore((state) => state.graphData);
export const useGraphLoading = () => useGraphStore((state) => state.isLoading);
