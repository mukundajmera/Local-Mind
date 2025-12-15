"""
Sovereign Cognitive Engine - Ingestion Pipeline
================================================
Asynchronous document ingestion with chunking, embedding, and graph extraction.
"""

import hashlib
import logging
from pathlib import Path
from typing import AsyncGenerator, Optional
from uuid import UUID, uuid4

from neo4j import AsyncGraphDatabase, AsyncDriver
from neo4j.exceptions import Neo4jError
from pymilvus import MilvusClient, MilvusException
from tenacity import retry, stop_after_attempt, wait_exponential

# Third-party libraries
from sentence_transformers import SentenceTransformer
from langchain_ollama import ChatOllama
from langchain_community.chat_models import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser

from config import Settings, get_settings
from schemas import (
    ExtractionResult,
    GraphEntity,
    GraphRelationship,
    IngestedDocument,
    TextChunk,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Stub Services (to be implemented with actual models)
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
            lambda: self._get_model().encode(text, convert_to_numpy=False)
        )
        return embedding
    
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple texts in batch."""
        import asyncio
        loop = asyncio.get_event_loop()
        
        embeddings = await loop.run_in_executor(
            None,
            lambda: self._get_model().encode(texts, convert_to_numpy=False)
        )
        return embeddings


class LLMService:
    """
    LLM service for entity/relationship extraction using Ollama or OpenAI/LM Studio.
    """
    
    def __init__(self, model: str = "llama3.2", base_url: str = "http://localhost:11434", provider: str = "ollama"):
        self.model = model
        self.base_url = base_url
        self.provider = provider
        self._llm = None
        
    def _get_llm(self):
        if self._llm is None:
            if self.provider == "lmstudio" or self.provider == "openai":
                logger.info(f"Initializing ChatOpenAI for provided: {self.provider} at {self.base_url}")
                self._llm = ChatOpenAI(
                    model=self.model,
                    base_url=self.base_url,
                    api_key="not-needed",
                    temperature=0,
                )
            else:
                logger.info(f"Initializing ChatOllama for provider: {self.provider} at {self.base_url}")
                self._llm = ChatOllama(
                    model=self.model,
                    base_url=self.base_url,
                    temperature=0,
                    format="json" # Important for structured output resilience
                )
        return self._llm
    
    async def extract_entities(self, chunk_text: str, chunk_id: str) -> ExtractionResult:
        """
        Extract entities and relationships from text chunk.
        """
        llm = self._get_llm()
        
        # We use a Pydantic parser to ensure valid JSON structure matches our schema
        parser = PydanticOutputParser(pydantic_object=ExtractionResult)
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are an expert knowledge graph extractor. Extract entities and relationships from the text. "
                       "Return ONLY JSON matching the requested schema. "
                       "\n{format_instructions}"),
            ("user", "Text chunk ({chunk_id}):\n{text}")
        ])
        
        chain = prompt | llm | parser
        
        try:
            result = await chain.ainvoke({
                "text": chunk_text,
                "chunk_id": chunk_id,
                "format_instructions": parser.get_format_instructions()
            })
            
            # Post-process to ensure chunk_ids are set (LLM might miss this)
            for entity in result.entities:
                if not entity.chunk_ids:
                    entity.chunk_ids = [chunk_id]
            for rel in result.relationships:
                if not rel.chunk_ids:
                    rel.chunk_ids = [chunk_id]
                    
            return result
            
        except Exception as e:
            logger.error(f"LLM extraction failed for chunk {chunk_id}: {e}")
            # Return empty result on failure to allow pipeline to continue
            return ExtractionResult(entities=[], relationships=[])


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
            Uses `unstructured` library for parsing.
            Install with: pip install unstructured[pdf]
        """
        try:
            from unstructured.partition.pdf import partition_pdf
            
            # partition_pdf is sync, run in executor for async
            import asyncio
            loop = asyncio.get_event_loop()
            elements = await loop.run_in_executor(
                None,
                lambda: partition_pdf(str(file_path))
            )
            
            # Combine all elements into text
            text = "\n\n".join(str(el) for el in elements)
            
            metadata = {
                "element_count": len(elements),
                "file_path": str(file_path),
            }
            
            return text, metadata
            
        except ImportError:
            logger.error("unstructured[pdf] not installed. Run: pip install unstructured[pdf]")
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
# Main Ingestion Pipeline
# =============================================================================

