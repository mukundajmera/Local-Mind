"""
Sovereign Cognitive Engine - Briefing Service
==============================================
Automated document summarization and briefing generation.
Uses in-memory storage (can be upgraded to Redis for persistence).
"""

import logging
from datetime import datetime
from typing import Optional

from config import Settings, get_settings
from schemas import BriefingResponse

logger = logging.getLogger(__name__)

# In-memory briefing cache (use Redis in production for persistence across restarts)
_briefing_cache: dict[str, BriefingResponse] = {}


class BriefingService:
    """
    Service for generating automated briefings after document upload.
    
    Generates:
    - Summary: 1-paragraph overview
    - Key topics: 5-7 bullet points
    - Suggested questions: 3 follow-up questions
    
    Example:
        ```python
        async with BriefingService() as service:
            briefing = await service.generate_briefing(doc_id, full_text)
        ```
    """
    
    def __init__(self, settings: Optional[Settings] = None):
        """Initialize briefing service with configuration."""
        self.settings = settings or get_settings()
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        pass
    
    async def generate_briefing(
        self, 
        doc_id: str, 
        full_text: str
    ) -> BriefingResponse:
        """
        Generate a briefing for a document using the local LLM.
        
        Args:
            doc_id: Document ID
            full_text: Complete document text
            
        Returns:
            BriefingResponse with summary, topics, and questions
            
        Raises:
            Exception: If LLM generation fails
        """
        logger.info(f"Generating briefing for document {doc_id}")
        
        # Import here to avoid circular dependency
        from services.llm_factory import LLMService
        
        try:
            async with LLMService() as llm:
                # Construct prompt for structured briefing generation
                # Limit text length based on model context (configurable via settings)
                max_text_length = getattr(self.settings, 'briefing_max_chars', 8000)
                truncated_text = full_text[:max_text_length]
                if len(full_text) > max_text_length:
                    logger.info(f"Truncated document from {len(full_text)} to {max_text_length} chars for briefing")
                
                prompt = f"""You are an expert document analyst. Analyze the following document and provide a comprehensive briefing.

Document text:
{truncated_text}

Please provide your response in the following JSON format:
{{
    "summary": "A concise 1-paragraph summary of the document",
    "key_topics": ["Topic 1", "Topic 2", "Topic 3", "Topic 4", "Topic 5", "Topic 6", "Topic 7"],
    "suggested_questions": ["Question 1?", "Question 2?", "Question 3?"]
}}

Guidelines:
- Summary should be 3-5 sentences capturing the main points
- Key topics should be 5-7 bullet points highlighting important concepts
- Suggested questions should help users explore the document further
- Return ONLY valid JSON, no additional text
"""
                
                # Generate response
                response = await llm.chat(user_message=prompt, context=None)
                
                # Parse JSON response
                import json
                try:
                    data = json.loads(response)
                    
                    briefing = BriefingResponse(
                        summary=data.get("summary", "Summary unavailable"),
                        key_topics=data.get("key_topics", [])[:7],  # Limit to 7
                        suggested_questions=data.get("suggested_questions", [])[:3],  # Limit to 3
                        doc_id=doc_id,
                    )
                    
                    # Cache briefing in memory
                    _briefing_cache[doc_id] = briefing
                    
                    logger.info(f"Briefing generated successfully for {doc_id}")
                    return briefing
                    
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse LLM response as JSON: {e}")
                    # Return a basic briefing if parsing fails
                    return BriefingResponse(
                        summary="Unable to generate summary automatically.",
                        key_topics=["Automated briefing failed"],
                        suggested_questions=["What are the main topics in this document?"],
                        doc_id=doc_id,
                    )
                    
        except Exception as e:
            logger.error(f"Briefing generation failed for {doc_id}: {e}")
            # Fallback for when LLM is offline or fails: use text preview
            summary_preview = truncated_text[:500].replace("\n", " ") + "..." if len(truncated_text) > 500 else truncated_text
            
            return BriefingResponse(
                summary=f"Automated summary unavailable (LLM service offline). Content preview: {summary_preview}",
                key_topics=["Content Preview (LLM Offline)", "Manual Review Required"],
                suggested_questions=[
                    "What is the main purpose of this document?",
                    "Who is the intended audience?",
                    "What are the key takeaways?"
                ],
                doc_id=doc_id,
            )
    
    async def get_briefing(self, doc_id: str) -> Optional[BriefingResponse]:
        """
        Retrieve saved briefing for a document.
        
        Args:
            doc_id: Document ID
            
        Returns:
            BriefingResponse if found, None otherwise
        """
        briefing = _briefing_cache.get(doc_id)
        if briefing:
            logger.debug(f"Briefing retrieved from cache for {doc_id}")
        return briefing
