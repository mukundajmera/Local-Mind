"use client";

/**
 * Sovereign Cognitive Engine - Cognitive Stream Hook
 * ===================================================
 * WebSocket hook for real-time AI streaming with token, citation, and audio handling.
 */

import { useEffect, useRef, useCallback, useState } from "react";
import { useAudioStore } from "@/store/audioStore";

// WebSocket message types
interface TextTokenMessage {
    type: "text_token";
    content: string;
    message_id: string;
}

interface CitationMarkerMessage {
    type: "citation_marker";
    citation_id: string;
    node_id: string;
    text_position: number;
}

interface AudioChunkMessage {
    type: "audio_chunk";
    data: string; // Base64 encoded audio
    chunk_index: number;
    is_final: boolean;
}

interface StreamStartMessage {
    type: "stream_start";
    session_id: string;
}

interface StreamEndMessage {
    type: "stream_end";
    session_id: string;
    total_tokens: number;
}

interface ErrorMessage {
    type: "error";
    message: string;
    code: string;
}

type WSMessage =
    | TextTokenMessage
    | CitationMarkerMessage
    | AudioChunkMessage
    | StreamStartMessage
    | StreamEndMessage
    | ErrorMessage;

// Custom event for highlighting nodes in the graph
export const HIGHLIGHT_NODE_EVENT = "highlight-node";

export function dispatchHighlightNode(nodeId: string) {
    window.dispatchEvent(
        new CustomEvent(HIGHLIGHT_NODE_EVENT, { detail: { nodeId } })
    );
}

// Connection state
export type ConnectionState = "connecting" | "connected" | "disconnected" | "error";

interface UseCognitiveStreamOptions {
    url?: string;
    autoConnect?: boolean;
    onToken?: (token: string, messageId: string) => void;
    onCitation?: (nodeId: string, citationId: string) => void;
    onStreamStart?: (sessionId: string) => void;
    onStreamEnd?: (sessionId: string, totalTokens: number) => void;
    onError?: (message: string, code: string) => void;
}

interface UseCognitiveStreamReturn {
    // Connection management
    connect: () => void;
    disconnect: () => void;
    connectionState: ConnectionState;

    // Sending messages
    sendMessage: (content: string, context?: string[]) => void;
    requestPodcast: (sourceIds: string[]) => void;

    // State
    isStreaming: boolean;
    currentMessageId: string | null;
    streamedContent: string;
    error: string | null;
}

