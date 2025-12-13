"""
Sovereign Cognitive Engine - Audio Factory
===========================================
Async TTS client with streaming audio synthesis and parallel prefetching.
"""

import asyncio
import time
from typing import AsyncGenerator, Optional

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from config import Settings, get_settings
from services.scriptwriter import DialogueLine, PodcastScript

# Structured logging with loguru
try:
    from loguru import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


# =============================================================================
# Custom Exceptions
# =============================================================================

class TTSServiceError(Exception):
    """Base exception for TTS service errors."""
    pass


class TTSBusyError(TTSServiceError):
    """Raised when TTS server is overloaded."""
    pass


# =============================================================================
# Voice Configuration
# =============================================================================

# Voice mapping for podcast hosts
# These map to Kokoro/StyleTTS2 voice IDs
VOICE_MAP = {
    "Alex": {
        "voice_id": "af_nicole",  # Analytical female voice
        "speed": 1.0,
        "pitch": 0.0,
    },
    "Sarah": {
        "voice_id": "af_sarah",  # Enthusiastic female voice  
        "speed": 1.05,  # Slightly faster for enthusiasm
        "pitch": 0.1,
    },
}

# Default voice for unknown speakers
DEFAULT_VOICE = {
    "voice_id": "af_nicole",
    "speed": 1.0,
    "pitch": 0.0,
}


# =============================================================================
# Audio Segment Model
# =============================================================================

class AudioSegment:
    """Container for synthesized audio data."""
    
    def __init__(
        self,
        speaker: str,
        text: str,
        audio_bytes: bytes,
        duration_ms: int,
        index: int,
    ):
        self.speaker = speaker
        self.text = text
        self.audio_bytes = audio_bytes
        self.duration_ms = duration_ms
        self.index = index
    
    def __repr__(self):
        return f"AudioSegment({self.speaker}, {len(self.audio_bytes)} bytes, {self.duration_ms}ms)"


# =============================================================================
# Audio Factory Service
# =============================================================================

