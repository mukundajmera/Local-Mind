"use client";

/**
 * Sovereign Cognitive Engine - Audio Waveform Visualizer
 * =======================================================
 * Real-time frequency visualization using Web Audio API AnalyserNode.
 * Lightweight canvas-based implementation without heavy libraries.
 */

import { useRef, useEffect, useCallback } from "react";
import { useAudioStore, useIsPlaying } from "@/store/audioStore";

interface WaveformProps {
    height?: number;
    barWidth?: number;
    barGap?: number;
    primaryColor?: string;
    secondaryColor?: string;
}

export function Waveform({
    height = 64,
    barWidth = 3,
    barGap = 1,
    primaryColor = "#00d4ff",
    secondaryColor = "#a855f7",
}: WaveformProps) {
    const canvasRef = useRef<HTMLCanvasElement>(null);
    const animationRef = useRef<number>(0);
    const analyserRef = useRef<AnalyserNode | null>(null);
    const audioContextRef = useRef<AudioContext | null>(null);
    const sourceRef = useRef<MediaElementAudioSourceNode | null>(null);

    const isPlaying = useIsPlaying();
    const currentTrack = useAudioStore((s) => s.currentTrack);

    // Initialize Web Audio API
    const initAudio = useCallback((audioElement: HTMLAudioElement) => {
        // Create audio context if not exists
        if (!audioContextRef.current) {
            audioContextRef.current = new (window.AudioContext || (window as any).webkitAudioContext)();
        }

        const audioContext = audioContextRef.current;

        // Create analyser
        if (!analyserRef.current) {
            analyserRef.current = audioContext.createAnalyser();
            analyserRef.current.fftSize = 128; // 64 frequency bins
            analyserRef.current.smoothingTimeConstant = 0.8;
        }

        // Create source from audio element if not exists
        if (!sourceRef.current) {
            try {
                sourceRef.current = audioContext.createMediaElementSource(audioElement);
                sourceRef.current.connect(analyserRef.current);
                analyserRef.current.connect(audioContext.destination);
            } catch (e) {
                // Source already created for this element
                console.log("[Waveform] Audio source already connected");
            }
        }

        // Resume context if suspended
        if (audioContext.state === "suspended") {
            audioContext.resume();
        }
    }, []);

    // Draw waveform
    const draw = useCallback(() => {
        const canvas = canvasRef.current;
        const analyser = analyserRef.current;

        if (!canvas || !analyser) {
            animationRef.current = requestAnimationFrame(draw);
            return;
        }

        const ctx = canvas.getContext("2d");
        if (!ctx) return;

        const bufferLength = analyser.frequencyBinCount;
        const dataArray = new Uint8Array(bufferLength);
        analyser.getByteFrequencyData(dataArray);

        // Clear canvas
        ctx.clearRect(0, 0, canvas.width, canvas.height);

        // Calculate bar dimensions
        const totalBarWidth = barWidth + barGap;
        const barCount = Math.floor(canvas.width / totalBarWidth);
        const centerY = canvas.height / 2;

        // Create gradient
        const gradient = ctx.createLinearGradient(0, 0, canvas.width, 0);
        gradient.addColorStop(0, primaryColor);
        gradient.addColorStop(0.5, secondaryColor);
        gradient.addColorStop(1, primaryColor);

        ctx.fillStyle = gradient;

        // Draw bars (mirrored top and bottom)
        for (let i = 0; i < barCount; i++) {
            // Map bar index to frequency bin
            const dataIndex = Math.floor((i / barCount) * bufferLength);
            const value = dataArray[dataIndex] || 0;

            // Calculate bar height (normalized)
            const barHeight = (value / 255) * (canvas.height / 2);

            const x = i * totalBarWidth;

            // Draw top bar
            ctx.fillRect(x, centerY - barHeight, barWidth, barHeight);

            // Draw bottom bar (mirrored)
            ctx.fillRect(x, centerY, barWidth, barHeight);
        }

        animationRef.current = requestAnimationFrame(draw);
    }, [barWidth, barGap, primaryColor, secondaryColor]);

    // Find audio element and connect
    useEffect(() => {
        // Look for audio element in the DOM (from AudioPanel)
        const findAndConnectAudio = () => {
            const audioElement = document.querySelector("audio") as HTMLAudioElement;
            if (audioElement && currentTrack) {
                initAudio(audioElement);
            }
        };

        // Retry a few times as audio element might not be ready
        const retryInterval = setInterval(findAndConnectAudio, 500);
        findAndConnectAudio();

        return () => clearInterval(retryInterval);
    }, [currentTrack, initAudio]);

    // Animation loop
    useEffect(() => {
        if (isPlaying) {
            animationRef.current = requestAnimationFrame(draw);
        } else {
            cancelAnimationFrame(animationRef.current);

            // Draw idle state
            const canvas = canvasRef.current;
            if (canvas) {
                const ctx = canvas.getContext("2d");
                if (ctx) {
                    ctx.clearRect(0, 0, canvas.width, canvas.height);

                    // Draw flat line when paused
                    const centerY = canvas.height / 2;
                    ctx.fillStyle = `${primaryColor}40`;
                    ctx.fillRect(0, centerY - 1, canvas.width, 2);
                }
            }
        }

        return () => cancelAnimationFrame(animationRef.current);
    }, [isPlaying, draw, primaryColor]);

    // Handle resize
    useEffect(() => {
        const canvas = canvasRef.current;
        if (!canvas) return;

        const resizeObserver = new ResizeObserver((entries) => {
            for (const entry of entries) {
                canvas.width = entry.contentRect.width;
                canvas.height = entry.contentRect.height;
            }
        });

        resizeObserver.observe(canvas.parentElement!);

        return () => resizeObserver.disconnect();
    }, []);

    return (
        <div className="w-full relative" style={{ height }}>
            <canvas
                ref={canvasRef}
                className="w-full h-full"
                style={{
                    background: "transparent",
                    borderRadius: "8px",
                }}
            />

            {/* Idle state overlay */}
            {!isPlaying && !currentTrack && (
                <div className="absolute inset-0 flex items-center justify-center">
                    <span className="text-xs text-white/30">No audio playing</span>
                </div>
            )}
        </div>
    );
}

// Static waveform for decoration (doesn't need audio)
export function StaticWaveform({ barCount = 40 }: { barCount?: number }) {
    return (
        <div className="flex items-center justify-center gap-px h-16">
            {Array.from({ length: barCount }).map((_, i) => {
                // Create a pleasing wave pattern
                const height = Math.sin((i / barCount) * Math.PI * 2 + Math.random()) * 0.5 + 0.5;
                return (
                    <div
                        key={i}
                        className="w-1 rounded-full bg-gradient-to-t from-cyber-blue/30 to-cyber-purple/30"
                        style={{
                            height: `${height * 100}%`,
                            animationDelay: `${i * 50}ms`,
                        }}
                    />
                );
            })}
        </div>
    );
}
