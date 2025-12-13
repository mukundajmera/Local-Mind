"""
Unit Tests - Reciprocal Rank Fusion Algorithm
==============================================
Mathematical verification of the RRF algorithm in HybridRetriever.
"""

import pytest
from collections import defaultdict


# RRF constant (must match the one in search.py)
RRF_K = 60


class TestRRFAlgorithm:
    """Tests for the Reciprocal Rank Fusion algorithm."""
    
    def test_rrf_formula_basic(self):
        """Test basic RRF score calculation."""
        # RRF formula: score = 1 / (rank + k)
        # For rank 0 with k=60: score = 1/60 ≈ 0.0167
        
        rank = 0
        expected_score = 1 / (rank + RRF_K)
        
        assert abs(expected_score - 0.016666) < 0.001
    
    def test_rrf_score_decreases_with_rank(self):
        """Test that RRF scores decrease as rank increases."""
        scores = [1 / (rank + RRF_K) for rank in range(10)]
        
        # Each score should be less than the previous
        for i in range(1, len(scores)):
            assert scores[i] < scores[i-1]
    
    def test_rrf_fusion_isolated(self):
        """Test RRF fusion logic in isolation without mocks."""
        # Simulated vector results (ranked by similarity)
        vector_ids = ["A", "B", "C", "D"]  # A is rank 0, D is rank 3
        
        # Simulated graph results (ranked by connectivity)
        graph_ids = ["B", "E", "A"]  # B is rank 0, A is rank 2
        
        # Expected: B should rank highest (appears in both at good ranks)
        # A appears in both but at worse ranks overall
        
        vector_weight = 0.5
        graph_weight = 0.5
        
        # Calculate RRF scores
        scores = defaultdict(float)
        
        for rank, doc_id in enumerate(vector_ids):
            scores[doc_id] += vector_weight / (rank + RRF_K)
        
        for rank, doc_id in enumerate(graph_ids):
            scores[doc_id] += graph_weight / (rank + RRF_K)
        
        # Sort by score descending
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        ranked_ids = [doc_id for doc_id, score in ranked]
        
        # B should be first (rank 1 in vector + rank 0 in graph)
        # B_score = 0.5/61 + 0.5/60 = 0.00819 + 0.00833 = 0.01652
        assert ranked_ids[0] == "B", f"Expected B first, got {ranked_ids}"
        
        # A should be second (rank 0 in vector + rank 2 in graph)
        # A_score = 0.5/60 + 0.5/62 = 0.00833 + 0.00806 = 0.01639
        assert ranked_ids[1] == "A", f"Expected A second, got {ranked_ids}"
    
    def test_rrf_with_weights(self):
        """Test that weights affect final ranking."""
        vector_ids = ["A", "B"]  # A is rank 0
        graph_ids = ["B", "A"]   # B is rank 0
        
        # With equal weights, tie should be resolved consistently
        scores_equal = {}
        for rank, doc_id in enumerate(vector_ids):
            scores_equal[doc_id] = scores_equal.get(doc_id, 0) + 0.5 / (rank + RRF_K)
        for rank, doc_id in enumerate(graph_ids):
            scores_equal[doc_id] = scores_equal.get(doc_id, 0) + 0.5 / (rank + RRF_K)
        
        # Both A and B have same score with equal weights
        assert abs(scores_equal["A"] - scores_equal["B"]) < 0.0001
        
        # With vector weight = 0.8, graph weight = 0.2
        # A should win (better vector rank)
        scores_vector_heavy = {}
        for rank, doc_id in enumerate(vector_ids):
            scores_vector_heavy[doc_id] = scores_vector_heavy.get(doc_id, 0) + 0.8 / (rank + RRF_K)
        for rank, doc_id in enumerate(graph_ids):
            scores_vector_heavy[doc_id] = scores_vector_heavy.get(doc_id, 0) + 0.2 / (rank + RRF_K)
        
        assert scores_vector_heavy["A"] > scores_vector_heavy["B"]
    
    def test_rrf_empty_lists(self):
        """Test RRF handles empty input lists."""
        vector_ids = []
        graph_ids = []
        
        scores = defaultdict(float)
        
        for rank, doc_id in enumerate(vector_ids):
            scores[doc_id] += 0.5 / (rank + RRF_K)
        
        for rank, doc_id in enumerate(graph_ids):
            scores[doc_id] += 0.5 / (rank + RRF_K)
        
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        
        assert len(ranked) == 0
    
    def test_rrf_one_empty_list(self):
        """Test RRF when only one source has results."""
        vector_ids = ["A", "B", "C"]
        graph_ids = []
        
        scores = defaultdict(float)
        
        for rank, doc_id in enumerate(vector_ids):
            scores[doc_id] += 0.5 / (rank + RRF_K)
        
        for rank, doc_id in enumerate(graph_ids):
            scores[doc_id] += 0.5 / (rank + RRF_K)
        
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        ranked_ids = [doc_id for doc_id, score in ranked]
        
        # Should maintain original order from vector
        assert ranked_ids == ["A", "B", "C"]
    
    def test_rrf_duplicate_handling(self):
        """Test that duplicates are properly merged."""
        # Same doc in both lists
        vector_ids = ["A", "A", "B"]  # Duplicate A (shouldn't happen in practice)
        graph_ids = ["A"]
        
        scores = defaultdict(float)
        
        for rank, doc_id in enumerate(vector_ids):
            scores[doc_id] += 0.5 / (rank + RRF_K)
        
        for rank, doc_id in enumerate(graph_ids):
            scores[doc_id] += 0.5 / (rank + RRF_K)
        
        # A should have accumulated score from all occurrences
        # This tests that defaultdict properly accumulates
        assert scores["A"] > scores["B"]


