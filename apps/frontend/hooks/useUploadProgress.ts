import { useState, useEffect, useCallback } from "react";
import type { UploadStatusResponse } from "@/types/api";

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
            const response = await fetch(`http://localhost:8000/api/v1/upload/${taskId}/status`);

            if (!response.ok) {
                throw new Error(`Failed to fetch status: ${response.status}`);
            }

            const data: UploadStatusResponse = await response.json();

            setProgress(data.progress);

            switch (data.status) {
                case "processing":
                    setStatus("processing");
                    break;
                case "completed":
                    setStatus("completed");
                    setDocId(data.doc_id || null);
                    break;
                case "failed":
                    setStatus("failed");
                    setError(data.error || "Upload failed");
                    break;
            }
        } catch (err) {
            console.error("Failed to poll upload status:", err);
            setError(err instanceof Error ? err.message : "Unknown error");
            setStatus("failed");
        }
    }, [taskId]);

    useEffect(() => {
        if (!taskId) {
            setStatus("idle");
            setProgress(0);
            setError(null);
            setDocId(null);
            return;
        }

        setStatus("uploading");
        setProgress(10);

        // Poll every 500ms until completed or failed
        const interval = setInterval(() => {
            if (status === "completed" || status === "failed") {
                clearInterval(interval);
                return;
            }
            pollStatus();
        }, 500);

        // Initial poll
        pollStatus();

        return () => clearInterval(interval);
    }, [taskId, pollStatus, status]);

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
