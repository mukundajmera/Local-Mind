"""
Sovereign Cognitive Engine - Ingestion Pipeline
================================================
Fast document ingestion with chunking and embedding (Pure Vector, Option B).
"""

import hashlib
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import UUID, uuid4

from pymilvus import MilvusClient, MilvusException
from tenacity import retry, stop_after_attempt, wait_exponential

# Third-party libraries
from sentence_transformers import SentenceTransformer

from config import Settings, get_settings
from schemas import (
    IngestedDocument,
    TextChunk,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Embedding Service
# =============================================================================

class EmbeddingService:
    """
    Embedding service using SentenceTransformers.
    """
    
    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        self.model_name = model_name
        self.dimension = 384  # all-MiniLM-L6-v2 dimension
        self._model = None  # Lazy load
    
    def _get_model(self):
        if self._model is None:
            logger.info(f"Loading embedding model: {self.model_name}")
            self._model = SentenceTransformer(self.model_name)
        return self._model

    async def embed_text(self, text: str) -> list[float]:
        """
        Generate embedding vector for text.
        
        Args:
            text: Input text to embed
            
        Returns:
            List of floats representing the embedding vector
        """
        import asyncio
        loop = asyncio.get_event_loop()
        
        # Run CPU-bound model in executor
        embedding = await loop.run_in_executor(
            None,
            lambda: self._get_model().encode(text, convert_to_numpy=True)
        )
        
        if hasattr(embedding, "tolist"):
            return embedding.tolist()
        return embedding
    
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple texts in batch."""
        import asyncio
        loop = asyncio.get_event_loop()
        
        embeddings = await loop.run_in_executor(
            None,
            lambda: self._get_model().encode(texts, convert_to_numpy=True)
        )
        
        if hasattr(embeddings, "tolist"):
            return embeddings.tolist()
        return embeddings


# =============================================================================
# Text Chunking
# =============================================================================

class TextChunker:
    """Split text into overlapping chunks based on token count."""
    
    def __init__(
        self,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        encoding_name: str = "cl100k_base",
    ):
        """
        Initialize chunker with size parameters.
        
        Args:
            chunk_size: Target tokens per chunk
            chunk_overlap: Overlap tokens between consecutive chunks
            encoding_name: tiktoken encoding (cl100k_base for GPT-4)
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.encoding_name = encoding_name
        self._encoder = None
    
    def _get_encoder(self):
        """Lazy load tiktoken encoder."""
        if self._encoder is None:
            try:
                import tiktoken
                self._encoder = tiktoken.get_encoding(self.encoding_name)
            except ImportError:
                logger.warning("tiktoken not available, falling back to char-based chunking")
                return None
        return self._encoder
    
    def _count_tokens(self, text: str) -> int:
        """Count tokens in text."""
        encoder = self._get_encoder()
        if encoder:
            return len(encoder.encode(text))
        # Fallback: ~4 chars per token
        return len(text) // 4
    
    def chunk_text(self, text: str, doc_id: UUID) -> list[TextChunk]:
        """
        Split text into overlapping chunks.
        
        Args:
            text: Full document text
            doc_id: Parent document ID
            
        Returns:
            List of TextChunk objects with position indexing
        """
        chunks = []
        
        # Split by paragraphs first for better semantic boundaries
        paragraphs = text.split("\n\n")
        
        current_chunk = ""
        current_start = 0
        position = 0
        char_offset = 0
        
        for para in paragraphs:
            para = para.strip()
            if not para:
                char_offset += 2  # Account for \n\n
                continue
            
            potential_chunk = current_chunk + ("\n\n" if current_chunk else "") + para
            
            if self._count_tokens(potential_chunk) <= self.chunk_size:
                current_chunk = potential_chunk
            else:
                # Save current chunk if non-empty
                if current_chunk:
                    chunks.append(TextChunk(
                        chunk_id=uuid4(),
                        doc_id=doc_id,
                        text=current_chunk,
                        position=position,
                        start_char=current_start,
                        end_char=char_offset,
                        token_count=self._count_tokens(current_chunk),
                    ))
                    position += 1
                
                # Start new chunk with overlap
                if self.chunk_overlap > 0 and current_chunk:
                    # Take last N tokens worth of text as overlap
                    overlap_chars = (self.chunk_overlap * 4)  # Approximate
                    overlap_text = current_chunk[-overlap_chars:] if len(current_chunk) > overlap_chars else ""
                    current_chunk = overlap_text + "\n\n" + para
                    current_start = char_offset - len(overlap_text)
                else:
                    current_chunk = para
                    current_start = char_offset
            
            char_offset += len(para) + 2
        
        # Don't forget the last chunk
        if current_chunk:
            chunks.append(TextChunk(
                chunk_id=uuid4(),
                doc_id=doc_id,
                text=current_chunk,
                position=position,
                start_char=current_start,
                end_char=char_offset,
                token_count=self._count_tokens(current_chunk),
            ))
        
        return chunks

    async def chunk_text_async(self, text: str, doc_id: UUID) -> list[TextChunk]:
        """
        Async wrapper for chunk_text that offloads CPU-bound work to thread pool.
        
        This prevents blocking the FastAPI event loop during text chunking.
        """
        import asyncio
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.chunk_text(text, doc_id)
        )


