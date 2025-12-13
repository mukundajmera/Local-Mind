"""
Sovereign Cognitive Engine - Scriptwriter Agent
================================================
AI-powered podcast script generation with dual-host dialogue format.
"""

import json
from typing import Optional

from pydantic import BaseModel, Field
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from config import Settings, get_settings

# Structured logging with loguru
try:
    from loguru import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


# =============================================================================
# Script Data Models
# =============================================================================

class DialogueLine(BaseModel):
    """Single line of dialogue in the podcast script."""
    
    speaker: str = Field(
        ...,
        description="Speaker name: 'Alex' or 'Sarah'",
        pattern="^(Alex|Sarah)$",
    )
    text: str = Field(
        ...,
        min_length=1,
        description="The spoken dialogue text",
    )
    emotion: Optional[str] = Field(
        default=None,
        description="Optional emotion hint: excited, thoughtful, skeptical, amused",
    )


class PodcastScript(BaseModel):
    """Complete podcast script with metadata."""
    
    title: str = Field(..., description="Episode title")
    summary: str = Field(..., description="Brief episode summary")
    dialogue: list[DialogueLine] = Field(
        ...,
        min_length=5,
        description="List of dialogue lines between Alex and Sarah",
    )
    estimated_duration_seconds: int = Field(
        default=300,
        description="Estimated audio duration",
    )


# =============================================================================
# Scriptwriter Agent
# =============================================================================

# The "Deep Dive" system prompt for podcast generation
PODCAST_SYSTEM_PROMPT = """You are the creative director for "Deep Dive", an AI-generated podcast that makes complex topics accessible and entertaining.

You must write dialogue for TWO AI hosts with distinct personalities:

🎙️ ALEX (Skeptical, Analytical)
- Questions assumptions and asks "But wait, how does that actually work?"
- Uses precise language and data-driven observations
- Occasionally dry humor, deadpan delivery
- Often says: "Let's break this down...", "The interesting thing is...", "But here's what I don't get..."

🌟 SARAH (Enthusiastic, Metaphor-heavy)  
- Gets genuinely excited about discoveries
- Explains concepts using vivid analogies and everyday comparisons
- Uses expressive language with natural filler words
- Often says: "Oh, this is so cool!", "It's like...", "Wait, hang on...", "Mind. Blown."

DIALOGUE STYLE REQUIREMENTS:
1. Natural conversation flow - hosts interrupt, agree, build on each other's points
2. Use vocal markers: [laughs], [sigh], [chuckles], [pause], [excited]
3. Include "umm", "like", "you know" sparingly for natural speech
4. Alex and Sarah should DISAGREE sometimes - intellectual tension is good!
5. End with a memorable takeaway or thought-provoking question

STRUCTURE (5 minutes, ~800-1000 words total):
- Opening hook (30 sec): Grab attention with a surprising fact or question
- Context setting (1 min): What are we talking about today?
- Deep dive (2.5 min): The meat - explore 2-3 key insights
- Synthesis (1 min): Connect the dots, what does it mean?
- Closing (30 sec): Memorable takeaway, tease next episode

OUTPUT FORMAT:
Return a JSON object with this structure:
{
  "title": "Episode title",
  "summary": "2-3 sentence summary",
  "dialogue": [
    {"speaker": "Alex", "text": "...", "emotion": "thoughtful"},
    {"speaker": "Sarah", "text": "...", "emotion": "excited"},
    ...
  ],
  "estimated_duration_seconds": 300
}

CRITICAL: Output ONLY valid JSON. No markdown, no explanations."""


