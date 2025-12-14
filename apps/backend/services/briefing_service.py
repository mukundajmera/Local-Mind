"""
Sovereign Cognitive Engine - Briefing Service
==============================================
Automated document summarization and briefing generation.
"""

import logging
from typing import Optional
from uuid import UUID

from neo4j import AsyncGraphDatabase, AsyncDriver
from neo4j.exceptions import Neo4jError

from config import Settings, get_settings
from schemas import BriefingResponse

logger = logging.getLogger(__name__)


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
        self._neo4j_driver: Optional[AsyncDriver] = None
    
    async def __aenter__(self):
        """Async context manager entry."""
        self._neo4j_driver = AsyncGraphDatabase.driver(
            self.settings.neo4j_uri,
            auth=(self.settings.neo4j_user, self.settings.neo4j_password),
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._neo4j_driver:
            await self._neo4j_driver.close()
    
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
                    
                    # Persist briefing to database
                    await self._save_briefing(doc_id, briefing)
                    
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
            # Return a minimal briefing on error
            return BriefingResponse(
                summary="Briefing generation encountered an error.",
                key_topics=["Error during processing"],
                suggested_questions=["What is this document about?"],
                doc_id=doc_id,
            )
    
    async def _save_briefing(self, doc_id: str, briefing: BriefingResponse):
        """
        Save briefing data to the Document node in Neo4j.
        
        Args:
            doc_id: Document ID
            briefing: BriefingResponse to persist
        """
        if not self._neo4j_driver:
            raise RuntimeError("Neo4j driver not initialized. Use async context manager.")
        
        async with self._neo4j_driver.session() as session:
            await session.run(
                """
                MATCH (d:Document {id: $doc_id})
                SET d.summary = $summary,
                    d.key_topics = $key_topics,
                    d.suggested_questions = $suggested_questions,
                    d.briefing_generated_at = datetime($generated_at)
                """,
                doc_id=doc_id,
                summary=briefing.summary,
                key_topics=briefing.key_topics,
                suggested_questions=briefing.suggested_questions,
                generated_at=briefing.generated_at.isoformat(),
            )
            
            logger.debug(f"Briefing persisted for document {doc_id}")
    
    async def get_briefing(self, doc_id: str) -> Optional[BriefingResponse]:
        """
        Retrieve saved briefing for a document.
        
        Args:
            doc_id: Document ID
            
        Returns:
            BriefingResponse if found, None otherwise
            
        Note:
            For optimal performance with large document counts, ensure an index exists:
            CREATE INDEX document_id_idx IF NOT EXISTS FOR (d:Document) ON (d.id)
        """
        if not self._neo4j_driver:
            raise RuntimeError("Neo4j driver not initialized. Use async context manager.")
        
        async with self._neo4j_driver.session() as session:
            result = await session.run(
                """
                MATCH (d:Document {id: $doc_id})
                RETURN d.summary as summary,
                       d.key_topics as key_topics,
                       d.suggested_questions as suggested_questions,
                       d.briefing_generated_at as generated_at
                """,
                doc_id=doc_id,
            )
            
            record = await result.single()
            if not record or not record["summary"]:
                return None
            
            from datetime import datetime
            
            # Handle missing generated_at with warning
            generated_at = record["generated_at"]
            if not generated_at:
                logger.warning(f"Document {doc_id} briefing missing generated_at timestamp")
                generated_at_dt = datetime.utcnow()
            else:
                generated_at_dt = datetime.fromisoformat(generated_at)
            
            return BriefingResponse(
                summary=record["summary"],
                key_topics=record["key_topics"] or [],
                suggested_questions=record["suggested_questions"] or [],
                doc_id=doc_id,
                generated_at=generated_at_dt,
            )
