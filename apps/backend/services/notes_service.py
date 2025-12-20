"""
Sovereign Cognitive Engine - Notes Service
==========================================
User notes management with SQLite persistence (Replacing Neo4j).
"""

import logging
import sqlite3
import aiosqlite
from typing import Optional, List
from uuid import uuid4
from datetime import datetime
import os

from config import Settings, get_settings
from schemas import SavedNote, CreateNoteRequest

logger = logging.getLogger(__name__)

DB_PATH = "data/notes.db"

class NotesService:
    """
    Service for managing user-created notes using SQLite.
    """
    
    def __init__(self, settings: Optional[Settings] = None):
        """Initialize notes service with configuration."""
        self.settings = settings or get_settings()
        self._db_path = DB_PATH
        # Ensure data directory exists
        os.makedirs(os.path.dirname(self._db_path), exist_ok=True)
    
    async def _init_db(self):
        """Initialize SQLite database table."""
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS notes (
                    id TEXT PRIMARY KEY,
                    content TEXT NOT NULL,
                    tags TEXT,
                    source_citation_id TEXT,
                    created_at TEXT NOT NULL
                )
            """)
            await db.commit()

    async def __aenter__(self):
        """Async context manager entry."""
        await self._init_db()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        pass
    
    async def create_note(self, request: CreateNoteRequest) -> SavedNote:
        """
        Create a new note and persist to SQLite.
        """
        note = SavedNote(
            note_id=uuid4(),
            content=request.content,
            tags=request.tags or [],
            source_citation_id=request.source_citation_id,
        )
        
        logger.info(f"Creating note {note.note_id}")
        
        tags_str = ",".join(note.tags) if note.tags else ""
        
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                """
                INSERT INTO notes (id, content, tags, source_citation_id, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    str(note.note_id),
                    note.content,
                    tags_str,
                    note.source_citation_id,
                    note.created_at.isoformat()
                )
            )
            await db.commit()
            
        logger.debug(f"Note {note.note_id} created successfully")
        return note
    
    async def get_all_notes(self) -> List[SavedNote]:
        """
        Retrieve all notes ordered by creation date (newest first).
        """
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM notes ORDER BY created_at DESC")
            rows = await cursor.fetchall()
            
            notes = []
            for row in rows:
                tags = row['tags'].split(',') if row['tags'] else []
                notes.append(SavedNote(
                    note_id=row['id'],
                    content=row['content'],
                    tags=tags,
                    source_citation_id=row['source_citation_id'],
                    created_at=datetime.fromisoformat(row['created_at'])
                ))
            
            return notes

    async def get_note_by_id(self, note_id: str) -> Optional[SavedNote]:
        """
        Retrieve a specific note by ID.
        """
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM notes WHERE id = ?", (note_id,))
            row = await cursor.fetchone()
            
            if not row:
                return None
                
            tags = row['tags'].split(',') if row['tags'] else []
            return SavedNote(
                note_id=row['id'],
                content=row['content'],
                tags=tags,
                source_citation_id=row['source_citation_id'],
                created_at=datetime.fromisoformat(row['created_at'])
            )

    async def delete_note(self, note_id: str) -> bool:
        """
        Delete a note by ID.
        """
        async with aiosqlite.connect(self._db_path) as db:
            cursor = await db.execute("DELETE FROM notes WHERE id = ?", (note_id,))
            await db.commit()
            deleted = cursor.rowcount > 0
            
            if deleted:
                logger.info(f"Note {note_id} deleted")
            else:
                logger.warning(f"Note {note_id} not found for deletion")
            
            return deleted
