"use client";

/**
 * Chat Panel - Center cognitive stream interface
 */

import { useState, useRef, useEffect } from "react";
import { useFocusedNode } from "@/store/graphStore";

interface Message {
    id: string;
    role: "user" | "assistant";
    content: string;
    timestamp: Date;
}

// Sample messages for development
const SAMPLE_MESSAGES: Message[] = [
    {
        id: "1",
        role: "assistant",
        content: "Welcome to the Sovereign Cognitive Engine. Upload documents to build your knowledge graph, then ask questions or generate podcast episodes.",
        timestamp: new Date(),
    },
];

export function ChatPanel() {
    const [messages, setMessages] = useState<Message[]>(SAMPLE_MESSAGES);
    const [input, setInput] = useState("");
    const [isLoading, setIsLoading] = useState(false);
    const scrollRef = useRef<HTMLDivElement>(null);
    const focusedNode = useFocusedNode();

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
        setInput("");
        setIsLoading(true);

        // Simulate AI response (replace with actual API call)
        setTimeout(() => {
            const assistantMessage: Message = {
                id: (Date.now() + 1).toString(),
                role: "assistant",
                content: `I understand you're asking about "${input}". This is a placeholder response. In production, this would query the knowledge graph and generate a contextual answer.`,
                timestamp: new Date(),
            };
            setMessages((prev) => [...prev, assistantMessage]);
            setIsLoading(false);
        }, 1500);
    };

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    };

    return (
        <div className="flex flex-col h-full">
            {/* Header */}
            <div className="panel-header flex items-center justify-between">
                <span>Cognitive Stream</span>
                {focusedNode && (
                    <span className="text-xs text-cyber-blue">
                        Context: {focusedNode.name}
                    </span>
                )}
            </div>

            {/* Messages */}
            <div
                ref={scrollRef}
                className="flex-1 overflow-y-auto p-4 space-y-4"
            >
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
                                {message.timestamp.toLocaleTimeString()}
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
                <div className="flex gap-2 mt-3">
                    <button className="text-xs px-3 py-1.5 rounded-full bg-glass-100 text-white/60 hover:text-white hover:bg-glass-200 transition-colors">
                        🎙️ Generate Podcast
                    </button>
                    <button className="text-xs px-3 py-1.5 rounded-full bg-glass-100 text-white/60 hover:text-white hover:bg-glass-200 transition-colors">
                        📝 Summarize All
                    </button>
                    <button className="text-xs px-3 py-1.5 rounded-full bg-glass-100 text-white/60 hover:text-white hover:bg-glass-200 transition-colors">
                        🔍 Deep Dive
                    </button>
                </div>
            </div>
        </div>
    );
}
