"""
Unit Tests - Pydantic Schema Validation
=======================================
Test strict validation of data models.
"""

import pytest
from pydantic import ValidationError


class TestExtractionResult:
    """Tests for ExtractionResult Pydantic model."""
    
    def test_valid_extraction_result(self):
        """Test that valid data passes validation."""
        from schemas import ExtractionResult, GraphEntity, GraphRelationship
        
        result = ExtractionResult(
            entities=[
                GraphEntity(name="Test Entity", type="CONCEPT", description="A test")
            ],
            relationships=[
                GraphRelationship(
                    source="Test Entity",
                    target="Another Entity",
                    type="RELATED_TO",
                    weight=0.8,
                )
            ],
        )
        
        assert result.entity_count == 1
        assert result.relationship_count == 1
    
    def test_empty_extraction_result(self):
        """Test that empty lists are valid."""
        from schemas import ExtractionResult
        
        result = ExtractionResult(entities=[], relationships=[])
        
        assert result.entity_count == 0
        assert result.relationship_count == 0
    
    def test_entity_missing_name_fails(self):
        """Test that entity without name fails validation."""
        from schemas import GraphEntity
        
        with pytest.raises(ValidationError) as exc_info:
            GraphEntity(type="PERSON")  # Missing required 'name'
        
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("name",) for e in errors)
    
    def test_entity_missing_type_fails(self):
        """Test that entity without type fails validation."""
        from schemas import GraphEntity
        
        with pytest.raises(ValidationError) as exc_info:
            GraphEntity(name="Test")  # Missing required 'type'
        
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("type",) for e in errors)
    
    def test_relationship_weight_bounds(self):
        """Test relationship weight must be 0-1."""
        from schemas import GraphRelationship
        
        # Valid weight
        rel = GraphRelationship(
            source="A", target="B", type="TEST", weight=0.5
        )
        assert rel.weight == 0.5
        
        # Invalid weight > 1
        with pytest.raises(ValidationError):
            GraphRelationship(
                source="A", target="B", type="TEST", weight=1.5
            )
        
        # Invalid weight < 0
        with pytest.raises(ValidationError):
            GraphRelationship(
                source="A", target="B", type="TEST", weight=-0.1
            )
    
    def test_extraction_result_merge(self):
        """Test merging two extraction results."""
        from schemas import ExtractionResult, GraphEntity
        
        result1 = ExtractionResult(
            entities=[GraphEntity(name="Entity1", type="TYPE1")],
            relationships=[],
        )
        result2 = ExtractionResult(
            entities=[GraphEntity(name="Entity2", type="TYPE2")],
            relationships=[],
        )
        
        merged = result1.merge_with(result2)
        
        assert merged.entity_count == 2
        assert merged.entities[0].name == "Entity1"
        assert merged.entities[1].name == "Entity2"


class TestTextChunk:
    """Tests for TextChunk model."""
    
    def test_text_chunk_creation(self):
        """Test valid TextChunk creation."""
        from uuid import uuid4
        from schemas import TextChunk
        
        doc_id = uuid4()
        chunk = TextChunk(
            doc_id=doc_id,
            text="Sample text content",
            position=0,
        )
        
        assert chunk.doc_id == doc_id
        assert chunk.text == "Sample text content"
        assert chunk.position == 0
    
    def test_text_chunk_to_milvus_dict(self):
        """Test conversion to Milvus format."""
        from uuid import uuid4
        from schemas import TextChunk
        
        doc_id = uuid4()
        chunk = TextChunk(
            doc_id=doc_id,
            text="Test",
            position=5,
            embedding=[0.1, 0.2, 0.3],
        )
        
        milvus_dict = chunk.to_milvus_dict()
        
        assert "id" in milvus_dict
        assert milvus_dict["doc_id"] == str(doc_id)
        assert milvus_dict["text"] == "Test"
        assert milvus_dict["embedding"] == [0.1, 0.2, 0.3]
        assert milvus_dict["position"] == 5
    
    def test_text_chunk_empty_text_fails(self):
        """Test that empty text fails validation."""
        from uuid import uuid4
        from schemas import TextChunk
        
        with pytest.raises(ValidationError):
            TextChunk(
                doc_id=uuid4(),
                text="",  # Empty text should fail
                position=0,
            )


class TestGraphEntity:
    """Tests for GraphEntity normalized name property."""
    
    def test_normalized_name(self):
        """Test normalized_name property."""
        from schemas import GraphEntity
        
        entity = GraphEntity(
            name="  Albert Einstein  ",
            type="PERSON",
        )
        
        assert entity.normalized_name == "albert einstein"
    
    def test_normalized_name_case_insensitive(self):
        """Test normalized name is lowercase."""
        from schemas import GraphEntity
        
        entity1 = GraphEntity(name="EINSTEIN", type="PERSON")
        entity2 = GraphEntity(name="einstein", type="PERSON")
        
        assert entity1.normalized_name == entity2.normalized_name
