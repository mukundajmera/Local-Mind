"use client";

/**
 * Audio Panel - Right sidebar with podcast player and controls
 */

import { useEffect, useRef } from "react";
import { useAudioStore, useCurrentTrack, useIsPlaying, useVolume, useQueue } from "@/store/audioStore";

export function AudioPanel() {
    const audioRef = useRef<HTMLAudioElement>(null);

    const currentTrack = useCurrentTrack();
    const isPlaying = useIsPlaying();
    const volume = useVolume();
    const queue = useQueue();

    const {
        play,
        pause,
        toggle,
        setVolume,
        setProgress,
        setDuration,
        playNext,
        clearQueue,
    } = useAudioStore();

    // Sync audio element with store state
    useEffect(() => {
        const audio = audioRef.current;
        if (!audio) return;

        if (isPlaying && currentTrack) {
            audio.play().catch(console.error);
        } else {
            audio.pause();
        }
    }, [isPlaying, currentTrack]);

    // Volume sync
    useEffect(() => {
        if (audioRef.current) {
            audioRef.current.volume = volume;
        }
    }, [volume]);

    // Handle track end - play next (gapless)
    const handleEnded = () => {
        playNext();
    };

    // Progress updates
    const handleTimeUpdate = () => {
        const audio = audioRef.current;
        if (!audio || !audio.duration) return;

        const progress = (audio.currentTime / audio.duration) * 100;
        setProgress(progress);
    };

    const handleLoadedMetadata = () => {
        if (audioRef.current) {
            setDuration(audioRef.current.duration);
        }
    };

    // Seek
    const handleSeek = (e: React.ChangeEvent<HTMLInputElement>) => {
        const audio = audioRef.current;
        if (!audio || !audio.duration) return;

        const newProgress = parseFloat(e.target.value);
        audio.currentTime = (newProgress / 100) * audio.duration;
        setProgress(newProgress);
    };

    const progress = useAudioStore((s) => s.progress);
    const duration = useAudioStore((s) => s.duration);

    const formatTime = (seconds: number) => {
        const mins = Math.floor(seconds / 60);
        const secs = Math.floor(seconds % 60);
        return `${mins}:${secs.toString().padStart(2, "0")}`;
    };

    return (
        <div className="flex flex-col h-full">
            {/* Hidden audio element */}
            <audio
                ref={audioRef}
                src={currentTrack?.url}
                onEnded={handleEnded}
                onTimeUpdate={handleTimeUpdate}
                onLoadedMetadata={handleLoadedMetadata}
            />

            {/* Header */}
            <div className="panel-header">Acoustic Control</div>

            {/* Now Playing */}
            <div className="p-4 border-b border-glass">
                <div className="text-xs text-white/50 mb-1">Now Playing</div>
                {currentTrack ? (
                    <>
                        <div className="text-sm font-medium text-white truncate">
                            {currentTrack.title}
                        </div>
                        {currentTrack.speaker && (
                            <div className="text-xs text-cyber-blue">
                                {currentTrack.speaker}
                            </div>
                        )}
                    </>
                ) : (
                    <div className="text-sm text-white/40">No track selected</div>
                )}

                {/* Waveform placeholder */}
                <div className="waveform-container mt-3">
                    <div
                        className="h-full bg-gradient-to-r from-cyber-blue/30 to-cyber-purple/30"
                        style={{ width: `${progress}%` }}
                    />
                </div>

                {/* Progress bar */}
                <input
                    type="range"
                    min="0"
                    max="100"
                    value={progress}
                    onChange={handleSeek}
                    className="w-full h-1 mt-2 appearance-none bg-glass-200 rounded-full cursor-pointer
            [&::-webkit-slider-thumb]:appearance-none
            [&::-webkit-slider-thumb]:w-3
            [&::-webkit-slider-thumb]:h-3
            [&::-webkit-slider-thumb]:bg-cyber-blue
            [&::-webkit-slider-thumb]:rounded-full
            [&::-webkit-slider-thumb]:cursor-pointer"
                />

                {/* Time display */}
                <div className="flex justify-between text-xs text-white/50 mt-1">
                    <span>{formatTime((progress / 100) * duration)}</span>
                    <span>{formatTime(duration)}</span>
                </div>
            </div>

            {/* Controls */}
            <div className="p-4 flex items-center justify-center gap-4">
                {/* Skip back */}
                <button className="p-2 text-white/60 hover:text-white transition-colors">
                    <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
                        <path d="M6 6h2v12H6zm3.5 6l8.5 6V6z" />
                    </svg>
                </button>

                {/* Play/Pause */}
                <button
                    onClick={toggle}
                    className="p-4 rounded-full bg-cyber-blue/20 text-cyber-blue hover:bg-cyber-blue/30 transition-colors"
                >
                    {isPlaying ? (
                        <svg className="w-6 h-6" fill="currentColor" viewBox="0 0 24 24">
                            <path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z" />
                        </svg>
                    ) : (
                        <svg className="w-6 h-6" fill="currentColor" viewBox="0 0 24 24">
                            <path d="M8 5v14l11-7z" />
                        </svg>
                    )}
                </button>

                {/* Skip forward */}
                <button className="p-2 text-white/60 hover:text-white transition-colors">
                    <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
                        <path d="M6 18l8.5-6L6 6v12zM16 6v12h2V6h-2z" />
                    </svg>
                </button>
            </div>

            {/* Volume */}
            <div className="px-4 pb-4 flex items-center gap-3">
                <svg className="w-4 h-4 text-white/50" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02z" />
                </svg>
                <input
                    type="range"
                    min="0"
                    max="100"
                    value={volume * 100}
                    onChange={(e) => setVolume(parseFloat(e.target.value) / 100)}
                    className="flex-1 h-1 appearance-none bg-glass-200 rounded-full cursor-pointer
            [&::-webkit-slider-thumb]:appearance-none
            [&::-webkit-slider-thumb]:w-3
            [&::-webkit-slider-thumb]:h-3
            [&::-webkit-slider-thumb]:bg-white
            [&::-webkit-slider-thumb]:rounded-full
            [&::-webkit-slider-thumb]:cursor-pointer"
                />
                <span className="text-xs text-white/50 w-8">
                    {Math.round(volume * 100)}%
                </span>
            </div>

            {/* Queue */}
            <div className="flex-1 border-t border-glass overflow-hidden flex flex-col">
                <div className="panel-header flex items-center justify-between">
                    <span>Up Next</span>
                    {queue.length > 0 && (
                        <button
                            onClick={clearQueue}
                            className="text-xs text-white/50 hover:text-white transition-colors"
                        >
                            Clear
                        </button>
                    )}
                </div>

                <div className="flex-1 overflow-y-auto p-2 space-y-1">
                    {queue.length === 0 ? (
                        <div className="text-sm text-white/40 text-center py-4">
                            Queue is empty
                        </div>
                    ) : (
                        queue.map((track, index) => (
                            <div
                                key={track.id}
                                className="flex items-center gap-2 p-2 rounded-lg hover:bg-glass-100 cursor-pointer transition-colors"
                            >
                                <span className="text-xs text-white/40 w-5">{index + 1}</span>
                                <div className="flex-1 min-w-0">
                                    <div className="text-sm text-white/80 truncate">
                                        {track.title}
                                    </div>
                                    {track.speaker && (
                                        <div className="text-xs text-white/50">{track.speaker}</div>
                                    )}
                                </div>
                            </div>
                        ))
                    )}
                </div>
            </div>
        </div>
    );
}
