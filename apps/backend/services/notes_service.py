"""
Sovereign Cognitive Engine - Notes Service
==========================================
User notes management with Neo4j persistence.
"""

import logging
from typing import Optional, List
from uuid import uuid4

from neo4j import AsyncGraphDatabase, AsyncDriver
from neo4j.exceptions import Neo4jError

from config import Settings, get_settings
from schemas import SavedNote, CreateNoteRequest

logger = logging.getLogger(__name__)


class NotesService:
    """
    Service for managing user-created notes.
    
    Notes can optionally be linked to source chunks for citation.
    
    Example:
        ```python
        async with NotesService() as service:
            note = await service.create_note("My insight", tags=["research"])
        ```
    """
    
    def __init__(self, settings: Optional[Settings] = None):
        """Initialize notes service with configuration."""
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
    
    async def create_note(self, request: CreateNoteRequest) -> SavedNote:
        """
        Create a new note and persist to Neo4j.
        
        Args:
            request: CreateNoteRequest with note details
            
        Returns:
            SavedNote with generated ID and timestamp
            
        Raises:
            Neo4jError: If database operation fails
        """
        if not self._neo4j_driver:
            raise RuntimeError("Neo4j driver not initialized. Use async context manager.")
        
        # Create note object
        note = SavedNote(
            note_id=uuid4(),
            content=request.content,
            tags=request.tags or [],
            source_citation_id=request.source_citation_id,
        )
        
        logger.info(f"Creating note {note.note_id}")
        
        async with self._neo4j_driver.session() as session:
            # Create Note node
            await session.run(
                """
                CREATE (n:Note {
                    id: $note_id,
                    content: $content,
                    tags: $tags,
                    source_citation_id: $source_citation_id,
                    created_at: datetime($created_at)
                })
                """,
                note_id=str(note.note_id),
                content=note.content,
                tags=note.tags,
                source_citation_id=note.source_citation_id,
                created_at=note.created_at.isoformat(),
            )
            
            # If source citation exists, create relationship
            if note.source_citation_id:
                await session.run(
                    """
                    MATCH (n:Note {id: $note_id})
                    MATCH (c:Chunk {id: $chunk_id})
                    MERGE (n)-[:CITES]->(c)
                    """,
                    note_id=str(note.note_id),
                    chunk_id=note.source_citation_id,
                )
            
            logger.debug(f"Note {note.note_id} created successfully")
        
        return note
    
    async def get_all_notes(self) -> List[SavedNote]:
        """
        Retrieve all notes ordered by creation date (newest first).
        
        Returns:
            List of SavedNote objects
        """
        if not self._neo4j_driver:
            raise RuntimeError("Neo4j driver not initialized. Use async context manager.")
        
        async with self._neo4j_driver.session() as session:
            result = await session.run(
                """
                MATCH (n:Note)
                RETURN n.id as note_id,
                       n.content as content,
                       n.tags as tags,
                       n.source_citation_id as source_citation_id,
                       n.created_at as created_at
                ORDER BY n.created_at DESC
                """
            )
            
            notes = []
            async for record in result:
                from datetime import datetime
                notes.append(SavedNote(
                    note_id=record["note_id"],
                    content=record["content"],
                    tags=record["tags"] or [],
                    source_citation_id=record["source_citation_id"],
                    created_at=datetime.fromisoformat(record["created_at"]) if record["created_at"] else datetime.utcnow(),
                ))
            
            logger.debug(f"Retrieved {len(notes)} notes")
            return notes
    
    async def get_note_by_id(self, note_id: str) -> Optional[SavedNote]:
        """
        Retrieve a specific note by ID.
        
        Args:
            note_id: Note UUID as string
            
        Returns:
            SavedNote if found, None otherwise
        """
        if not self._neo4j_driver:
            raise RuntimeError("Neo4j driver not initialized. Use async context manager.")
        
        async with self._neo4j_driver.session() as session:
            result = await session.run(
                """
                MATCH (n:Note {id: $note_id})
                RETURN n.id as note_id,
                       n.content as content,
                       n.tags as tags,
                       n.source_citation_id as source_citation_id,
                       n.created_at as created_at
                """,
                note_id=note_id,
            )
            
            record = await result.single()
            if not record:
                return None
            
            from datetime import datetime
            return SavedNote(
                note_id=record["note_id"],
                content=record["content"],
                tags=record["tags"] or [],
                source_citation_id=record["source_citation_id"],
                created_at=datetime.fromisoformat(record["created_at"]) if record["created_at"] else datetime.utcnow(),
            )
    
    async def delete_note(self, note_id: str) -> bool:
        """
        Delete a note by ID.
        
        Args:
            note_id: Note UUID as string
            
        Returns:
            True if note was deleted, False if not found
        """
        if not self._neo4j_driver:
            raise RuntimeError("Neo4j driver not initialized. Use async context manager.")
        
        async with self._neo4j_driver.session() as session:
            result = await session.run(
                """
                MATCH (n:Note {id: $note_id})
                DETACH DELETE n
                RETURN count(n) as deleted_count
                """,
                note_id=note_id,
            )
            
            record = await result.single()
            deleted = record["deleted_count"] > 0 if record else False
            
            if deleted:
                logger.info(f"Note {note_id} deleted")
            else:
                logger.warning(f"Note {note_id} not found for deletion")
            
            return deleted
