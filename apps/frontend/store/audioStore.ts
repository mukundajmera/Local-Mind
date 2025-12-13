/**
 * Sovereign Cognitive Engine - Audio Store
 * =========================================
 * Zustand store for persistent audio playback state with gapless queue.
 */

import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";

interface AudioTrack {
    id: string;
    url: string;
    title: string;
    speaker?: string;
    duration?: number;
}

interface AudioState {
    // Playback state
    isPlaying: boolean;
    currentTrack: AudioTrack | null;
    volume: number;
    progress: number; // 0-100
    duration: number; // seconds

    // Gapless queue
    queue: AudioTrack[];

    // Actions
    play: () => void;
    pause: () => void;
    toggle: () => void;
    setVolume: (volume: number) => void;
    setProgress: (progress: number) => void;
    setDuration: (duration: number) => void;

    // Queue management
    setCurrentTrack: (track: AudioTrack) => void;
    addToQueue: (track: AudioTrack) => void;
    addManyToQueue: (tracks: AudioTrack[]) => void;
    clearQueue: () => void;
    playNext: () => void;
    skipTo: (index: number) => void;

    // Full reset
    reset: () => void;
}

const initialState = {
    isPlaying: false,
    currentTrack: null,
    volume: 0.7,
    progress: 0,
    duration: 0,
    queue: [],
};

/**
 * Audio store with localStorage persistence.
 * Persists: volume, currentTrack (for resume), queue
 * Does NOT persist: isPlaying, progress (user should re-play)
 */
export const useAudioStore = create<AudioState>()(
    persist(
        (set, get) => ({
            ...initialState,

            // Playback controls
            play: () => set({ isPlaying: true }),
            pause: () => set({ isPlaying: false }),
            toggle: () => set((state) => ({ isPlaying: !state.isPlaying })),

            setVolume: (volume) => set({ volume: Math.max(0, Math.min(1, volume)) }),
            setProgress: (progress) => set({ progress: Math.max(0, Math.min(100, progress)) }),
            setDuration: (duration) => set({ duration }),

            // Track management
            setCurrentTrack: (track) => set({
                currentTrack: track,
                progress: 0,
                isPlaying: true,
            }),

            // Queue operations
            addToQueue: (track) => set((state) => ({
                queue: [...state.queue, track],
            })),

            addManyToQueue: (tracks) => set((state) => ({
                queue: [...state.queue, ...tracks],
            })),

            clearQueue: () => set({ queue: [] }),

            /**
             * Play next track in queue (gapless transition).
             * Called automatically when current track ends.
             */
            playNext: () => {
                const { queue } = get();

                if (queue.length === 0) {
                    // Queue exhausted
                    set({
                        isPlaying: false,
                        currentTrack: null,
                        progress: 0,
                    });
                    return;
                }

                // Pop first item from queue
                const [nextTrack, ...remainingQueue] = queue;

                set({
                    currentTrack: nextTrack,
                    queue: remainingQueue,
                    progress: 0,
                    isPlaying: true,
                });
            },

            skipTo: (index) => {
                const { queue } = get();

                if (index < 0 || index >= queue.length) return;

                const track = queue[index];
                const newQueue = queue.filter((_, i) => i !== index);

                set({
                    currentTrack: track,
                    queue: newQueue,
                    progress: 0,
                    isPlaying: true,
                });
            },

            reset: () => set(initialState),
        }),
        {
            name: "sce-audio-store",
            storage: createJSONStorage(() => localStorage),
            // Only persist these fields
            partialize: (state) => ({
                volume: state.volume,
                currentTrack: state.currentTrack,
                queue: state.queue,
            }),
        }
    )
);

// Selector hooks for common patterns
export const useIsPlaying = () => useAudioStore((state) => state.isPlaying);
export const useCurrentTrack = () => useAudioStore((state) => state.currentTrack);
export const useVolume = () => useAudioStore((state) => state.volume);
export const useQueue = () => useAudioStore((state) => state.queue);