class IngestionPipeline:
    """
    Orchestrates document ingestion: parse → chunk → embed → extract → persist.
    
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
        self.llm_service = LLMService(
            model=self.settings.llm_model,
            base_url=self.settings.llm_base_url or "",
            provider=self.settings.llm_provider,
        )
        
        # Database clients (initialized in __aenter__)
        self._neo4j_driver: Optional[AsyncDriver] = None
        self._milvus_client: Optional[MilvusClient] = None
    
    async def __aenter__(self):
        """Async context manager entry - initialize database connections."""
        # Neo4j async driver
        self._neo4j_driver = AsyncGraphDatabase.driver(
            self.settings.neo4j_uri,
            auth=(self.settings.neo4j_user, self.settings.neo4j_password),
        )
        
        # Milvus client (pymilvus MilvusClient is sync but thread-safe)
        self._milvus_client = MilvusClient(uri=self.settings.milvus_uri)
        
        # Ensure Milvus collection exists
        await self._ensure_milvus_collection()
        
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - cleanup connections."""
        if self._neo4j_driver:
            await self._neo4j_driver.close()
        if self._milvus_client:
            self._milvus_client.close()
    
    async def _ensure_milvus_collection(self):
        """Create Milvus collection if it doesn't exist."""
        collection_name = self.settings.milvus_collection
        
        try:
            # Check if collection exists
            if self._milvus_client.has_collection(collection_name):
                logger.info(f"Milvus collection '{collection_name}' exists")
                return
            
            # Create collection with schema
            from pymilvus import DataType
            
            self._milvus_client.create_collection(
                collection_name=collection_name,
                dimension=self.settings.embedding_dimension,
                metric_type="COSINE",
                id_type=DataType.VARCHAR,
                max_length=36,  # UUID length
            )
            logger.info(f"Created Milvus collection '{collection_name}'")
            
        except MilvusException as e:
            logger.error(f"Milvus collection setup failed: {e}")
            raise
    
    async def ingest_document(self, file_path: Path) -> IngestedDocument:
        """
        Full ingestion pipeline for a document.
        
        Args:
            file_path: Path to document file (PDF supported)
            
        Returns:
            IngestedDocument with metadata
            
        Raises:
            IngestionError: If ingestion fails at any stage
        """
        from exceptions import IngestionError
        
        logger.info(f"Starting ingestion: {file_path}")
        
        # 1. Create document metadata
        doc = IngestedDocument(
            filename=file_path.name,
            file_size_bytes=file_path.stat().st_size,
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
        
        # 3. Chunk text
        try:
            chunks = self.chunker.chunk_text(text, doc.doc_id)
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
        
        # 5. Extract entities and relationships from each chunk
        # IMPORTANT: Continue on individual chunk failures to avoid losing entire document
        all_entities: list[GraphEntity] = []
        all_relationships: list[GraphRelationship] = []
        extraction_errors: list[str] = []
        
        for chunk in chunks_with_embeddings:
            try:
                extraction = await self.llm_service.extract_entities(
                    chunk.text,
                    str(chunk.chunk_id),
                )
                all_entities.extend(extraction.entities)
                all_relationships.extend(extraction.relationships)
            except Exception as e:
                # Log error but continue processing remaining chunks
                error_msg = f"Extraction failed for chunk {chunk.chunk_id}: {e}"
                logger.warning(error_msg)
                extraction_errors.append(error_msg)
                continue
        
        if extraction_errors:
            logger.warning(f"Entity extraction had {len(extraction_errors)} failures out of {len(chunks)} chunks")
        
        logger.info(f"Extracted {len(all_entities)} entities, {len(all_relationships)} relationships")
        
        # 6. Persist to vector store
        try:
            await self._persist_to_milvus(chunks_with_embeddings)
        except Exception as e:
            raise IngestionError(
                message=f"Failed to persist to Milvus: {str(e)}",
                doc_id=str(doc.doc_id),
                filename=file_path.name,
                stage="milvus_persistence",
                original_error=e
            )
        
        # 7. Persist to graph store
        try:
            await self._persist_to_neo4j(doc, chunks_with_embeddings, all_entities, all_relationships)
        except Exception as e:
            raise IngestionError(
                message=f"Failed to persist to Neo4j: {str(e)}",
                doc_id=str(doc.doc_id),
                filename=file_path.name,
                stage="neo4j_persistence",
                original_error=e
            )
        
        logger.info(f"Ingestion complete: {doc.doc_id}")
        return doc
    
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
    async def _persist_to_milvus(self, chunks: list[TextChunk]):
        """
        Persist chunk embeddings to Milvus.
        
        Uses upsert to handle re-ingestion.
        """
        if not chunks:
            return
        
        try:
            data = [chunk.to_milvus_dict() for chunk in chunks]
            
            self._milvus_client.upsert(
                collection_name=self.settings.milvus_collection,
                data=data,
            )
            logger.debug(f"Persisted {len(chunks)} chunks to Milvus")
            
        except MilvusException as e:
            logger.error(f"Milvus persistence failed: {e}")
            # Extract clean message if available
            msg = e.message if hasattr(e, 'message') else str(e)
            
            # Get context from first chunk if available
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
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
    async def _persist_to_neo4j(
        self,
        doc: IngestedDocument,
        chunks: list[TextChunk],
        entities: list[GraphEntity],
        relationships: list[GraphRelationship],
    ):
        """
        Persist document, chunks, entities, and relationships to Neo4j.
        
        Uses MERGE to prevent duplicates when re-ingesting the same document.
        Uses UNWIND for batch operations to minimize database round-trips.
        
        Graph Schema:
            (Document)-[:HAS_CHUNK]->(Chunk)
            (Chunk)-[:MENTIONS]->(Entity)
            (Entity)-[relationship_type]->(Entity)
            
        Performance: Uses UNWIND pattern to batch operations.
        For 1000 chunks, this reduces from 1000+ queries to 4 queries.
        """
        if not self._neo4j_driver:
            raise RuntimeError("Neo4j driver not initialized. Use async context manager.")
        
        async with self._neo4j_driver.session() as session:
            try:
                # 1. Create Document node
                await session.run(
                    """
                    MERGE (d:Document {id: $doc_id})
                    SET d.filename = $filename,
                        d.upload_date = datetime($upload_date),
                        d.file_size_bytes = $file_size
                    """,
                    doc_id=str(doc.doc_id),
                    filename=doc.filename,
                    upload_date=doc.upload_date.isoformat(),
                    file_size=doc.file_size_bytes,
                )
                
                # 2. BATCH: Create all Chunk nodes and link to Document
                # Using UNWIND for O(1) queries instead of O(n)
                if chunks:
                    chunk_data = [
                        {
                            "chunk_id": str(c.chunk_id),
                            "text": c.text[:1000],  # Truncate for graph storage
                            "position": c.position,
                            "token_count": c.token_count,
                        }
                        for c in chunks
                    ]
                    await session.run(
                        """
                        MATCH (d:Document {id: $doc_id})
                        UNWIND $chunks AS chunk
                        MERGE (c:Chunk {id: chunk.chunk_id})
                        SET c.text = chunk.text,
                            c.position = chunk.position,
                            c.token_count = chunk.token_count
                        MERGE (d)-[:HAS_CHUNK]->(c)
                        """,
                        doc_id=str(doc.doc_id),
                        chunks=chunk_data,
                    )
                
                # 3. BATCH: Create all Entity nodes
                # Uses MERGE with normalized name to deduplicate across documents
                if entities:
                    entity_data = [
                        {
                            "normalized_name": e.normalized_name,
                            "name": e.name,
                            "type": e.type,
                            "description": e.description,
                            "chunk_ids": e.chunk_ids,
                        }
                        for e in entities
                    ]
                    await session.run(
                        """
                        UNWIND $entities AS entity
                        MERGE (e:Entity {normalized_name: entity.normalized_name})
                        ON CREATE SET
                            e.name = entity.name,
                            e.type = entity.type,
                            e.description = entity.description,
                            e.chunk_ids = entity.chunk_ids
                        ON MATCH SET
                            e.chunk_ids = e.chunk_ids + entity.chunk_ids
                        """,
                        entities=entity_data,
                    )
                    
                    # BATCH: Link entities to their source chunks
                    # Flatten the entity-chunk relationships
                    mention_links = [
                        {"chunk_id": cid, "normalized_name": e.normalized_name}
                        for e in entities
                        for cid in e.chunk_ids
                    ]
                    if mention_links:
                        await session.run(
                            """
                            UNWIND $links AS link
                            MATCH (c:Chunk {id: link.chunk_id})
                            MATCH (e:Entity {normalized_name: link.normalized_name})
                            MERGE (c)-[:MENTIONS]->(e)
                            """,
                            links=mention_links,
                        )
                
                # 4. BATCH: Create all Relationship edges between entities
                if relationships:
                    rel_data = [
                        {
                            "source_name": r.source.strip().lower(),
                            "target_name": r.target.strip().lower(),
                            "rel_type": r.type,
                            "weight": r.weight,
                            "chunk_ids": r.chunk_ids,
                        }
                        for r in relationships
                    ]
                    await session.run(
                        """
                        UNWIND $rels AS rel
                        MATCH (source:Entity {normalized_name: rel.source_name})
                        MATCH (target:Entity {normalized_name: rel.target_name})
                        MERGE (source)-[r:RELATED_TO {type: rel.rel_type}]->(target)
                        SET r.weight = rel.weight,
                            r.chunk_ids = rel.chunk_ids
                        """,
                        rels=rel_data,
                    )
                
                logger.debug(f"Persisted graph: {len(chunks)} chunks, {len(entities)} entities, {len(relationships)} relationships")
                
            except Neo4jError as e:
                logger.error(f"Neo4j persistence failed: {e}")
                raise

