"use client";

/**
 * Chat Panel - Clean conversational interface
 */

import { useState, useRef, useEffect } from "react";
import { useWorkspaceStore } from "@/store/workspaceStore";

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
    const { activeSourceId, sources, setViewMode } = useWorkspaceStore();

    const activeSource = sources.find(s => s.id === activeSourceId);

    // Auto-scroll to bottom
    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [messages]);

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
            const response = await fetch("http://localhost:8000/api/v1/chat", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    message: userInput,
                    context_node_ids: [],
                    strategies: ["sources"],
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
            console.error("Chat error:", error);
            const errorMessage: Message = {
                id: (Date.now() + 1).toString(),
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

    return (
        <div className="flex flex-col h-full" data-testid="chat-panel">
            {/* Header */}
            <div className="panel-header flex items-center justify-between">
                <div className="flex items-center gap-3">
                    <button
                        onClick={() => setViewMode("guide")}
                        className="text-white/60 hover:text-white transition-colors"
                        title="Back to guide"
                    >
                        ←
                    </button>
                    <span>Chat</span>
                </div>
                {activeSource && (
                    <span className="text-xs text-cyber-blue truncate max-w-[200px]">
                        {activeSource.title}
                    </span>
                )}
            </div>

            {/* Suggestions */}
            <div className="px-4 py-3 border-b border-glass flex flex-wrap gap-2">
                {PROMPT_SUGGESTIONS.map((s) => (
                    <button
                        key={s.id}
                        onClick={() => handleSuggestion(s.prompt)}
                        className="text-xs px-3 py-1.5 rounded-full bg-glass-100 text-white/60 hover:text-white hover:bg-glass-200 transition-colors"
                    >
                        {s.label}
                    </button>
                ))}
            </div>

            {/* Messages */}
            <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 space-y-4">
                {messages.map((message) => (
                    <div
                        key={message.id}
                        className={`flex ${message.role === "user" ? "justify-end" : "justify-start"}`}
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
                                    <span className="opacity-50">--:--</span>
                                )}
                            </p>
                        </div>
                    </div>
                ))}

                {isLoading && (
                    <div className="flex justify-start">
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
                    />
                    <button
                        onClick={handleSend}
                        disabled={!input.trim() || isLoading}
                        className="glass-button px-6 disabled:opacity-50 disabled:cursor-not-allowed hover:shadow-glow"
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
