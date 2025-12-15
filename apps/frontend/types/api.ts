/**
 * API Type Definitions for Local-Mind Frontend
 * 
 * These interfaces enforce type safety at the frontend-backend boundary.
 */

// =============================================================================
// Chat API Types
// =============================================================================

/**
 * Request payload for chat endpoint.
 * Maps to backend schemas.ChatRequest
 */
export interface ChatRequest {
    /** User's query or message */
    message: string;
    
    /** 
     * Document IDs to filter search. 
     * null = search all documents 
     */
    source_ids: string[] | null;
    
    /** Search strategies to use (e.g., ["sources"]) */
    strategies: string[];
}

/**
 * Citation source returned with chat response
 */
export interface ChatCitation {
    id: string;
    score: number;
    source: string;
    doc_id?: string;
}

/**
 * Response from chat endpoint.
 * Maps to backend response in main.py chat()
 */
export interface ChatResponse {
    /** AI-generated response text */
    response: string;
    
    /** Source citations with relevance scores */
    sources: ChatCitation[];
    
    /** Whether context was used for generation */
    context_used: boolean;
    
    /** Whether results were filtered to specific sources */
    filtered_sources: boolean;
}

// =============================================================================
// Upload API Types
// =============================================================================

/**
 * Response when upload is accepted for processing
 */
export interface UploadAcceptedResponse {
    task_id: string;
    status: "accepted";
}

/**
 * Status of an upload task
 */
export interface UploadStatusResponse {
    status: "processing" | "completed" | "failed";
    progress: number;
    doc_id?: string;
    error?: string;
}

/**
 * Successful upload completion details
 */
export interface UploadCompletedResponse {
    status: "success";
    doc_id: string;
    filename: string;
    chunks_created: number;
    entities_extracted: number;
    briefing_status: string;
}

// =============================================================================
// Source API Types
// =============================================================================

/**
 * Document source metadata
 */
export interface Source {
    id: string;
    title: string;
    status: "ready" | "processing" | "failed";
    upload_date?: string;
    file_size_bytes?: number;
}

/**
 * Source briefing/guide data
 */
export interface SourceBriefing {
    summary: string;
    key_topics: string[];
    suggested_questions: string[];
    doc_id: string;
    generated_at: string;
}