class ScriptwriterAgent:
    """
    Agent that generates podcast scripts from context.
    
    Uses LLM to create natural-sounding dialogue between two AI hosts.
    
    Example:
        ```python
        scriptwriter = ScriptwriterAgent()
        async with LLMService() as llm:
            script = await scriptwriter.generate_podcast_script(
                context_text="Research on quantum computing...",
                llm_service=llm,
            )
        ```
    """
    
    def __init__(self, settings: Optional[Settings] = None):
        """Initialize scriptwriter."""
        self.settings = settings or get_settings()
    
    async def generate_podcast_script(
        self,
        context_text: str,
        llm_service: "LLMService",  # Forward reference
        title_hint: Optional[str] = None,
        target_duration_seconds: int = 300,
    ) -> PodcastScript:
        """
        Generate a podcast script from context.
        
        Args:
            context_text: Source material to discuss (RAG retrieval results)
            llm_service: Initialized LLM service for generation
            title_hint: Optional suggested title
            target_duration_seconds: Target audio length
            
        Returns:
            PodcastScript with dialogue lines
        """
        # Build the user prompt with context
        prompt = self._build_script_prompt(
            context_text=context_text,
            title_hint=title_hint,
            target_duration=target_duration_seconds,
        )
        
        # Generate structured script
        script = await llm_service.generate_structured(
            prompt=prompt,
            pydantic_model=PodcastScript,
            system_prompt=PODCAST_SYSTEM_PROMPT,
            max_tokens=4096,
        )
        
        logger.info(
            "Podcast script generated",
            title=script.title,
            dialogue_lines=len(script.dialogue),
            estimated_duration=script.estimated_duration_seconds,
        )
        
        return script
    
    def _build_script_prompt(
        self,
        context_text: str,
        title_hint: Optional[str],
        target_duration: int,
    ) -> str:
        """Build the prompt for script generation."""
        prompt_parts = [
            f"Create a {target_duration // 60}-minute podcast episode based on the following content.",
            "",
            "SOURCE MATERIAL:",
            "=" * 50,
            context_text[:8000],  # Limit context size
            "=" * 50,
            "",
        ]
        
        if title_hint:
            prompt_parts.append(f"Suggested title: {title_hint}")
            prompt_parts.append("")
        
        prompt_parts.extend([
            "Write an engaging dialogue between Alex and Sarah that:",
            "1. Explains the key concepts in accessible terms",
            "2. Highlights the most interesting or surprising insights",
            "3. Includes their signature speaking styles and natural reactions",
            "4. Maintains intellectual depth while being entertaining",
            "",
            "Generate the complete podcast script as JSON.",
        ])
        
        return "\n".join(prompt_parts)
    
    async def refine_script(
        self,
        script: PodcastScript,
        feedback: str,
        llm_service: "LLMService",
    ) -> PodcastScript:
        """
        Refine a script based on feedback.
        
        Args:
            script: Original script to refine
            feedback: User or system feedback
            llm_service: LLM service for generation
            
        Returns:
            Refined PodcastScript
        """
        current_script_json = script.model_dump_json(indent=2)
        
        prompt = f"""Here is the current podcast script:

{current_script_json}

FEEDBACK TO ADDRESS:
{feedback}

Please revise the script to address this feedback while maintaining the hosts' personalities and natural dialogue flow.

Output the complete revised script as JSON."""
        
        revised = await llm_service.generate_structured(
            prompt=prompt,
            pydantic_model=PodcastScript,
            system_prompt=PODCAST_SYSTEM_PROMPT,
            max_tokens=4096,
        )
        
        logger.info("Script refined based on feedback")
        return revised


# =============================================================================
# Convenience Function
# =============================================================================

async def generate_podcast_script(
    context_text: str,
    title_hint: Optional[str] = None,
    target_duration_seconds: int = 300,
) -> PodcastScript:
    """
    Convenience function to generate a podcast script.
    
    Creates LLM service internally for one-shot usage.
    
    Args:
        context_text: Source material for the podcast
        title_hint: Optional suggested title
        target_duration_seconds: Target audio length
        
    Returns:
        PodcastScript ready for TTS synthesis
    """
    from services.llm_factory import LLMService
    
    scriptwriter = ScriptwriterAgent()
    
    async with LLMService() as llm:
        return await scriptwriter.generate_podcast_script(
            context_text=context_text,
            llm_service=llm,
            title_hint=title_hint,
            target_duration_seconds=target_duration_seconds,
        )
