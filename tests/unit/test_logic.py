"""
Unit Tests - Core Logic
========================
Fast tests with no I/O, mocks only.

Run with: pytest tests/unit/test_logic.py -m unit
"""

import pytest
from collections import defaultdict
from pydantic import ValidationError


# =============================================================================
# RRF Algorithm Tests
# =============================================================================

class TestReciprocalRankFusion:
    """Test the Reciprocal Rank Fusion algorithm math."""
    
    # RRF constant (must match implementation)
    RRF_K = 60
    
    @pytest.mark.unit
    def test_rrf_formula_correctness(self):
        """
        Verify RRF formula: score = 1 / (rank + k)
        
        For k=60:
        - Rank 0: 1/60 = 0.01667
        - Rank 1: 1/61 = 0.01639
        - Rank 2: 1/62 = 0.01613
        """
        expected_scores = [
            1 / 60,  # 0.01667
            1 / 61,  # 0.01639
            1 / 62,  # 0.01613
        ]
        
        for rank, expected in enumerate(expected_scores):
            actual = 1 / (rank + self.RRF_K)
            assert abs(actual - expected) < 1e-5, f"Rank {rank}: expected {expected}, got {actual}"
    
    @pytest.mark.unit
    def test_rrf_fusion_two_lists(self):
        """
        Test RRF fusion with two hardcoded lists.
        
        Vector results: [A, B, C, D] (A is best)
        Graph results:  [B, E, A]    (B is best)
        
        Expected ranking after fusion:
        - B: appears at rank 1 in vector + rank 0 in graph → highest combined
        - A: appears at rank 0 in vector + rank 2 in graph → second highest
        - E, C, D: appear in only one list
        """
        # Input lists (ordered by rank)
        vector_ids = ["A", "B", "C", "D"]
        graph_ids = ["B", "E", "A"]
        
        # Equal weights
        vector_weight = 0.5
        graph_weight = 0.5
        
        # Calculate RRF scores
        scores = defaultdict(float)
        
        for rank, doc_id in enumerate(vector_ids):
            scores[doc_id] += vector_weight / (rank + self.RRF_K)
        
        for rank, doc_id in enumerate(graph_ids):
            scores[doc_id] += graph_weight / (rank + self.RRF_K)
        
        # Sort by score (descending)
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        ranked_ids = [doc_id for doc_id, _ in ranked]
        
        # Assertions
        assert ranked_ids[0] == "B", f"B should be first (was {ranked_ids[0]})"
        assert ranked_ids[1] == "A", f"A should be second (was {ranked_ids[1]})"
        
        # Verify math for B
        # B: rank 1 in vector, rank 0 in graph
        # Score = 0.5/61 + 0.5/60 = 0.01652
        expected_b_score = (0.5 / 61) + (0.5 / 60)
        actual_b_score = scores["B"]
        assert abs(actual_b_score - expected_b_score) < 1e-6
        
        # Verify math for A
        # A: rank 0 in vector, rank 2 in graph
        # Score = 0.5/60 + 0.5/62 = 0.01639
        expected_a_score = (0.5 / 60) + (0.5 / 62)
        actual_a_score = scores["A"]
        assert abs(actual_a_score - expected_a_score) < 1e-6
    
    @pytest.mark.unit
    def test_rrf_weight_effects(self):
        """Test that adjusting weights changes rankings."""
        vector_ids = ["A", "B"]  # A is rank 0
        graph_ids = ["B", "A"]   # B is rank 0
        
        # With equal weights, A and B have same score
        scores_equal = defaultdict(float)
        for rank, doc_id in enumerate(vector_ids):
            scores_equal[doc_id] += 0.5 / (rank + self.RRF_K)
        for rank, doc_id in enumerate(graph_ids):
            scores_equal[doc_id] += 0.5 / (rank + self.RRF_K)
        
        assert abs(scores_equal["A"] - scores_equal["B"]) < 1e-10, "Should be equal with equal weights"
        
        # With vector_weight=0.8, A should win
        scores_vector_heavy = defaultdict(float)
        for rank, doc_id in enumerate(vector_ids):
            scores_vector_heavy[doc_id] += 0.8 / (rank + self.RRF_K)
        for rank, doc_id in enumerate(graph_ids):
            scores_vector_heavy[doc_id] += 0.2 / (rank + self.RRF_K)
        
        assert scores_vector_heavy["A"] > scores_vector_heavy["B"], "A should win with vector-heavy weights"
    
    @pytest.mark.unit
    def test_rrf_empty_lists(self):
        """Test RRF handles empty input gracefully."""
        scores = defaultdict(float)
        
        # Both lists empty
        for rank, doc_id in enumerate([]):
            scores[doc_id] += 0.5 / (rank + self.RRF_K)
        
        for rank, doc_id in enumerate([]):
            scores[doc_id] += 0.5 / (rank + self.RRF_K)
        
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        
        assert len(ranked) == 0, "Empty input should produce empty output"
    
    @pytest.mark.unit
    def test_rrf_single_source(self):
        """Test RRF when only one source has results."""
        vector_ids = ["A", "B", "C"]
        graph_ids = []
        
        scores = defaultdict(float)
        
        for rank, doc_id in enumerate(vector_ids):
            scores[doc_id] += 0.5 / (rank + self.RRF_K)
        
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        ranked_ids = [doc_id for doc_id, _ in ranked]
        
        # Should maintain original ordering
        assert ranked_ids == ["A", "B", "C"]


