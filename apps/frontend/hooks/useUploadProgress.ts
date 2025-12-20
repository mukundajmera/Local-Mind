import { useState, useEffect, useCallback } from "react";
import type { UploadStatusResponse } from "@/types/api";
import { API_BASE_URL } from "@/lib/api";

/**
 * Hook to poll upload task status and track progress.
 * 
 * @param taskId - The upload task ID returned from POST /api/v1/sources/upload
 * @returns Status information including progress percentage
 */
export function useUploadProgress(taskId: string | null) {
    const [status, setStatus] = useState<"idle" | "uploading" | "processing" | "completed" | "failed">("idle");
    const [progress, setProgress] = useState(0);
    const [error, setError] = useState<string | null>(null);
    const [docId, setDocId] = useState<string | null>(null);

    const pollStatus = useCallback(async () => {
        if (!taskId) return;

        try {
            // Correct endpoint matches backend routers/ingestion.py
            const response = await fetch(`${API_BASE_URL}/api/v1/sources/${taskId}/status`);

            if (!response.ok) {
                throw new Error(`Failed to fetch status: ${response.status}`);
            }

            const data = await response.json();

            // Backend returns: id, status (pending|processing|ready|failed), error_message
            // Frontend expects: status (processing|completed|failed), progress

            // Map backend status to frontend status
            let normalizedStatus = data.status;
            if (data.status === 'ready') {
                normalizedStatus = 'completed';
                setProgress(100);
            } else if (data.status === 'processing') {
                // Fake progress since backend doesn't provide it yet
                setProgress((prev) => Math.min(prev + 10, 90));
            } else if (data.status === 'pending') {
                normalizedStatus = 'processing'; // Treat pending as processing in UI
                setProgress(20);
            }

            switch (normalizedStatus) {
                case "processing":
                    setStatus("processing");
                    break;
                case "completed":
                    setStatus("completed");
                    setDocId(data.id); // Backend uses 'id'
                    break;
                case "failed":
                    setStatus("failed");
                    setError(data.error_message || "Upload failed");
                    break;
            }
        } catch (err) {
            console.error("Failed to poll upload status:", err);
            setError(err instanceof Error ? err.message : "Unknown error");
            setStatus("failed");
        }
    }, [taskId]);

    // Reset/Init state when taskId changes
    useEffect(() => {
        if (taskId) {
            setStatus("uploading");
            setProgress(10);
            setError(null);
            setDocId(null);
        } else {
            setStatus("idle");
            setProgress(0);
            setError(null);
            setDocId(null);
        }
    }, [taskId]);

    // Polling logic
    useEffect(() => {
        if (!taskId || status === "completed" || status === "failed" || status === "idle") {
            return;
        }

        // Poll every 500ms
        const interval = setInterval(() => {
            pollStatus();
        }, 500);

        // Initial poll immediately
        pollStatus();

        return () => clearInterval(interval);
    }, [taskId, status, pollStatus]);

    const reset = useCallback(() => {
        setStatus("idle");
        setProgress(0);
        setError(null);
        setDocId(null);
    }, []);

    return {
        status,
        progress,
        error,
        docId,
        isUploading: status === "uploading" || status === "processing",
        isComplete: status === "completed",
        isFailed: status === "failed",
        reset,
    };
}