# =============================================================================
# Document Parser
# =============================================================================


class DocumentParser:
    """Parse documents (PDF, etc.) into raw text."""
    
    @staticmethod
    async def parse_pdf(file_path: Path) -> tuple[str, dict]:
        """
        Extract text from PDF file.
        
        Args:
            file_path: Path to PDF file
            
        Returns:
            Tuple of (extracted_text, metadata_dict)
            
        Note:
            Uses `pypdf` library for reliable parsing.
        """
        try:
            import pypdf
            
            def _read_pdf():
                reader = pypdf.PdfReader(file_path)
                text = ""
                for page in reader.pages:
                    extract = page.extract_text()
                    if extract:
                        text += extract + "\n\n"
                return text, len(reader.pages)
            
            import asyncio
            loop = asyncio.get_event_loop()
            text, num_pages = await loop.run_in_executor(None, _read_pdf)
            
            metadata = {
                "element_count": num_pages,
                "file_path": str(file_path),
                "parser": "pypdf"
            }
            
            return text, metadata
            
        except ImportError:
            logger.error("pypdf not installed. Run: pip install pypdf")
            raise
        except Exception as e:
            logger.error(f"Failed to parse PDF {file_path}: {e}")
            raise

    @staticmethod
    async def parse_text(file_path: Path) -> tuple[str, dict]:
        """
        Read text from a plain text or markdown file.
        """
        try:
            import aiofiles
            async with aiofiles.open(file_path, mode="r", encoding="utf-8") as f:
                text = await f.read()
            
            metadata = {
                "file_path": str(file_path),
                "element_count": 1
            }
            return text, metadata
        except Exception as e:
            logger.error(f"Failed to parse text file {file_path}: {e}")
            raise


# =============================================================================
# Main Ingestion Pipeline (Option B: Pure Vector)
# =============================================================================

