"use client";

/**
 * Chat Panel - Center cognitive stream interface
 */

import { useState, useRef, useEffect, useMemo } from "react";
import { useFocusedNode, useGraphStore } from "@/store/graphStore";
import { ContextComposer } from "@/components/primitives/ContextComposer";

const STRATEGIES = [
    {
        id: "insight" as const,
        label: "Graph Insight",
        description: "Ground answers in relationships across the knowledge graph.",
    },
    {
        id: "sources" as const,
        label: "Source Citations",
        description: "Quote supporting passages with document titles and page numbers.",
    },
    {
        id: "podcast" as const,
        label: "Podcast Script",
        description: "Return a dialogue-ready narrative for audio synthesis.",
    },
] as const;

type StrategyKey = (typeof STRATEGIES)[number]["id"];

const PROMPT_SUGGESTIONS = [
    {
        id: "daily-brief",
        label: "Daily Brief",
        prompt: "Give me a daily brief of the most important updates inside this notebook.",
    },
    {
        id: "compare",
        label: "Compare Perspectives",
        prompt: "Compare the differing viewpoints or findings across my sources on this topic.",
    },
    {
        id: "action-items",
        label: "Action Items",
        prompt: "List the key action items and open questions I should follow up on next.",
    },
] as const;

interface Message {
    id: string;
    role: "user" | "assistant";
    content: string;
    timestamp: Date | null;
}

/**
 * Client-only timestamp component to prevent React hydration mismatch.
 * Renders a placeholder during SSR and formats on the client after mount.
 */
function FormattedTime({ date }: { date: Date }) {
    const [formatted, setFormatted] = useState("--:--");

    useEffect(() => {
        const formatter = new Intl.DateTimeFormat(undefined, {
            hour: "2-digit",
            minute: "2-digit",
        });
        setFormatted(formatter.format(date));
    }, [date]);

    return <>{formatted}</>;
}

const INITIAL_MESSAGES: Message[] = [
    {
        id: "welcome",
        role: "assistant",
        content: "Welcome to the Sovereign Cognitive Engine. Upload documents to build your knowledge graph, then ask questions or generate podcast episodes.",
        timestamp: null,
    },
];

