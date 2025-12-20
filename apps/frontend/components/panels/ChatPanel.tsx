"use client";

/**
 * Chat Panel - Clean conversational interface with message pinning
 */

import { useState, useRef, useEffect } from "react";
import { useWorkspaceStore } from "@/store/workspaceStore";
import { API_BASE_URL } from "@/lib/api";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

const PROMPT_SUGGESTIONS = [
    {
        id: "summary",
        label: "📝 Summarize",
        prompt: "Summarize the key points from this document.",
    },
    {
        id: "questions",
        label: "❓ Key Questions",
        prompt: "What are the most important questions this document raises?",
    },
    {
        id: "compare",
        label: "🔍 Deep Dive",
        prompt: "Provide a detailed analysis of the main arguments.",
    },
] as const;

interface Message {
    id: string;
    role: "user" | "assistant";
    content: string;
    timestamp: Date | null;
    isPinned?: boolean;
}

/**
 * Client-only timestamp to prevent hydration mismatch.
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
        content: "Hello! I'm ready to help you explore your documents. Ask me anything about the sources you've uploaded.",
        timestamp: null,
    },
];

export function ChatPanel() {
    const [messages, setMessages] = useState<Message[]>(INITIAL_MESSAGES);
    const [input, setInput] = useState("");
    const [isLoading, setIsLoading] = useState(false);
    const scrollRef = useRef<HTMLDivElement>(null);
    const { activeSourceId, sources, selectedSourceIds, setViewMode, pinMessage, pendingChatInput, setPendingChatInput } = useWorkspaceStore();

    // Explicit reference to handleSend for the useEffect to call it
    // We need to use a ref to avoid circular dependency in useEffect
    const handleSendRef = useRef<() => void>(() => { });

    const activeSource = sources.find(s => s.id === activeSourceId);
    const selectedSources = sources.filter(s => selectedSourceIds.includes(s.id));

    // Auto-scroll to bottom
    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [messages]);

    // Handle pending input (auto-send)
    useEffect(() => {
        if (pendingChatInput) {
            const content = pendingChatInput; // Capture it
            setPendingChatInput(null); // Clear it
            handleSend(content);
        }
    }, [pendingChatInput, setPendingChatInput]);

    const handleSend = async (contentOverride?: string) => {
        // Determine what content to send
        const contentToSend = typeof contentOverride === 'string' ? contentOverride : input;

        if (!contentToSend.trim() || isLoading) return;

        const userMessage: Message = {
            id: crypto.randomUUID(),
            role: "user",
            content: contentToSend,
            timestamp: new Date(),
        };

        setMessages((prev) => [...prev, userMessage]);
        // Only clear input if we sent what was in the input box
        if (contentToSend === input) {
            setInput("");
        }
        setIsLoading(true);

        try {
            const response = await fetch(`${API_BASE_URL}/api/v1/chat`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    message: contentToSend,
                    source_ids: selectedSourceIds.length > 0 ? selectedSourceIds : null,
                    strategies: selectedSourceIds.length > 0 ? ["sources"] : [],
                }),
            });

            if (!response.ok) {
                const error = await response.json().catch(() => ({ detail: "Unknown error" }));
                throw new Error(error.detail || `HTTP ${response.status}`);
            }

            const data = await response.json();

            const assistantMessage: Message = {
                id: crypto.randomUUID(),
                role: "assistant",
                content: data.response,
                timestamp: new Date(),
            };
            setMessages((prev) => [...prev, assistantMessage]);
        } catch (error) {
            console.error("Chat error:", error);
            const errorMessage: Message = {
                id: crypto.randomUUID(),
                role: "assistant",
                content: `⚠️ Error: ${error instanceof Error ? error.message : "Failed to connect"}. Please ensure the backend is running.`,
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

    const handleSuggestion = (prompt: string) => {
        setInput(prompt);
    };

    const handlePinMessage = (message: Message) => {
        // Toggle pin state locally
        setMessages((prev) =>
            prev.map((m) =>
                m.id === message.id ? { ...m, isPinned: !m.isPinned } : m
            )
        );

        // Add to pinned messages store if pinning (not unpinning)
        if (!message.isPinned) {
            pinMessage({
                id: message.id,
                content: message.content,
                pinnedAt: new Date(),
            });
        }
    };

    return (
        <div className="flex flex-col h-full" data-testid="chat-panel">
            {/* Header */}
            <div className="panel-header flex items-center justify-between" data-testid="chat-header">
                <div className="flex items-center gap-3">
                    <button
                        onClick={() => setViewMode("guide")}
                        className="theme-text-muted hover:text-white transition-colors"
                        title="Back to guide"
                    >
                        ←
                    </button>
                    <span>Chat</span>
                </div>
                <div className="flex items-center gap-2">
                    {selectedSources.length > 0 && (
                        <span className="text-xs theme-text-faint">
                            {selectedSources.length} source{selectedSources.length > 1 ? 's' : ''} selected
                        </span>
                    )}
                    {activeSource && (
                        <span className="text-xs text-cyber-blue truncate max-w-[200px]">
                            {activeSource.title}
                        </span>
                    )}
                </div>
            </div>

            {/* Suggestions */}
            <div className="px-4 py-3 border-b border-glass flex flex-wrap gap-2">
                {PROMPT_SUGGESTIONS.map((s) => (
                    <button
                        key={s.id}
                        onClick={() => handleSuggestion(s.prompt)}
                        className="text-xs px-3 py-1.5 rounded-full bg-glass-100 theme-text-muted hover:text-white hover:bg-glass-200 transition-colors"
                        data-testid={`quick-action-${s.id}`}
                    >
                        {s.label}
                    </button>
                ))}
            </div>

            {/* Messages */}
            <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 space-y-4" data-testid="chat-messages">
                {messages.map((message) => (
                    <div
                        key={message.id}
                        className={`flex ${message.role === "user" ? "justify-end" : "justify-start"}`}
                        data-testid={`message-${message.id}`}
                        data-role={message.role}
                    >
                        <div
                            className={`message-bubble ${message.role === "user"
                                ? "message-bubble-user"
                                : "message-bubble-ai"
                                }`}
                        >
                            {message.role === "assistant" ? (
                                <div className="text-sm prose prose-invert prose-sm max-w-none">
                                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                                        {message.content}
                                    </ReactMarkdown>
                                </div>
                            ) : (
                                <p className="text-sm whitespace-pre-wrap">{message.content}</p>
                            )}
                            <div className="flex items-center justify-between mt-2">
                                <span className="text-xs theme-text-faint">
                                    {message.timestamp ? (
                                        <FormattedTime date={message.timestamp} />
                                    ) : (
                                        <span className="opacity-50">--:--</span>
                                    )}
                                </span>

                                {/* Pin button for AI messages */}
                                {message.role === "assistant" && message.id !== "welcome" && (
                                    <button
                                        onClick={() => handlePinMessage(message)}
                                        className={`pin-button ${message.isPinned ? 'pinned' : ''}`}
                                        title={message.isPinned ? "Unpin from notes" : "Pin to notes"}
                                        data-testid={`pin-btn-${message.id}`}
                                    >
                                        📌
                                    </button>
                                )}
                            </div>
                        </div>
                    </div>
                ))}

                {isLoading && (
                    <div className="flex justify-start" data-testid="loading-indicator">
                        <div className="message-bubble message-bubble-ai">
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
                        onClick={() => handleSend()}
                        disabled={!input.trim() || isLoading}
                        className="glass-button px-6 disabled:opacity-50 disabled:cursor-not-allowed hover:shadow-glow"
                        data-testid="send-button"
                    >
                        <svg className="w-5 h-5 text-cyber-blue" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                        </svg>
                    </button>
                </div>
            </div>
        </div>
    );
}

