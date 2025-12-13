"use client";

/**
 * Sovereign Cognitive Engine - 3D Graph Visualization
 * =====================================================
 * Interactive force-directed graph with citation syncer for "Director Mode".
 */

import React, { useCallback, useRef, useEffect, useState } from "react";
import dynamic from "next/dynamic";
import { useGraphStore, useGraphData } from "@/store/graphStore";
import { HIGHLIGHT_NODE_EVENT } from "@/hooks/useCognitiveStream";

// Dynamic import to avoid SSR issues with Three.js
const ForceGraph3D = dynamic(() => import("react-force-graph-3d"), {
    ssr: false,
    loading: () => (
        <div className="h-full w-full flex items-center justify-center">
            <div className="text-white/50 text-sm">Loading graph...</div>
        </div>
    ),
});

// Node color mapping by type
const NODE_COLORS: Record<string, string> = {
    PERSON: "#ec4899",       // Pink
    CONCEPT: "#00d4ff",      // Cyber blue
    ORGANIZATION: "#a855f7", // Purple
    TECHNOLOGY: "#22c55e",   // Green
    EVENT: "#f59e0b",        // Amber
    LOCATION: "#06b6d4",     // Cyan
    DEFAULT: "#64748b",      // Slate
};

// Link color by type
const LINK_COLORS: Record<string, string> = {
    DEVELOPED: "#22c55e",
    RESEARCHES: "#a855f7",
    USES: "#00d4ff",
    DEFAULT: "rgba(255, 255, 255, 0.15)",
};

interface GraphViewProps {
    width?: number;
    height?: number;
}

export function GraphView({ width, height }: GraphViewProps) {
    const graphRef = useRef<any>(null);
    const containerRef = useRef<HTMLDivElement>(null);

    const graphData = useGraphData();
    const { setFocusContext, setHoveredNode, focusedNodeId } = useGraphStore();
    const [dimensions, setDimensions] = useState({ width: 400, height: 300 });

    // ==========================================================================
    // Citation Syncer - "Director Mode" camera control
    // ==========================================================================
    // Listens for highlight-node events dispatched by the WebSocket hook
    // and smoothly flies the camera to the cited node.

    const flyToNode = useCallback((nodeId: string) => {
        if (!graphRef.current) return;

        // Find the node in graph data
        const node = graphData.nodes.find((n) => n.id === nodeId);
        if (!node) {
            console.warn(`[GraphView] Node ${nodeId} not found for flyTo`);
            return;
        }

        // Get node's 3D position from the force graph
        const graphNode = graphRef.current.graphData().nodes.find(
            (n: any) => n.id === nodeId
        );

        if (!graphNode || graphNode.x === undefined) {
            console.warn(`[GraphView] Node ${nodeId} has no position yet`);
            return;
        }

        // Set focus context
        setFocusContext(nodeId);

        // Calculate camera position for smooth flyTo
        const distance = 100;
        const distRatio = 1 + distance / Math.hypot(
            graphNode.x || 0,
            graphNode.y || 0,
            graphNode.z || 0
        );

        // Fly camera to node over 1 second
        graphRef.current.cameraPosition(
            {
                x: graphNode.x * distRatio,
                y: graphNode.y * distRatio,
                z: graphNode.z * distRatio,
            },
            graphNode, // lookAt target
            1000       // 1 second transition
        );

        console.log(`[GraphView] Flying to node: ${node.name}`);
    }, [graphData.nodes, setFocusContext]);

    // Listen for citation highlight events
    useEffect(() => {
        const handleHighlightNode = (event: CustomEvent<{ nodeId: string }>) => {
            flyToNode(event.detail.nodeId);
        };

        window.addEventListener(
            HIGHLIGHT_NODE_EVENT,
            handleHighlightNode as EventListener
        );

        return () => {
            window.removeEventListener(
                HIGHLIGHT_NODE_EVENT,
                handleHighlightNode as EventListener
            );
        };
    }, [flyToNode]);

    // ==========================================================================
    // Node Click Handler
    // ==========================================================================

    const handleNodeClick = useCallback((node: any) => {
        setFocusContext(node.id);

        // Zoom to node
        if (graphRef.current) {
            const distance = 120;
            const distRatio = 1 + distance / Math.hypot(node.x, node.y, node.z);

            graphRef.current.cameraPosition(
                {
                    x: node.x * distRatio,
                    y: node.y * distRatio,
                    z: node.z * distRatio,
                },
                node, // lookAt
                2000  // transition ms
            );
        }
    }, [setFocusContext]);

    // Handle node hover
    const handleNodeHover = useCallback((node: any | null) => {
        setHoveredNode(node?.id ?? null);

        // Change cursor
        if (containerRef.current) {
            containerRef.current.style.cursor = node ? "pointer" : "grab";
        }
    }, [setHoveredNode]);

    // ==========================================================================
    // Node Rendering - Glowing Spheres
    // ==========================================================================

    const nodeThreeObject = useCallback((node: any) => {
        // Only import THREE on client side
        const THREE = require("three");

        const color = NODE_COLORS[node.type] || NODE_COLORS.DEFAULT;
        const isFocused = node.id === focusedNodeId;

        // Create sphere geometry
        const geometry = new THREE.SphereGeometry(isFocused ? 6 : 4, 16, 16);

        // Glowing material
        const material = new THREE.MeshBasicMaterial({
            color: color,
            transparent: true,
            opacity: isFocused ? 1 : 0.8,
        });

        const sphere = new THREE.Mesh(geometry, material);

        // Add glow effect for focused node
        if (isFocused) {
            const glowGeometry = new THREE.SphereGeometry(10, 16, 16);
            const glowMaterial = new THREE.MeshBasicMaterial({
                color: color,
                transparent: true,
                opacity: 0.2,
            });
            const glow = new THREE.Mesh(glowGeometry, glowMaterial);
            sphere.add(glow);
        }

        return sphere;
    }, [focusedNodeId]);

    // Link styling
    const linkColor = useCallback((link: any) => {
        return LINK_COLORS[link.type] || LINK_COLORS.DEFAULT;
    }, []);

    const linkWidth = useCallback((link: any) => {
        return (link.weight || 0.5) * 2;
    }, []);

    // ==========================================================================
    // Auto-resize
    // ==========================================================================

    useEffect(() => {
        const updateDimensions = () => {
            if (containerRef.current) {
                setDimensions({
                    width: containerRef.current.clientWidth,
                    height: containerRef.current.clientHeight,
                });
            }
        };

        updateDimensions();
        window.addEventListener("resize", updateDimensions);

        return () => window.removeEventListener("resize", updateDimensions);
    }, []);

    return (
        <div ref={containerRef} className="h-full w-full">
            <ForceGraph3D
                ref={graphRef}
                graphData={graphData}
                width={width ?? dimensions.width}
                height={height ?? dimensions.height}
                backgroundColor="rgba(0,0,0,0)"
                nodeLabel={(node: any) => `${node.name} (${node.type})`}
                nodeThreeObject={nodeThreeObject}
                nodeThreeObjectExtend={false}
                onNodeClick={handleNodeClick}
                onNodeHover={handleNodeHover}
                linkColor={linkColor}
                linkWidth={linkWidth}
                linkOpacity={0.6}
                linkDirectionalParticles={2}
                linkDirectionalParticleWidth={1}
                linkDirectionalParticleColor={() => "#00d4ff"}
                enableNodeDrag={true}
                enableNavigationControls={true}
                showNavInfo={false}
            />
        </div>
    );
}