class TestHybridRetrieverRRF:
    """Integration tests for HybridRetriever._rrf_fuse method."""
    
    def test_rrf_fuse_with_fixtures(self, sample_search_results):
        """Test actual _rrf_fuse method with fixture data."""
        from services.search import HybridRetriever
        from schemas import SearchResult
        
        vector_results, graph_results = sample_search_results
        
        retriever = HybridRetriever.__new__(HybridRetriever)
        retriever.settings = None  # Not needed for _rrf_fuse
        
        fused = retriever._rrf_fuse(
            vector_results=vector_results,
            graph_results=graph_results,
            vector_weight=0.5,
            graph_weight=0.5,
            k=5,
        )
        
        # Should have max 5 results
        assert len(fused) <= 5
        
        # B should rank high (appears in both)
        chunk_ids = [r.chunk_id for r in fused]
        assert "chunk-B" in chunk_ids
        
        # A should also be present (appears in both)
        assert "chunk-A" in chunk_ids
    
    def test_rrf_fuse_marks_source_correctly(self, sample_search_results):
        """Test that source attribution is correct."""
        from services.search import HybridRetriever
        
        vector_results, graph_results = sample_search_results
        
        retriever = HybridRetriever.__new__(HybridRetriever)
        retriever.settings = None
        
        fused = retriever._rrf_fuse(
            vector_results=vector_results,
            graph_results=graph_results,
            vector_weight=0.5,
            graph_weight=0.5,
            k=10,
        )
        
        # Find results that appear in both
        for result in fused:
            if result.chunk_id in ["chunk-A", "chunk-B"]:
                assert result.source == "both", f"{result.chunk_id} should be 'both'"
            elif result.chunk_id in ["chunk-C", "chunk-D"]:
                assert result.source == "vector"
            elif result.chunk_id == "chunk-E":
                assert result.source == "graph"
    
    def test_rrf_fuse_respects_k_limit(self, sample_search_results):
        """Test that k parameter limits output."""
        from services.search import HybridRetriever
        
        vector_results, graph_results = sample_search_results
        
        retriever = HybridRetriever.__new__(HybridRetriever)
        retriever.settings = None
        
        for k in [1, 2, 3]:
            fused = retriever._rrf_fuse(
                vector_results=vector_results,
                graph_results=graph_results,
                vector_weight=0.5,
                graph_weight=0.5,
                k=k,
            )
            assert len(fused) == k
    
    def test_rrf_fuse_empty_inputs(self):
        """Test RRF with empty inputs doesn't crash."""
        from services.search import HybridRetriever
        
        retriever = HybridRetriever.__new__(HybridRetriever)
        retriever.settings = None
        
        fused = retriever._rrf_fuse(
            vector_results=[],
            graph_results=[],
            vector_weight=0.5,
            graph_weight=0.5,
            k=10,
        )
        
        assert fused == []
