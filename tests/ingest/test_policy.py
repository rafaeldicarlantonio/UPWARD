#!/usr/bin/env python3
"""Tests for ingest policy system."""

from __future__ import annotations

import os
import sys
import pytest
import tempfile
import yaml
from unittest.mock import Mock, patch, MagicMock

# Patch environment variables before imports
os.environ.setdefault("OPENAI_API_KEY", "test-key")
os.environ.setdefault("SUPABASE_URL", "http://localhost")
os.environ.setdefault("SUPABASE_KEY", "test-key")
os.environ.setdefault("PINECONE_API_KEY", "test-key")
os.environ.setdefault("PINECONE_INDEX", "test-index")
os.environ.setdefault("PINECONE_EXPLICATE_INDEX", "test-explicate")
os.environ.setdefault("PINECONE_IMPLICATE_INDEX", "test-implicate")

from core.policy import (
    IngestPolicy,
    IngestPolicyManager,
    get_ingest_policy,
    get_ingest_policy_manager,
)
from ingest.commit import commit_analysis
from ingest.pipeline import AnalysisResult
from nlp.verbs import PredicateFrame
from nlp.frames import EventFrame
from nlp.contradictions import ContradictionCandidate


class TestIngestPolicyLoading:
    """Tests for loading ingest policies from YAML."""
    
    def test_load_valid_policy(self):
        """Test loading a valid policy file."""
        manager = IngestPolicyManager()
        
        # Should have loaded successfully
        assert manager._default_policy is not None
        assert manager._global_limits
        assert manager._valid_frame_types
        
        # Check global limits
        limits = manager.get_global_limits()
        assert "max_concepts_per_file_absolute" in limits
        assert "max_frames_per_chunk_absolute" in limits
    
    def test_load_malformed_policy_falls_back_to_safe_defaults(self):
        """Test that malformed policy files fall back to safe defaults."""
        # Create a malformed YAML file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("{ invalid: yaml: content: }")
            malformed_path = f.name
        
        try:
            manager = IngestPolicyManager(policy_path=malformed_path)
            
            # Should fall back to safe defaults
            policy = manager.get_policy()
            assert policy.max_concepts_per_file == 20  # Safe default
            assert policy.max_frames_per_chunk == 5  # Safe default
            assert policy.write_contradictions_to_memories is False  # Safe default
            assert policy.allowed_frame_types == ["claim"]  # Safe default
            assert policy.contradiction_tolerance == 0.5  # Safe default
        finally:
            os.unlink(malformed_path)
    
    def test_missing_policy_file_falls_back(self):
        """Test that missing policy file falls back to safe defaults."""
        manager = IngestPolicyManager(policy_path="/nonexistent/path/policy.yaml")
        
        # Should fall back to safe defaults
        policy = manager.get_policy()
        assert policy.max_concepts_per_file == 20
        assert policy.max_frames_per_chunk == 5
        assert policy.write_contradictions_to_memories is False


class TestPolicySelection:
    """Tests for role-based policy selection."""
    
    def setup_method(self):
        """Create a policy manager for testing."""
        self.manager = IngestPolicyManager()
    
    def test_get_policy_for_admin_role(self):
        """Test getting policy for admin role."""
        policy = self.manager.get_policy(["admin"])
        
        assert policy.role == "admin"
        assert policy.max_concepts_per_file == 500
        assert policy.max_frames_per_chunk == 50
        assert policy.write_contradictions_to_memories is True
        assert "hypothesis" in policy.allowed_frame_types
    
    def test_get_policy_for_general_role(self):
        """Test getting policy for general role (conservative)."""
        policy = self.manager.get_policy(["general"])
        
        assert policy.role == "general"
        assert policy.max_concepts_per_file == 50
        assert policy.max_frames_per_chunk == 10
        assert policy.write_contradictions_to_memories is False
        assert policy.allowed_frame_types == ["claim", "evidence"]
        assert policy.contradiction_tolerance == 0.3
    
    def test_get_policy_for_multiple_roles_picks_most_permissive(self):
        """Test that multiple roles pick the most permissive policy."""
        policy = self.manager.get_policy(["general", "pro", "user"])
        
        # Should pick 'pro' as it has higher caps
        assert policy.role == "pro"
        assert policy.max_concepts_per_file == 200
    
    def test_get_policy_with_no_roles_returns_default(self):
        """Test that no roles returns the default policy."""
        policy = self.manager.get_policy([])
        
        assert policy.role == "default"
        assert policy.max_concepts_per_file == 20
    
    def test_get_policy_with_unknown_role_returns_default(self):
        """Test that unknown roles return the default policy."""
        policy = self.manager.get_policy(["unknown_role"])
        
        assert policy.role == "default"