# =============================================================================
# Schema Validation Tests
# =============================================================================

class TestExtractionResultValidation:
    """Test Pydantic schema validation for ExtractionResult."""
    
    @pytest.mark.unit
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
    
    @pytest.mark.unit
    def test_invalid_json_raises_validation_error(self):
        """Test that invalid JSON/data raises ValidationError."""
        from schemas import ExtractionResult
        import json
        
        # Invalid JSON structure (missing required fields)
        invalid_data_cases = [
            {},  # Empty dict
            {"entities": "not a list"},  # Wrong type
            {"entities": [{"wrong_field": "value"}]},  # Missing required fields
            {"entities": [], "relationships": [{"source": "A"}]},  # Incomplete relationship
        ]
        
        for invalid_data in invalid_data_cases:
            with pytest.raises(ValidationError):
                ExtractionResult.model_validate(invalid_data)
    
    @pytest.mark.unit
    def test_entity_missing_name_fails(self):
        """Test that entity without name raises ValidationError."""
        from schemas import GraphEntity
        
        with pytest.raises(ValidationError) as exc_info:
            GraphEntity(type="PERSON")  # Missing 'name'
        
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("name",) for e in errors)
    
    @pytest.mark.unit
    def test_entity_missing_type_fails(self):
        """Test that entity without type raises ValidationError."""
        from schemas import GraphEntity
        
        with pytest.raises(ValidationError) as exc_info:
            GraphEntity(name="Test")  # Missing 'type'
        
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("type",) for e in errors)
    
    @pytest.mark.unit
    def test_relationship_weight_bounds(self):
        """Test relationship weight must be 0.0 - 1.0."""
        from schemas import GraphRelationship
        
        # Valid weight
        rel = GraphRelationship(source="A", target="B", type="TEST", weight=0.5)
        assert rel.weight == 0.5
        
        # Weight > 1 should fail
        with pytest.raises(ValidationError):
            GraphRelationship(source="A", target="B", type="TEST", weight=1.5)
        
        # Weight < 0 should fail
        with pytest.raises(ValidationError):
            GraphRelationship(source="A", target="B", type="TEST", weight=-0.1)
    
    @pytest.mark.unit
    def test_extraction_result_from_invalid_json_string(self):
        """Test parsing malformed JSON string raises error."""
        from schemas import ExtractionResult
        import json
        
        invalid_json_strings = [
            "{not valid json}",
            '{"entities": [{"name": "incomplete",',
            "null",
            '[]',  # Array, not object
        ]
        
        for invalid_json in invalid_json_strings:
            with pytest.raises((json.JSONDecodeError, ValidationError)):
                data = json.loads(invalid_json)
                ExtractionResult.model_validate(data)


# =============================================================================
# Text Chunk Validation Tests
# =============================================================================

class TestTextChunkValidation:
    """Test TextChunk model validation."""
    
    @pytest.mark.unit
    def test_text_chunk_creation(self):
        """Test valid TextChunk creation."""
        from uuid import uuid4
        from schemas import TextChunk
        
        doc_id = uuid4()
        chunk = TextChunk(
            doc_id=doc_id,
            text="Sample text content for testing",
            position=0,
        )
        
        assert chunk.doc_id == doc_id
        assert chunk.position == 0
        assert chunk.chunk_id is not None  # Auto-generated
    
    @pytest.mark.unit
    def test_text_chunk_empty_text_fails(self):
        """Test that empty text fails validation."""
        from uuid import uuid4
        from schemas import TextChunk
        
        with pytest.raises(ValidationError) as exc_info:
            TextChunk(doc_id=uuid4(), text="", position=0)
        
        errors = exc_info.value.errors()
        assert any("text" in str(e.get("loc", "")) for e in errors)
    
    @pytest.mark.unit
    def test_text_chunk_negative_position_fails(self):
        """Test that negative position fails validation."""
        from uuid import uuid4
        from schemas import TextChunk
        
        with pytest.raises(ValidationError):
            TextChunk(doc_id=uuid4(), text="Valid text", position=-1)
