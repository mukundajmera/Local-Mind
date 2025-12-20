"""
Sovereign Cognitive Engine - Notes Service
==========================================
User notes management with SQLite persistence.
Enhanced with project association, update capability, search, and pin functionality.
"""

import logging
import aiosqlite
from typing import Optional, List
from uuid import uuid4
from datetime import datetime
import os
import json

from config import Settings, get_settings
from schemas import SavedNote, CreateNoteRequest, UpdateNoteRequest

logger = logging.getLogger(__name__)

DB_PATH = "data/notes.db"


class NotesService:
    """
    Service for managing user-created notes using SQLite.
    
    Features:
    - CRUD operations for notes
    - Project-based filtering
    - Tag-based search
    - Pin/unpin functionality
    - Full-text search
    """
    
    def __init__(self, settings: Optional[Settings] = None):
        """Initialize notes service with configuration."""
        self.settings = settings or get_settings()
        self._db_path = DB_PATH
        # Ensure data directory exists
        os.makedirs(os.path.dirname(self._db_path), exist_ok=True)
    
    async def _init_db(self):
        """Initialize SQLite database table with enhanced schema."""
        async with aiosqlite.connect(self._db_path) as db:
            # Create enhanced notes table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS notes (
                    id TEXT PRIMARY KEY,
                    project_id TEXT,
                    content TEXT NOT NULL,
                    title TEXT,
                    tags TEXT,
                    source_citation_id TEXT,
                    source_filename TEXT,
                    is_pinned INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT
                )
            """)
            
            # Add new columns if they don't exist (migration support)
            try:
                await db.execute("ALTER TABLE notes ADD COLUMN project_id TEXT")
            except aiosqlite.OperationalError:
                pass  # Column already exists
            
            try:
                await db.execute("ALTER TABLE notes ADD COLUMN title TEXT")
            except aiosqlite.OperationalError:
                pass
            
            try:
                await db.execute("ALTER TABLE notes ADD COLUMN source_filename TEXT")
            except aiosqlite.OperationalError:
                pass
            
            try:
                await db.execute("ALTER TABLE notes ADD COLUMN is_pinned INTEGER DEFAULT 0")
            except aiosqlite.OperationalError:
                pass
            
            try:
                await db.execute("ALTER TABLE notes ADD COLUMN updated_at TEXT")
            except aiosqlite.OperationalError:
                pass
            
            # Create indexes for common queries
            await db.execute("CREATE INDEX IF NOT EXISTS idx_notes_project ON notes(project_id)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_notes_pinned ON notes(is_pinned)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_notes_created ON notes(created_at)")
            
            await db.commit()

    async def __aenter__(self):
        """Async context manager entry."""
        await self._init_db()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        pass
    
    def _row_to_note(self, row) -> SavedNote:
        """Convert a database row to a SavedNote object."""
        tags = row['tags'].split(',') if row['tags'] else []
        # Filter empty tags
        tags = [t.strip() for t in tags if t.strip()]
        
        return SavedNote(
            note_id=row['id'],
            project_id=row['project_id'] if row['project_id'] else None,
            content=row['content'],
            title=row['title'] if row['title'] else None,
            tags=tags,
            source_citation_id=row['source_citation_id'],
            source_filename=row['source_filename'] if row['source_filename'] else None,
            is_pinned=bool(row['is_pinned']) if row['is_pinned'] is not None else False,
            created_at=datetime.fromisoformat(row['created_at']),
            updated_at=datetime.fromisoformat(row['updated_at']) if row['updated_at'] else None
        )
    
    async def create_note(self, request: CreateNoteRequest) -> SavedNote:
        """
        Create a new note and persist to SQLite.
        """
        now = datetime.utcnow()
        note = SavedNote(
            note_id=uuid4(),
            project_id=request.project_id,
            content=request.content,
            title=request.title,
            tags=request.tags or [],
            source_citation_id=request.source_citation_id,
            source_filename=request.source_filename,
            is_pinned=False,
            created_at=now,
            updated_at=now
        )
        
        logger.info(f"Creating note {note.note_id}")
        
        tags_str = ",".join(note.tags) if note.tags else ""
        
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                """
                INSERT INTO notes (id, project_id, content, title, tags, source_citation_id, 
                                   source_filename, is_pinned, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(note.note_id),
                    str(note.project_id) if note.project_id else None,
                    note.content,
                    note.title,
                    tags_str,
                    note.source_citation_id,
                    note.source_filename,
                    0,
                    note.created_at.isoformat(),
                    note.updated_at.isoformat()
                )
            )
            await db.commit()
            
        logger.debug(f"Note {note.note_id} created successfully")
        return note
    
    async def update_note(self, note_id: str, request: UpdateNoteRequest) -> Optional[SavedNote]:
        """
        Update an existing note.
        """
        # First check if note exists
        existing = await self.get_note_by_id(note_id)
        if not existing:
            logger.warning(f"Note {note_id} not found for update")
            return None
        
        # Build update query dynamically based on provided fields
        updates = []
        params = []
        
        if request.content is not None:
            updates.append("content = ?")
            params.append(request.content)
        
        if request.title is not None:
            updates.append("title = ?")
            params.append(request.title)
        
        if request.tags is not None:
            updates.append("tags = ?")
            params.append(",".join(request.tags))
        
        if request.is_pinned is not None:
            updates.append("is_pinned = ?")
            params.append(1 if request.is_pinned else 0)
        
        # Always update the updated_at timestamp
        now = datetime.utcnow()
        updates.append("updated_at = ?")
        params.append(now.isoformat())
        
        # Add note_id to params
        params.append(note_id)
        
        async with aiosqlite.connect(self._db_path) as db:
            query = f"UPDATE notes SET {', '.join(updates)} WHERE id = ?"
            await db.execute(query, params)
            await db.commit()
        
        logger.info(f"Note {note_id} updated successfully")
        return await self.get_note_by_id(note_id)
    
    async def toggle_pin(self, note_id: str) -> Optional[SavedNote]:
        """
        Toggle the pin status of a note.
        """
        existing = await self.get_note_by_id(note_id)
        if not existing:
            return None
        
        new_pinned = not existing.is_pinned
        now = datetime.utcnow()
        
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                "UPDATE notes SET is_pinned = ?, updated_at = ? WHERE id = ?",
                (1 if new_pinned else 0, now.isoformat(), note_id)
            )
            await db.commit()
        
        logger.info(f"Note {note_id} pin status toggled to {new_pinned}")
        return await self.get_note_by_id(note_id)
    
    async def get_all_notes(self, project_id: Optional[str] = None) -> List[SavedNote]:
        """
        Retrieve all notes ordered by pin status then creation date (newest first).
        Optionally filter by project.
        """
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            
            if project_id:
                cursor = await db.execute(
                    """SELECT * FROM notes WHERE project_id = ? 
                       ORDER BY is_pinned DESC, created_at DESC""",
                    (project_id,)
                )
            else:
                cursor = await db.execute(
                    "SELECT * FROM notes ORDER BY is_pinned DESC, created_at DESC"
                )
            
            rows = await cursor.fetchall()
            return [self._row_to_note(row) for row in rows]

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
            
            return self._row_to_note(row)

    async def search_notes(
        self, 
        query: Optional[str] = None, 
        tags: Optional[List[str]] = None,
        project_id: Optional[str] = None
    ) -> List[SavedNote]:
        """
        Search notes by content and/or tags.
        """
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            
            conditions = []
            params = []
            
            if query:
                # Search in both content and title
                conditions.append("(content LIKE ? OR title LIKE ?)")
                search_term = f"%{query}%"
                params.extend([search_term, search_term])
            
            if tags:
                # Search for any of the provided tags
                tag_conditions = []
                for tag in tags:
                    tag_conditions.append("tags LIKE ?")
                    params.append(f"%{tag}%")
                conditions.append(f"({' OR '.join(tag_conditions)})")
            
            if project_id:
                conditions.append("project_id = ?")
                params.append(project_id)
            
            where_clause = " AND ".join(conditions) if conditions else "1=1"
            
            cursor = await db.execute(
                f"""SELECT * FROM notes WHERE {where_clause} 
                    ORDER BY is_pinned DESC, created_at DESC""",
                params
            )
            
            rows = await cursor.fetchall()
            return [self._row_to_note(row) for row in rows]

    async def get_all_tags(self, project_id: Optional[str] = None) -> List[str]:
        """
        Get all unique tags across notes.
        """
        notes = await self.get_all_notes(project_id)
        all_tags = set()
        for note in notes:
            all_tags.update(note.tags)
        return sorted(list(all_tags))

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


# Singleton instance for convenience
_notes_service: Optional[NotesService] = None


async def get_notes_service() -> NotesService:
    """Get or create the notes service singleton."""
    global _notes_service
    if _notes_service is None:
        _notes_service = NotesService()
        await _notes_service._init_db()
    return _notes_service