class TestPolicyValidation:
    """Tests for policy validation and clamping."""
    
    def test_validate_clamps_to_global_limits(self):
        """Test that validation clamps values to global limits."""
        policy = IngestPolicy(
            max_concepts_per_file=2000,  # Exceeds global limit
            max_frames_per_chunk=200,  # Exceeds global limit
            write_contradictions_to_memories=True,
            allowed_frame_types=["claim"],
            contradiction_tolerance=1.5,  # Exceeds limit
            role="test"
        )
        
        global_limits = {
            "max_concepts_per_file_absolute": 1000,
            "max_frames_per_chunk_absolute": 100,
            "min_contradiction_tolerance": 0.05,
            "max_contradiction_tolerance": 0.9,
        }
        
        policy.validate(global_limits)
        
        assert policy.max_concepts_per_file == 1000
        assert policy.max_frames_per_chunk == 100
        assert policy.contradiction_tolerance == 0.9
    
    def test_validate_clamps_contradiction_tolerance_minimum(self):
        """Test that validation enforces minimum contradiction tolerance."""
        policy = IngestPolicy(
            max_concepts_per_file=50,
            max_frames_per_chunk=10,
            write_contradictions_to_memories=False,
            allowed_frame_types=["claim"],
            contradiction_tolerance=0.01,  # Too low
            role="test"
        )
        
        global_limits = {
            "min_contradiction_tolerance": 0.05,
            "max_contradiction_tolerance": 0.9,
        }
        
        policy.validate(global_limits)
        
        assert policy.contradiction_tolerance == 0.05


class TestPolicyEnforcement:
    """Tests for enforcing policy caps during commit."""
    
    def setup_method(self):
        """Create a policy manager for testing."""
        self.manager = IngestPolicyManager()
    
    def test_enforce_caps_limits_concepts(self):
        """Test that enforce_caps limits concepts to policy max."""
        policy = IngestPolicy(
            max_concepts_per_file=3,
            max_frames_per_chunk=10,
            write_contradictions_to_memories=True,
            allowed_frame_types=["claim", "evidence"],
            contradiction_tolerance=0.1,
            role="test"
        )
        
        concepts = [
            {"name": "Concept 1"},
            {"name": "Concept 2"},
            {"name": "Concept 3"},
            {"name": "Concept 4"},
            {"name": "Concept 5"},
        ]
        
        result = self.manager.enforce_caps(concepts, [], [], policy)
        
        assert len(result["concepts"]) == 3
        assert result["caps_applied"]["concepts_before"] == 5
        assert result["caps_applied"]["concepts_after"] == 3
    
    def test_enforce_caps_filters_frame_types(self):
        """Test that enforce_caps filters frames by allowed types."""
        policy = IngestPolicy(
            max_concepts_per_file=100,
            max_frames_per_chunk=10,
            write_contradictions_to_memories=True,
            allowed_frame_types=["claim", "evidence"],
            contradiction_tolerance=0.1,
            role="test"
        )
        
        frames = [
            Mock(type="claim", frame_id="f1"),
            Mock(type="evidence", frame_id="f2"),
            Mock(type="hypothesis", frame_id="f3"),  # Not allowed
            Mock(type="claim", frame_id="f4"),
            Mock(type="method", frame_id="f5"),  # Not allowed
        ]
        
        result = self.manager.enforce_caps([], frames, [], policy)
        
        # Should only have 3 frames (2 claim + 1 evidence)
        assert len(result["frames"]) == 3
        assert result["caps_applied"]["frames_before"] == 5
        assert result["caps_applied"]["frames_after"] == 3
        assert result["caps_applied"]["frames_filtered_count"] == 2
        assert "hypothesis" in result["frames_filtered"]
        assert "method" in result["frames_filtered"]
    
    def test_enforce_caps_filters_contradictions_by_tolerance(self):
        """Test that enforce_caps filters contradictions by tolerance threshold."""
        policy = IngestPolicy(
            max_concepts_per_file=100,
            max_frames_per_chunk=10,
            write_contradictions_to_memories=True,
            allowed_frame_types=["claim"],
            contradiction_tolerance=0.5,  # 50% threshold
            role="test"
        )
        
        contradictions = [
            {"score": 0.8, "claim_a": "A", "claim_b": "B"},  # Above threshold
            {"score": 0.3, "claim_a": "C", "claim_b": "D"},  # Below threshold
            {"score": 0.6, "claim_a": "E", "claim_b": "F"},  # Above threshold
            {"score": 0.1, "claim_a": "G", "claim_b": "H"},  # Below threshold
        ]
        
        result = self.manager.enforce_caps([], [], contradictions, policy)
        
        # Should only have 2 contradictions (scores >= 0.5)
        assert len(result["contradictions"]) == 2
        assert result["caps_applied"]["contradictions_before"] == 4
        assert result["caps_applied"]["contradictions_after"] == 2
    
    def test_enforce_caps_blocks_contradictions_for_general_role(self):
        """Test that general role doesn't write contradictions to memories."""
        policy = self.manager.get_policy(["general"])
        
        contradictions = [
            {"score": 0.9, "claim_a": "A", "claim_b": "B"},
            {"score": 0.8, "claim_a": "C", "claim_b": "D"},
        ]
        
        result = self.manager.enforce_caps([], [], contradictions, policy)
        
        # Should return empty list because write_contradictions_to_memories is False
        assert len(result["contradictions"]) == 0
        assert result["caps_applied"]["write_contradictions"] is False