export function useCognitiveStream(
    options: UseCognitiveStreamOptions = {}
): UseCognitiveStreamReturn {
    const {
        url = "ws://localhost:8000/ws",
        autoConnect = true,
        onToken,
        onCitation,
        onStreamStart,
        onStreamEnd,
        onError,
    } = options;

    const wsRef = useRef<WebSocket | null>(null);
    const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);

    const [connectionState, setConnectionState] = useState<ConnectionState>("disconnected");
    const [isStreaming, setIsStreaming] = useState(false);
    const [currentMessageId, setCurrentMessageId] = useState<string | null>(null);
    const [streamedContent, setStreamedContent] = useState("");
    const [error, setError] = useState<string | null>(null);

    const { addToQueue } = useAudioStore();

    // Connect to WebSocket
    const connect = useCallback(() => {
        if (wsRef.current?.readyState === WebSocket.OPEN) {
            return;
        }

        setConnectionState("connecting");
        setError(null);

        try {
            const ws = new WebSocket(url);
            wsRef.current = ws;

            ws.onopen = () => {
                console.log("[WS] Connected to Cognitive Stream");
                setConnectionState("connected");

                // Clear any reconnect timeout
                if (reconnectTimeoutRef.current) {
                    clearTimeout(reconnectTimeoutRef.current);
                    reconnectTimeoutRef.current = null;
                }
            };

            ws.onclose = (event) => {
                console.log("[WS] Disconnected:", event.code, event.reason);
                setConnectionState("disconnected");
                setIsStreaming(false);

                // Auto-reconnect after 3 seconds
                if (autoConnect && event.code !== 1000) {
                    reconnectTimeoutRef.current = setTimeout(() => {
                        console.log("[WS] Attempting reconnection...");
                        connect();
                    }, 3000);
                }
            };

            ws.onerror = (event) => {
                console.error("[WS] Error:", event);
                setConnectionState("error");
                setError("WebSocket connection failed");
            };

            ws.onmessage = (event) => {
                handleMessage(event);
            };

        } catch (err) {
            console.error("[WS] Failed to connect:", err);
            setConnectionState("error");
            setError("Failed to establish connection");
        }
    }, [url, autoConnect]);

    // Disconnect
    const disconnect = useCallback(() => {
        if (reconnectTimeoutRef.current) {
            clearTimeout(reconnectTimeoutRef.current);
            reconnectTimeoutRef.current = null;
        }

        if (wsRef.current) {
            wsRef.current.close(1000, "User disconnected");
            wsRef.current = null;
        }

        setConnectionState("disconnected");
        setIsStreaming(false);
    }, []);

    // Handle incoming messages
    const handleMessage = useCallback((event: MessageEvent) => {
        try {
            // Handle binary audio data
            if (event.data instanceof Blob) {
                handleAudioBlob(event.data);
                return;
            }

            const message: WSMessage = JSON.parse(event.data);

            switch (message.type) {
                case "text_token":
                    // Append token to current message
                    setStreamedContent((prev) => prev + message.content);
                    setCurrentMessageId(message.message_id);
                    onToken?.(message.content, message.message_id);
                    break;

                case "citation_marker":
                    // Dispatch custom event to highlight node in graph
                    dispatchHighlightNode(message.node_id);
                    onCitation?.(message.node_id, message.citation_id);
                    break;

                case "audio_chunk":
                    // Decode base64 and add to audio queue
                    handleAudioChunk(message);
                    break;

                case "stream_start":
                    setIsStreaming(true);
                    setStreamedContent("");
                    setCurrentMessageId(null);
                    onStreamStart?.(message.session_id);
                    break;

                case "stream_end":
                    setIsStreaming(false);
                    onStreamEnd?.(message.session_id, message.total_tokens);
                    break;

                case "error":
                    setError(message.message);
                    setIsStreaming(false);
                    onError?.(message.message, message.code);
                    break;

                default:
                    console.warn("[WS] Unknown message type:", message);
            }
        } catch (err) {
            console.error("[WS] Failed to parse message:", err);
        }
    }, [onToken, onCitation, onStreamStart, onStreamEnd, onError]);

    // Handle audio blob (binary WebSocket data)
    const handleAudioBlob = useCallback(async (blob: Blob) => {
        const arrayBuffer = await blob.arrayBuffer();
        const url = URL.createObjectURL(blob);

        addToQueue({
            id: `audio-${Date.now()}`,
            url,
            title: "AI Speech",
            speaker: "Assistant",
        });
    }, [addToQueue]);

    // Handle audio chunk (base64 encoded)
    const handleAudioChunk = useCallback((message: AudioChunkMessage) => {
        const binaryString = atob(message.data);
        const bytes = new Uint8Array(binaryString.length);
        for (let i = 0; i < binaryString.length; i++) {
            bytes[i] = binaryString.charCodeAt(i);
        }

        const blob = new Blob([bytes], { type: "audio/wav" });
        const url = URL.createObjectURL(blob);

        addToQueue({
            id: `audio-chunk-${message.chunk_index}`,
            url,
            title: `Segment ${message.chunk_index + 1}`,
            speaker: "Assistant",
        });
    }, [addToQueue]);

    // Send chat message
    const sendMessage = useCallback((content: string, context?: string[]) => {
        if (wsRef.current?.readyState !== WebSocket.OPEN) {
            setError("Not connected to server");
            return;
        }

        const payload = {
            type: "chat_message",
            content,
            context_node_ids: context ?? [],
            timestamp: new Date().toISOString(),
        };

        wsRef.current.send(JSON.stringify(payload));
        setStreamedContent("");
        setIsStreaming(true);
    }, []);

    // Request podcast generation
    const requestPodcast = useCallback((sourceIds: string[]) => {
        if (wsRef.current?.readyState !== WebSocket.OPEN) {
            setError("Not connected to server");
            return;
        }

        const payload = {
            type: "generate_podcast",
            source_ids: sourceIds,
            timestamp: new Date().toISOString(),
        };

        wsRef.current.send(JSON.stringify(payload));
        setIsStreaming(true);
    }, []);

    // Auto-connect on mount
    useEffect(() => {
        if (autoConnect) {
            connect();
        }

        return () => {
            disconnect();
        };
    }, [autoConnect, connect, disconnect]);

    return {
        connect,
        disconnect,
        connectionState,
        sendMessage,
        requestPodcast,
        isStreaming,
        currentMessageId,
        streamedContent,
        error,
    };
}
