"use client";

import { useState, useRef, useEffect } from "react";
import { UploadCloud, X, FileText, Loader2, CheckCircle } from "lucide-react";
import { useWorkspaceStore } from "@/store/workspaceStore";
import { useUploadProgress } from "@/hooks/useUploadProgress";
import { API_BASE_URL } from "@/lib/api";

interface UploadProps {
    onUploadComplete?: (docId?: string) => void;
}

export function Upload({ onUploadComplete }: UploadProps) {
    const { currentProjectId } = useWorkspaceStore();
    const fileInputRef = useRef<HTMLInputElement>(null);

    // State
    const [file, setFile] = useState<File | null>(null);
    const [uploadProgress, setUploadProgress] = useState(0); // 0-100 for XHR upload
    const [taskId, setTaskId] = useState<string | null>(null);
    const [xhrError, setXhrError] = useState<string | null>(null);

    // Hook for backend processing status (after upload)
    const {
        status: processingStatus,
        progress: processingProgress,
        isComplete,
        isFailed: isProcessingFailed,
        error: processingError,
        reset: resetProcessing
    } = useUploadProgress(taskId);

    // Reset everything
    const reset = () => {
        setFile(null);
        setUploadProgress(0);
        setTaskId(null);
        setXhrError(null);
        resetProcessing();
        if (fileInputRef.current) fileInputRef.current.value = "";
    };

    // Auto-close/reset on completion after delay
    useEffect(() => {
        if (isComplete) {
            const t = setTimeout(() => {
                reset();
                // onUploadComplete already called immediately after upload
            }, 3000);
            return () => clearTimeout(t);
        }
    }, [isComplete]);

    const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files?.[0]) {
            setFile(e.target.files[0]);
            startUpload(e.target.files[0]);
        }
    };

    const startUpload = (selectedFile: File) => {
        setUploadProgress(0);
        setXhrError(null);

        const formData = new FormData();
        formData.append("file", selectedFile);

        // Add project_id if selected
        // Note: Query param or FormData? verification script used query param.
        // Let's use query param to match verification script success.
        let url = `${API_BASE_URL}/api/v1/sources/upload`;
        if (currentProjectId) {
            url += `?project_id=${currentProjectId}`;
        }

        const xhr = new XMLHttpRequest();
        xhr.open("POST", url, true);

        xhr.upload.onprogress = (event) => {
            if (event.lengthComputable) {
                const percent = Math.round((event.loaded / event.total) * 100);
                setUploadProgress(percent);
            }
        };

        xhr.onload = () => {
            if (xhr.status === 202) {
                const response = JSON.parse(xhr.responseText);
                // New async backend returns { id, status, message }
                if (response.id) {
                    setTaskId(response.id);
                    // Immediately notify parent to start polling
                    onUploadComplete?.(response.id);
                } else if (response.task_id) {
                    // Fallback for old format
                    setTaskId(response.task_id);
                    onUploadComplete?.(response.task_id);
                }
            } else {
                setXhrError(`Upload failed: ${xhr.statusText}`);
            }
        };

        xhr.onerror = () => {
            setXhrError("Network error occurred during upload.");
        };

        xhr.send(formData);
    };

    // UI States
    const isUploading = uploadProgress > 0 && uploadProgress < 100 && !taskId;
    const isProcessing = !!taskId && !isComplete && !isProcessingFailed;
    const hasError = xhrError || isProcessingFailed;
    const errorMessage = xhrError || processingError;

    return (
        <div className="w-full">
            <input
                ref={fileInputRef}
                type="file"
                className="hidden"
                accept=".pdf,.txt,.md"
                onChange={handleFileSelect}
            />

            {!file ? (
                <button
                    onClick={() => currentProjectId && fileInputRef.current?.click()}
                    disabled={!currentProjectId}
                    className={`w-full h-24 border-2 border-dashed border-glass rounded-xl flex flex-col items-center justify-center gap-2 transition-all group ${!currentProjectId ? 'opacity-50 cursor-not-allowed' : 'hover:border-cyber-blue/50 hover:bg-glass-100'}`}
                >
                    <UploadCloud className={`w-8 h-8 transition-colors ${!currentProjectId ? 'text-gray-500' : 'text-cyber-blue/50 group-hover:text-cyber-blue'}`} />
                    <span className="text-sm theme-text-muted">
                        {!currentProjectId ? "Select a project to upload" : "Click to upload PDF/TXT"}
                    </span>
                </button>
            ) : (
                <div className="bg-glass-100 rounded-xl p-3 border border-glass relative overflow-hidden">
                    {/* Progress Background */}
                    {(isUploading || isProcessing) && (
                        <div
                            className="absolute bottom-0 left-0 top-0 bg-cyber-blue/5 transition-all duration-300"
                            style={{ width: isUploading ? `${uploadProgress}%` : `${processingProgress}%` }}
                        />
                    )}

                    <div className="relative flex items-center gap-3">
                        <div className="w-10 h-10 rounded-lg bg-cyber-purple/20 flex items-center justify-center shrink-0">
                            {isComplete ? (
                                <CheckCircle className="w-5 h-5 text-green-400" />
                            ) : hasError ? (
                                <X className="w-5 h-5 text-red-400" />
                            ) : (
                                <FileText className="w-5 h-5 text-cyber-purple" />
                            )}
                        </div>

                        <div className="flex-1 min-w-0">
                            <div className="flex justify-between items-center mb-1">
                                <span className="text-sm font-medium theme-text-primary truncate">{file.name}</span>
                                <span className="text-xs theme-text-muted">
                                    {isComplete && "Done"}
                                    {hasError && "Failed"}
                                    {isUploading && `${uploadProgress}%`}
                                    {isProcessing && `${processingProgress}%`}
                                </span>
                            </div>

                            {/* Status Text */}
                            <div className="text-xs theme-text-muted flex items-center gap-2">
                                {isUploading && "Uploading..."}
                                {isProcessing && (
                                    <>
                                        <Loader2 className="w-3 h-3 animate-spin" />
                                        Processing...
                                    </>
                                )}
                                {isComplete && <span className="text-green-400">Ready to chat</span>}
                                {hasError && <span className="text-red-400">{errorMessage}</span>}
                            </div>
                        </div>

                        {canCancel(!!hasError, isComplete) && (
                            <button onClick={reset} className="p-1 hover:bg-white/10 rounded">
                                <X className="w-4 h-4 theme-text-muted hover:text-white" />
                            </button>
                        )}
                    </div>
                </div>
            )}
        </div>
    );
}

function canCancel(hasError: boolean, isComplete: boolean) {
    return hasError || isComplete;
}