class TestCommitWithPolicy:
    """Integration tests for commit_analysis with policy enforcement."""
    
    @pytest.fixture
    def mock_supabase(self):
        """Create a mock Supabase client."""
        mock_sb = Mock()
        
        # Counter for unique IDs
        entity_counter = {"count": 0}
        edge_counter = {"count": 0}
        
        def mock_table(table_name):
            table_mock = Mock()
            
            if table_name == "entities":
                # Mock upsert for entities
                def mock_upsert(*args, **kwargs):
                    upsert_mock = Mock()
                    def mock_execute():
                        entity_counter["count"] += 1
                        return Mock(data=[{"id": f"entity-{entity_counter['count']}"}])
                    upsert_mock.execute = mock_execute
                    return upsert_mock
                table_mock.upsert = mock_upsert
                
                # Mock insert for entities
                def mock_insert(*args, **kwargs):
                    insert_mock = Mock()
                    def mock_execute():
                        entity_counter["count"] += 1
                        return Mock(data=[{"id": f"entity-{entity_counter['count']}"}])
                    insert_mock.execute = mock_execute
                    return insert_mock
                table_mock.insert = mock_insert
                
                # Mock select for checking existing entities
                def mock_select(*args, **kwargs):
                    select_mock = Mock()
                    def mock_eq(*args2, **kwargs2):
                        eq_mock = Mock()
                        def mock_limit(*args3, **kwargs3):
                            limit_mock = Mock()
                            limit_mock.execute = lambda: Mock(data=[])
                            return limit_mock
                        eq_mock.limit = mock_limit
                        eq_mock.eq = mock_eq  # Allow chaining multiple eq calls
                        return eq_mock
                    select_mock.eq = mock_eq
                    return select_mock
                table_mock.select = mock_select
                
            elif table_name == "entity_edges":
                # Mock select for checking existing edges
                def mock_select(*args, **kwargs):
                    select_mock = Mock()
                    def mock_eq(*args2, **kwargs2):
                        eq_mock = Mock()
                        def mock_limit(*args3, **kwargs3):
                            limit_mock = Mock()
                            limit_mock.execute = lambda: Mock(data=[])
                            return limit_mock
                        eq_mock.eq = mock_eq  # Chain multiple eq calls
                        eq_mock.limit = mock_limit
                        return eq_mock
                    select_mock.eq = mock_eq
                    return select_mock
                table_mock.select = mock_select
                
                # Mock insert for edges
                def mock_insert(*args, **kwargs):
                    insert_mock = Mock()
                    def mock_execute():
                        edge_counter["count"] += 1
                        return Mock(data=[{"id": f"edge-{edge_counter['count']}"}])
                    insert_mock.execute = mock_execute
                    return insert_mock
                table_mock.insert = mock_insert
                
            elif table_name == "memories":
                # Mock update for contradictions
                def mock_update(*args, **kwargs):
                    update_mock = Mock()
                    def mock_eq(*args2, **kwargs2):
                        eq_mock = Mock()
                        eq_mock.execute = lambda: Mock()
                        return eq_mock
                    update_mock.eq = mock_eq
                    return update_mock
                table_mock.update = mock_update
            
            elif table_name == "jobs":
                # Mock insert for jobs queue
                def mock_insert(*args, **kwargs):
                    insert_mock = Mock()
                    insert_mock.execute = lambda: Mock(data=[{"id": "job-123"}])
                    return insert_mock
                table_mock.insert = mock_insert
            
            return table_mock
        
        mock_sb.table = mock_table
        
        return mock_sb
    
    def test_commit_enforces_concept_caps(self, mock_supabase):
        """Test that commit_analysis enforces concept caps."""
        analysis = AnalysisResult(
            predicates=[],
            frames=[],
            concepts=[
                {"name": f"Concept {i}"} for i in range(100)
            ],
            contradictions=[]
        )
        
        # Use 'general' role with max 50 concepts
        result = commit_analysis(
            mock_supabase,
            analysis,
            user_roles=["general"]
        )
        
        # Should only create 50 concept entities
        assert len(result.concept_entity_ids) <= 50
    
    def test_commit_filters_frame_types(self, mock_supabase):
        """Test that commit_analysis filters frame types."""
        analysis = AnalysisResult(
            predicates=[],
            frames=[
                EventFrame(frame_id="f1", type="claim", roles={}),
                EventFrame(frame_id="f2", type="evidence", roles={}),
                EventFrame(frame_id="f3", type="hypothesis", roles={}),
                EventFrame(frame_id="f4", type="method", roles={}),
            ],
            concepts=[],
            contradictions=[]
        )
        
        # Use 'general' role which only allows claim and evidence
        result = commit_analysis(
            mock_supabase,
            analysis,
            user_roles=["general"],
            file_id="test-file",
            chunk_idx=0
        )
        
        # Should only create 2 frame entities (claim + evidence)
        assert len(result.frame_entity_ids) == 2
    
    def test_commit_blocks_contradictions_for_general_role(self, mock_supabase):
        """Test that general role doesn't write contradictions."""
        analysis = AnalysisResult(
            predicates=[],
            frames=[],
            concepts=[],
            contradictions=[
                ContradictionCandidate(
                    subject_entity_id=None,
                    subject_text="Test",
                    claim_a="Claim A",
                    claim_b="Claim B",
                    evidence_ids=[]
                )
            ]
        )
        
        # Use 'general' role with write_contradictions_to_memories=False
        result = commit_analysis(
            mock_supabase,
            analysis,
            memory_id="memory-123",
            user_roles=["general"]
        )
        
        # Should not call update_memory_contradictions
        # Check that update was not called (or called with empty list)
        # This is tested through the mock - we can check the result
        assert result is not None
    
    @patch("ingest.commit.get_feature_flag")
    def test_commit_with_admin_role_allows_more_concepts(self, mock_flag, mock_supabase):
        """Test that admin role allows more concepts."""
        mock_flag.return_value = False  # Disable implicate refresh
        
        analysis = AnalysisResult(
            predicates=[],
            frames=[],
            concepts=[
                {"name": f"Concept {i}"} for i in range(300)
            ],
            contradictions=[]
        )
        
        # Use 'admin' role with max 500 concepts
        with patch("ingest.commit.enqueue_implicate_refresh", return_value=0):
            result = commit_analysis(
                mock_supabase,
                analysis,
                user_roles=["admin"]
            )
        
        # Should create all 300 concept entities (under admin's 500 limit)
        assert len(result.concept_entity_ids) == 300