export function ChatPanel() {
    const [messages, setMessages] = useState<Message[]>(INITIAL_MESSAGES);
    const [input, setInput] = useState("");
    const [isLoading, setIsLoading] = useState(false);
    const [activeStrategies, setActiveStrategies] = useState<StrategyKey[]>(["insight", "sources"]);
    const scrollRef = useRef<HTMLDivElement>(null);
    const focusedNode = useFocusedNode();
    const { selectedNodeIds } = useGraphStore();
    const contextNodeIds = useMemo(() => {
        const ids = Array.from(selectedNodeIds);
        if (ids.length > 0) {
            return ids;
        }
        if (focusedNode) {
            return [focusedNode.id];
        }
        return [];
    }, [selectedNodeIds, focusedNode]);

    const toggleStrategy = (strategy: StrategyKey) => {
        setActiveStrategies((prev) =>
            prev.includes(strategy)
                ? prev.filter((s) => s !== strategy)
                : [...prev, strategy]
        );
    };

    const applyStrategy = (strategy: StrategyKey) => {
        setActiveStrategies((prev) =>
            prev.includes(strategy) ? prev : [...prev, strategy]
        );
    };

    const handleSuggestion = (prompt: string) => {
        setInput(prompt);
        const textarea = scrollRef.current?.parentElement?.querySelector<HTMLTextAreaElement>("textarea");
        if (textarea) {
            textarea.focus();
        }
    };

    // Auto-scroll to bottom
    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [messages]);

    // Handle send message
    const handleSend = async () => {
        if (!input.trim() || isLoading) return;

        const userMessage: Message = {
            id: Date.now().toString(),
            role: "user",
            content: input,
            timestamp: new Date(),
        };

        setMessages((prev) => [...prev, userMessage]);
        const userInput = input;
        setInput("");
        setIsLoading(true);

        try {
            // Call the backend chat API
            const response = await fetch("http://localhost:8000/api/v1/chat", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({
                    message: userInput,
                    context_node_ids: contextNodeIds,
                    strategies: activeStrategies,
                }),
            });

            if (!response.ok) {
                const error = await response.json().catch(() => ({ detail: "Unknown error" }));
                throw new Error(error.detail || `HTTP ${response.status}`);
            }

            const data = await response.json();

            const assistantMessage: Message = {
                id: (Date.now() + 1).toString(),
                role: "assistant",
                content: data.response,
                timestamp: new Date(),
            };
            setMessages((prev) => [...prev, assistantMessage]);
        } catch (error) {
            console.error("Chat API error:", error);
            const errorMessage: Message = {
                id: (Date.now() + 1).toString(),
                role: "assistant",
                content: `⚠️ Error: ${error instanceof Error ? error.message : "Failed to connect to LLM service"}. Please ensure the backend is running and LM Studio is active.`,
                timestamp: new Date(),
            };
            setMessages((prev) => [...prev, errorMessage]);
        } finally {
            setIsLoading(false);
        }
    };


    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    };

    const appendAssistantMessage = (content: string) => {
        setMessages((prev) => [
            ...prev,
            {
                id: `${Date.now()}-assistant`,
                role: "assistant",
                content,
                timestamp: new Date(),
            },
        ]);
    };

    const handleQuickAction = (action: "podcast" | "summarize" | "deep-dive") => {
        switch (action) {
            case "podcast":
                applyStrategy("podcast");
                setInput("Create a podcast-style script with two hosts discussing the highlighted context.");
                break;
            case "summarize":
                applyStrategy("insight");
                setInput("Summarize the current knowledge graph focus with bullet points and key evidence.");
                break;
            case "deep-dive":
                applyStrategy("sources");
                setInput("Run a deep dive analysis citing the most relevant passages for this question.");
                break;
            default:
                break;
        }
    };

    return (
        <div className="flex flex-col h-full" data-testid="chat-panel">
            {/* Header */}
            <div className="panel-header flex items-center justify-between" data-testid="chat-header">
                <span>Cognitive Stream</span>
                {focusedNode && (
                    <span className="text-xs text-cyber-blue">
                        Context: {focusedNode.name}
                    </span>
                )}
            </div>

            <ContextComposer />

            <div className="px-4 py-3 border-b border-glass flex flex-wrap items-center gap-3" data-testid="strategy-selector">
                <span className="text-[11px] uppercase tracking-wide text-white/40">Response Strategies</span>
                {STRATEGIES.map((strategy) => (
                    <label
                        key={strategy.id}
                        className={`flex items-center gap-2 px-3 py-1.5 rounded-full border ${
                            activeStrategies.includes(strategy.id)
                                ? "border-cyber-blue/60 bg-cyber-blue/20 text-cyber-blue"
                                : "border-glass text-white/60 hover:text-white"
                        } transition-colors text-xs`}
                    >
                        <input
                            type="checkbox"
                            checked={activeStrategies.includes(strategy.id)}
                            onChange={() => toggleStrategy(strategy.id)}
                            className="accent-cyber-blue"
                        />
                        <span>{strategy.label}</span>
                    </label>
                ))}
            </div>

            <div className="px-4 py-2 border-b border-glass flex flex-wrap gap-2" data-testid="chat-suggestions">
                {PROMPT_SUGGESTIONS.map((suggestion) => (
                    <button
                        key={suggestion.id}
                        onClick={() => handleSuggestion(suggestion.prompt)}
                        className="text-xs px-3 py-1.5 rounded-full bg-glass-100 text-white/60 hover:text-white hover:bg-glass-200 transition-colors"
                        type="button"
                    >
                        {suggestion.label}
                    </button>
                ))}
            </div>

            {/* Messages */}
            <div
                ref={scrollRef}
                className="flex-1 overflow-y-auto p-4 space-y-4"
                data-testid="chat-messages"
            >
                {messages.map((message) => (
                    <div
                        key={message.id}
                        className={`flex ${message.role === "user" ? "justify-end" : "justify-start"}`}
                        data-testid={`message-${message.id}`}
                        data-role={message.role}
                    >
                        <div
                            className={`max-w-[80%] rounded-2xl px-4 py-3 ${message.role === "user"
                                ? "bg-cyber-blue/20 text-white"
                                : "bg-glass-200 text-white/90"
                                }`}
                        >
                            <p className="text-sm whitespace-pre-wrap">{message.content}</p>
                            <p className="text-xs text-white/40 mt-1">
                                {message.timestamp ? (
                                    <FormattedTime date={message.timestamp} />
                                ) : (
                                    <span className="opacity-50" data-testid="chat-timestamp-placeholder">--:--</span>
                                )}
                            </p>
                        </div>
                    </div>
                ))}

                {isLoading && (
                    <div className="flex justify-start" data-testid="loading-indicator">
                        <div className="bg-glass-200 rounded-2xl px-4 py-3">
                            <div className="flex items-center gap-2">
                                <div className="w-2 h-2 bg-cyber-blue rounded-full animate-pulse" />
                                <div className="w-2 h-2 bg-cyber-blue rounded-full animate-pulse delay-75" />
                                <div className="w-2 h-2 bg-cyber-blue rounded-full animate-pulse delay-150" />
                            </div>
                        </div>
                    </div>
                )}
            </div>

            {/* Input */}
            <div className="p-4 border-t border-glass">
                <div className="flex gap-3">
                    <textarea
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onKeyDown={handleKeyDown}
                        placeholder="Ask about your documents..."
                        className="glass-input resize-none"
                        rows={1}
                        data-testid="chat-input"
                    />
                    <button
                        onClick={handleSend}
                        disabled={!input.trim() || isLoading}
                        className="glass-button px-6 disabled:opacity-50 disabled:cursor-not-allowed hover:shadow-glow"
                        data-testid="send-button"
                    >
                        <svg
                            className="w-5 h-5 text-cyber-blue"
                            fill="none"
                            stroke="currentColor"
                            viewBox="0 0 24 24"
                        >
                            <path
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                strokeWidth={2}
                                d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"
                            />
                        </svg>
                    </button>
                </div>

                {/* Quick actions */}
                <div className="flex gap-2 mt-3" data-testid="chat-quick-actions">
                    <button
                        className="text-xs px-3 py-1.5 rounded-full bg-glass-100 text-white/60 hover:text-white hover:bg-glass-200 transition-colors"
                        data-testid="quick-action-podcast"
                        onClick={() => handleQuickAction("podcast")}
                    >
                        🎙️ Generate Podcast
                    </button>
                    <button
                        className="text-xs px-3 py-1.5 rounded-full bg-glass-100 text-white/60 hover:text-white hover:bg-glass-200 transition-colors"
                        data-testid="quick-action-summarize"
                        onClick={() => handleQuickAction("summarize")}
                    >
                        📝 Summarize All
                    </button>
                    <button
                        className="text-xs px-3 py-1.5 rounded-full bg-glass-100 text-white/60 hover:text-white hover:bg-glass-200 transition-colors"
                        data-testid="quick-action-deepdive"
                        onClick={() => handleQuickAction("deep-dive")}
                    >
                        🔍 Deep Dive
                    </button>
                </div>
            </div>
        </div>
    );
}