class AudioFactory:
    """
    Async TTS client for Kokoro/StyleTTS2 synthesis.
    
    Features:
    - Parallel prefetching (synthesize next N lines while current plays)
    - Speaker-specific voice configuration
    - Streaming audio generation
    - Retry logic for busy servers
    
    Example:
        ```python
        async with AudioFactory() as audio:
            async for segment in audio.stream_audio(podcast_script):
                # Process audio segment
                yield segment.audio_bytes
        ```
    """
    
    # Number of lines to prefetch in parallel
    PREFETCH_COUNT = 3
    
    def __init__(
        self,
        base_url: Optional[str] = None,
        settings: Optional[Settings] = None,
    ):
        """
        Initialize Audio Factory.
        
        Args:
            base_url: TTS server URL (default: http://tts-engine:8880)
            settings: Application settings
        """
        self.settings = settings or get_settings()
        self.base_url = base_url or "http://tts-engine:8880"
        self._client: Optional[httpx.AsyncClient] = None
    
    async def __aenter__(self):
        """Initialize async HTTP client."""
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(60.0, connect=10.0),
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
    
    def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(60.0, connect=10.0),
            )
        return self._client
    
    def _get_voice_config(self, speaker: str) -> dict:
        """Get voice configuration for a speaker."""
        return VOICE_MAP.get(speaker, DEFAULT_VOICE)
    
    @retry(
        retry=retry_if_exception_type(TTSBusyError),
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=2, min=1, max=20),
        before_sleep=lambda retry_state: logger.warning(
            f"TTS busy, retrying in {retry_state.next_action.sleep}s"
        ),
    )
    async def synthesize_line(
        self,
        text: str,
        speaker: str,
        index: int = 0,
    ) -> AudioSegment:
        """
        Synthesize a single line of dialogue to audio.
        
        Args:
            text: Text to synthesize
            speaker: Speaker name for voice selection
            index: Line index in script
            
        Returns:
            AudioSegment with synthesized audio bytes
        """
        start_time = time.perf_counter()
        client = self._get_client()
        voice_config = self._get_voice_config(speaker)
        
        # Clean text of stage directions
        clean_text = self._clean_text_for_synthesis(text)
        
        # Build TTS request
        # Kokoro API format (adjust based on actual API)
        request_body = {
            "text": clean_text,
            "voice": voice_config["voice_id"],
            "speed": voice_config["speed"],
            "pitch": voice_config.get("pitch", 0.0),
            "output_format": "wav",  # or "mp3"
        }
        
        try:
            response = await client.post("/synthesize", json=request_body)
            
            if response.status_code == 503:
                raise TTSBusyError("TTS server is busy")
            
            response.raise_for_status()
            
            audio_bytes = response.content
            
            # Estimate duration from audio length (approximate)
            # WAV: ~176KB per second at 44.1kHz 16-bit mono
            duration_ms = int(len(audio_bytes) / 176 * 1000 / 1000) if audio_bytes else 0
            
            latency_ms = (time.perf_counter() - start_time) * 1000
            
            logger.debug(
                "TTS synthesis complete",
                speaker=speaker,
                text_length=len(text),
                audio_bytes=len(audio_bytes),
                duration_ms=duration_ms,
                latency_ms=round(latency_ms, 2),
            )
            
            return AudioSegment(
                speaker=speaker,
                text=text,
                audio_bytes=audio_bytes,
                duration_ms=duration_ms,
                index=index,
            )
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 503:
                raise TTSBusyError("TTS server is busy") from e
            logger.error(f"TTS request failed: {e}")
            raise TTSServiceError(f"TTS request failed: {e}") from e
        except httpx.RequestError as e:
            logger.error(f"TTS connection error: {e}")
            raise TTSServiceError(f"TTS connection error: {e}") from e
    
    def _clean_text_for_synthesis(self, text: str) -> str:
        """
        Clean text for TTS synthesis.
        
        Handles stage directions like [laughs], [sigh] by either:
        - Removing them (simple approach)
        - Converting to SSML pauses (if TTS supports)
        """
        import re
        
        # Map stage directions to pauses or remove
        replacements = {
            r"\[laughs?\]": "...",  # Short pause for laugh
            r"\[chuckles?\]": "...",
            r"\[sigh\]": "...",
            r"\[pause\]": "...",
            r"\[excited\]": "",  # Remove emotion markers
            r"\[thoughtful\]": "",
        }
        
        cleaned = text
        for pattern, replacement in replacements.items():
            cleaned = re.sub(pattern, replacement, cleaned, flags=re.IGNORECASE)
        
        return cleaned.strip()
    
    async def stream_audio(
        self,
        script: PodcastScript,
    ) -> AsyncGenerator[AudioSegment, None]:
        """
        Stream synthesized audio from a podcast script.
        
        Uses parallel prefetching to synthesize upcoming lines
        while yielding current ones.
        
        Args:
            script: PodcastScript with dialogue lines
            
        Yields:
            AudioSegment for each dialogue line in order
        """
        dialogue = script.dialogue
        total_lines = len(dialogue)
        
        if total_lines == 0:
            logger.warning("Empty script provided to stream_audio")
            return
        
        logger.info(
            "Starting audio streaming",
            title=script.title,
            total_lines=total_lines,
        )
        
        # Queue for prefetched audio segments
        pending_tasks: dict[int, asyncio.Task] = {}
        
        async def fetch_segment(line: DialogueLine, index: int) -> AudioSegment:
            """Fetch a single audio segment."""
            return await self.synthesize_line(
                text=line.text,
                speaker=line.speaker,
                index=index,
            )
        
        # Process lines with prefetching
        for current_idx, line in enumerate(dialogue):
            # Start prefetching next N lines
            for prefetch_idx in range(
                current_idx + 1,
                min(current_idx + 1 + self.PREFETCH_COUNT, total_lines)
            ):
                if prefetch_idx not in pending_tasks:
                    prefetch_line = dialogue[prefetch_idx]
                    pending_tasks[prefetch_idx] = asyncio.create_task(
                        fetch_segment(prefetch_line, prefetch_idx)
                    )
            
            # Get current segment (either from pending or synthesize now)
            if current_idx in pending_tasks:
                # Was prefetched, await it
                try:
                    segment = await pending_tasks.pop(current_idx)
                except Exception as e:
                    logger.error(f"Prefetched segment {current_idx} failed: {e}")
                    # Try direct synthesis as fallback
                    segment = await fetch_segment(line, current_idx)
            else:
                # First few lines - synthesize directly
                segment = await fetch_segment(line, current_idx)
            
            yield segment
            
            logger.debug(
                f"Yielded segment {current_idx + 1}/{total_lines}",
                speaker=segment.speaker,
            )
        
        # Cancel any remaining prefetch tasks
        for idx, task in pending_tasks.items():
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        
        logger.info("Audio streaming complete")
    
    async def synthesize_full_podcast(
        self,
        script: PodcastScript,
    ) -> bytes:
        """
        Synthesize entire podcast script to a single audio file.
        
        Collects all segments and concatenates them.
        
        Args:
            script: PodcastScript to synthesize
            
        Returns:
            Complete audio file as bytes
        """
        all_audio = []
        total_duration_ms = 0
        
        async for segment in self.stream_audio(script):
            all_audio.append(segment.audio_bytes)
            total_duration_ms += segment.duration_ms
        
        # Simple concatenation for WAV (works for raw PCM)
        # For production, use proper audio library for format-aware concat
        combined = b"".join(all_audio)
        
        logger.info(
            "Full podcast synthesized",
            title=script.title,
            segments=len(all_audio),
            duration_ms=total_duration_ms,
            total_bytes=len(combined),
        )
        
        return combined
    
    async def synthesize_with_parallel_batches(
        self,
        script: PodcastScript,
        batch_size: int = 5,
    ) -> list[AudioSegment]:
        """
        Synthesize script using parallel batch processing.
        
        More aggressive parallelism than streaming - synthesizes
        multiple lines simultaneously.
        
        Args:
            script: PodcastScript to synthesize
            batch_size: Number of lines to process in parallel
            
        Returns:
            List of AudioSegments in order
        """
        dialogue = script.dialogue
        all_segments: list[AudioSegment] = []
        
        # Process in batches
        for batch_start in range(0, len(dialogue), batch_size):
            batch_end = min(batch_start + batch_size, len(dialogue))
            batch = dialogue[batch_start:batch_end]
            
            # Create tasks for batch
            tasks = [
                self.synthesize_line(
                    text=line.text,
                    speaker=line.speaker,
                    index=batch_start + i,
                )
                for i, line in enumerate(batch)
            ]
            
            # Execute batch in parallel
            try:
                batch_results = await asyncio.gather(*tasks, return_exceptions=True)
                
                for result in batch_results:
                    if isinstance(result, Exception):
                        logger.error(f"Batch synthesis error: {result}")
                        # Create empty segment as placeholder
                        all_segments.append(AudioSegment(
                            speaker="unknown",
                            text="[synthesis failed]",
                            audio_bytes=b"",
                            duration_ms=0,
                            index=len(all_segments),
                        ))
                    else:
                        all_segments.append(result)
                        
            except Exception as e:
                logger.error(f"Batch processing failed: {e}")
                raise
        
        # Sort by index to ensure order
        all_segments.sort(key=lambda s: s.index)
        
        logger.info(
            "Parallel batch synthesis complete",
            total_segments=len(all_segments),
        )
        
        return all_segments