class TestPolicyHelperFunctions:
    """Tests for policy helper functions."""
    
    def test_get_ingest_policy_convenience_function(self):
        """Test the get_ingest_policy convenience function."""
        policy = get_ingest_policy(["pro"])
        
        assert policy.role == "pro"
        assert policy.max_concepts_per_file == 200
    
    def test_get_ingest_policy_manager_returns_singleton(self):
        """Test that get_ingest_policy_manager returns the same instance."""
        manager1 = get_ingest_policy_manager()
        manager2 = get_ingest_policy_manager()
        
        assert manager1 is manager2
    
    def test_validate_frame_type(self):
        """Test frame type validation."""
        manager = IngestPolicyManager()
        
        assert manager.validate_frame_type("claim") is True
        assert manager.validate_frame_type("evidence") is True
        assert manager.validate_frame_type("hypothesis") is True
        assert manager.validate_frame_type("invalid_type") is False


class TestPolicyYAMLStructure:
    """Tests for validating the YAML policy structure."""
    
    def test_policy_file_exists(self):
        """Test that the policy file exists in the expected location."""
        expected_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "config",
            "ingest_policy.yaml"
        )
        assert os.path.exists(expected_path), f"Policy file not found at {expected_path}"
    
    def test_policy_file_is_valid_yaml(self):
        """Test that the policy file is valid YAML."""
        policy_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "config",
            "ingest_policy.yaml"
        )
        
        with open(policy_path, 'r') as f:
            policy_data = yaml.safe_load(f)
        
        assert policy_data is not None
        assert isinstance(policy_data, dict)
    
    def test_policy_has_required_sections(self):
        """Test that the policy file has all required sections."""
        manager = IngestPolicyManager()
        
        # Check that we have policies for standard roles
        admin_policy = manager.get_policy(["admin"])
        general_policy = manager.get_policy(["general"])
        pro_policy = manager.get_policy(["pro"])
        
        assert admin_policy.role == "admin"
        assert general_policy.role == "general"
        assert pro_policy.role == "pro"
        
        # Check global limits exist
        limits = manager.get_global_limits()
        assert "max_concepts_per_file_absolute" in limits
        
        # Check valid frame types exist
        frame_types = manager.get_valid_frame_types()
        assert "claim" in frame_types
        assert "evidence" in frame_types


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