class IngestionPipeline:
    """
    Fast document ingestion: parse → chunk → embed → persist to Milvus.
    
    This is the Option B "Pure Vector" pipeline - no graph extraction or Neo4j.
    Uploads should now take seconds instead of minutes.
    
    Example:
        ```python
        async with IngestionPipeline() as pipeline:
            doc = await pipeline.ingest_document(Path("research.pdf"))
        ```
    """
    
    def __init__(self, settings: Optional[Settings] = None):
        """Initialize pipeline with configuration."""
        self.settings = settings or get_settings()
        
        # Initialize components
        self.chunker = TextChunker(
            chunk_size=self.settings.chunk_size_tokens,
            chunk_overlap=self.settings.chunk_overlap_tokens,
        )
        self.embedding_service = EmbeddingService(self.settings.embedding_model)
        
        # Milvus client (initialized in __aenter__)
        self._milvus_client: Optional[MilvusClient] = None
    
    async def __aenter__(self):
        """Async context manager entry - initialize database connections."""
        # Milvus client (pymilvus MilvusClient is sync but thread-safe)
        self._milvus_client = MilvusClient(uri=self.settings.milvus_uri)
        
        # Ensure Milvus collection exists
        await self._ensure_milvus_collection()
        
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - cleanup connections."""
        if self._milvus_client:
            self._milvus_client.close()
    
    async def _ensure_milvus_collection(self):
        """Create Milvus collection if it doesn't exist and ensure it's loaded."""
        collection_name = self.settings.milvus_collection
        
        try:
            from pymilvus import DataType

            # Check if collection exists
            if not self._milvus_client.has_collection(collection_name):
                logger.info(f"Creating new collection '{collection_name}' with explicit schema")
                
                # Create schema
                schema = MilvusClient.create_schema(
                    auto_id=False,
                    enable_dynamic_field=True,
                )
                schema.add_field(field_name="id", datatype=DataType.VARCHAR, max_length=36, is_primary=True)
                schema.add_field(field_name="vector", datatype=DataType.FLOAT_VECTOR, dim=self.settings.embedding_dimension)
                schema.add_field(field_name="doc_id", datatype=DataType.VARCHAR, max_length=36)
                schema.add_field(field_name="text", datatype=DataType.VARCHAR, max_length=60000)
                schema.add_field(field_name="filename", datatype=DataType.VARCHAR, max_length=512)
                
                # Prepare index parameters
                index_params = self._milvus_client.prepare_index_params()
                index_params.add_index(
                    field_name="vector",
                    metric_type="COSINE",
                    index_type="IVF_FLAT",
                    params={"nlist": 128}
                )
                
                schema.add_field(field_name="project_id", datatype=DataType.VARCHAR, max_length=36)
                
                self._milvus_client.create_collection(
                    collection_name=collection_name,
                    schema=schema,
                    index_params=index_params,
                )
                logger.info(f"Created Milvus collection '{collection_name}' with explicit schema")
            
            # CRITICAL: Load collection into memory for queries to work
            # Without this, queries will fail with "channel not subscribed" errors
            # Run in executor since it's a synchronous blocking call
            try:
                import asyncio
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(
                    None,
                    lambda: self._milvus_client.load_collection(collection_name)
                )
                logger.debug(f"Collection '{collection_name}' loaded into memory")
            except Exception as load_error:
                # Collection might already be loaded, which is fine
                logger.debug(f"Collection load status check: {load_error}")
            
        except MilvusException as e:
            logger.error(f"Milvus collection setup failed: {e}")
            raise
    
    async def ingest_document(self, file_path: Path, project_id: Optional[UUID] = None) -> IngestedDocument:
        """
        Fast ingestion pipeline for a document (Option B: Pure Vector).
        
        Pipeline:
        1. Parse document
        2. Chunk text
        3. Embed chunks
        4. Persist to Milvus
        
        No LLM entity extraction = FAST uploads!
        
        Args:
            file_path: Path to document file (PDF, TXT, MD supported)
            project_id: Optional Project ID for multi-tenancy
            
        Returns:
            IngestedDocument with metadata
            
        Raises:
            IngestionError: If ingestion fails at any stage
        """
        from exceptions import IngestionError
        
        logger.info(f"Starting fast ingestion: {file_path}")
        
        # 1. Create document metadata
        doc = IngestedDocument(
            filename=file_path.name,
            file_size_bytes=file_path.stat().st_size,
            project_id=project_id,
        )
        
        # 2. Parse document
        try:
            text = ""
            if file_path.suffix.lower() == ".pdf":
                text, parse_metadata = await DocumentParser.parse_pdf(file_path)
            elif file_path.suffix.lower() in [".md", ".txt", ".json", ".yaml", ".yml"]:
                text, parse_metadata = await DocumentParser.parse_text(file_path)
            else:
                raise IngestionError(
                    message=f"Unsupported file type: {file_path.suffix}",
                    filename=file_path.name,
                    stage="parsing"
                )
                
            logger.info(f"Parsed {len(text)} characters from {file_path.name}")
        except IngestionError:
            raise
        except Exception as e:
            raise IngestionError(
                message=f"Failed to parse document: {str(e)}",
                doc_id=str(doc.doc_id),
                filename=file_path.name,
                stage="parsing",
                original_error=e
            )
        
        # 3. Chunk text (using async version to avoid blocking event loop)
        try:
            chunks = await self.chunker.chunk_text_async(text, doc.doc_id)
            logger.info(f"Created {len(chunks)} chunks")
        except Exception as e:
            raise IngestionError(
                message=f"Failed to chunk document: {str(e)}",
                doc_id=str(doc.doc_id),
                filename=file_path.name,
                stage="chunking",
                original_error=e
            )
        
        # 4. Embed chunks
        try:
            chunks_with_embeddings = await self._embed_chunks(chunks)
        except Exception as e:
            raise IngestionError(
                message=f"Failed to embed chunks: {str(e)}",
                doc_id=str(doc.doc_id),
                filename=file_path.name,
                stage="embedding",
                original_error=e
            )
        
        # 5. Persist to Milvus vector store (ONLY - no Neo4j!)
        try:
            await self._persist_to_milvus(chunks_with_embeddings, doc)
        except Exception as e:
            raise IngestionError(
                message=f"Failed to persist to Milvus: {str(e)}",
                doc_id=str(doc.doc_id),
                filename=file_path.name,
                stage="milvus_persistence",
                original_error=e
            )
        
        logger.info(f"Fast ingestion complete: {doc.doc_id} ({len(chunks)} chunks)")
        return doc, text
    
    async def _embed_chunks(self, chunks: list[TextChunk]) -> list[TextChunk]:
        """Add embeddings to chunks."""
        embedded_chunks = []
        
        for chunk in chunks:
            embedding = await self.embedding_service.embed_text(chunk.text)
            # Create new chunk with embedding (TextChunk is frozen)
            embedded_chunk = TextChunk(
                chunk_id=chunk.chunk_id,
                doc_id=chunk.doc_id,
                text=chunk.text,
                embedding=embedding,
                position=chunk.position,
                start_char=chunk.start_char,
                end_char=chunk.end_char,
                token_count=chunk.token_count,
            )
            embedded_chunks.append(embedded_chunk)
        
        return embedded_chunks
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
    async def _persist_to_milvus(self, chunks: list[TextChunk], doc: IngestedDocument):
        """
        Persist chunk embeddings to Milvus with document metadata.
        
        Uses upsert to handle re-ingestion.
        """
        if not chunks:
            return
        
        try:
            data = [chunk.to_milvus_dict() for chunk in chunks]
            
            # Add document metadata to each chunk for filtering
            for item in data:
                item["filename"] = doc.filename
                item["upload_date"] = doc.upload_date.isoformat()
                if doc.project_id:
                    item["project_id"] = str(doc.project_id)
            
            self._milvus_client.upsert(
                collection_name=self.settings.milvus_collection,
                data=data,
            )
            logger.debug(f"Persisted {len(chunks)} chunks to Milvus")
            
        except MilvusException as e:
            logger.error(f"Milvus persistence failed: {e}")
            msg = e.message if hasattr(e, 'message') else str(e)
            doc_id = str(chunks[0].doc_id) if chunks else "unknown"
            
            from exceptions import IngestionError
            raise IngestionError(
                message=f"Failed to persist to Milvus: {msg}",
                doc_id=doc_id,
                filename="unknown",
                stage="milvus_persistence",
                original_error=e
            )
        except Exception as e:
            logger.error(f"Milvus persistence failed: {e}")
            raise
    
    async def get_all_sources(self, project_id: Optional[UUID] = None) -> list[dict]:
        """
        Get a list of all ingested documents from Milvus.
        
        Args:
            project_id: Optional filter for multi-tenancy
            
        Returns:
            List of dicts with document metadata.
        """
        try:
            # Build query parameters
            query_params = {
                "collection_name": self.settings.milvus_collection,
                "output_fields": ["doc_id", "filename", "project_id", "upload_date"],
                "limit": 10000,  # Get enough to cover typical usage
                "consistency_level": "Strong",
            }
            
            # Only add filter if project_id is provided
            if project_id:
                query_params["filter"] = f'project_id == "{str(project_id)}"'
            
            results = self._milvus_client.query(**query_params)
            
            # Aggregate by doc_id
            sources_map = {}
            for item in results:
                doc_id = item.get("doc_id")
                if doc_id and doc_id not in sources_map:
                    sources_map[doc_id] = {
                        "id": doc_id,
                        "doc_id": doc_id,  # Add explicit doc_id field
                        "title": item.get("filename", "Unknown"),
                        "filename": item.get("filename", "Unknown"),
                        "uploaded_at": item.get("upload_date", ""),
                        "status": "ready",
                        "chunk_count": 0,
                    }
                if doc_id:
                    sources_map[doc_id]["chunk_count"] += 1
            
            return list(sources_map.values())
            
        except MilvusException as e:
            logger.error(f"Failed to get sources from Milvus: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error getting sources: {e}")
            return []
    
    async def delete_document(self, doc_id: str) -> dict:
        """
        Delete a document and all its chunks from Milvus.
        
        Args:
            doc_id: Document ID to delete
            
        Returns:
            Dict with deletion statistics
        """
        try:
            # Delete all entities with matching doc_id
            filter_expr = f'doc_id == "{doc_id}"'
            
            # First, get the filename so we can delete it from disk
            # We only need one chunk to get the filename
            existing = self._milvus_client.query(
                collection_name=self.settings.milvus_collection,
                filter=filter_expr,
                output_fields=["id", "filename"],
                limit=1, # Just need one to get the filename
            )
            
            if not existing:
                return {"found": False, "chunks_deleted": 0}
            
            filename = existing[0].get("filename")
            
            # Now delete from Milvus
            self._milvus_client.delete(
                collection_name=self.settings.milvus_collection,
                filter=filter_expr,
            )
            

            # Verify deletion from Milvus by querying again
            deleted_check = self._milvus_client.query(
                collection_name=self.settings.milvus_collection,
                filter=filter_expr,
                output_fields=["id"],
                limit=1,
            )
            
            if deleted_check:
                logger.error(f"CRITICAL: Failed to delete doc {doc_id} from Milvus even after delete call!")
                # Don't delete from disk if Milvus deletion failed
                return {"found": True, "chunks_deleted": "failed", "disk_deleted": False, "error": "Milvus deletion verification failed"}

            # Delete file from disk only if Milvus deletion confirmed
            disk_deleted = False
            if filename:
                try:
                    upload_path = Path(self.settings.upload_dir) / filename
                    if upload_path.exists():
                        upload_path.unlink()
                        disk_deleted = True
                        logger.info(f"Deleted file from disk: {upload_path}")
                    else:
                        logger.warning(f"File not found on disk: {upload_path}")
                except Exception as e:
                    logger.error(f"Failed to delete file from disk: {e}")
            
            logger.info(f"Deleted chunks for document {doc_id} (Disk: {disk_deleted})")
            return {"found": True, "chunks_deleted": "verified", "disk_deleted": disk_deleted}
            
        except MilvusException as e:
            logger.error(f"Failed to delete document {doc_id}: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error deleting document: {e}")
            raise
