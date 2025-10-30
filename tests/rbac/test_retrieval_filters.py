"""
Tests for role-based retrieval filtering.

Tests visibility level filtering, trace summary processing,
and integration with selection strategies.
"""

import pytest
from typing import List, Dict, Any

from core.rbac.levels import (
    ROLE_VISIBILITY_LEVELS,
    get_role_level,
    get_max_role_level,
    can_view_memory,
    filter_memories_by_level,
    process_trace_summary,
    strip_sensitive_provenance,
    get_level_description,
    get_roles_with_level,
    get_roles_with_min_level,
)
from core.rbac import (
    ROLE_GENERAL,
    ROLE_PRO,
    ROLE_SCHOLARS,
    ROLE_ANALYTICS,
    ROLE_OPS,
)


# ============================================================================
# Test Level Mappings
# ============================================================================

class TestLevelMappings:
    """Test role to level mappings."""
    
    def test_role_levels(self):
        """Test that roles map to correct levels."""
        assert get_role_level(ROLE_GENERAL) == 0
        assert get_role_level(ROLE_PRO) == 1
        assert get_role_level(ROLE_SCHOLARS) == 1
        assert get_role_level(ROLE_ANALYTICS) == 2
        assert get_role_level(ROLE_OPS) == 2
    
    def test_case_insensitive(self):
        """Role level lookup should be case-insensitive."""
        assert get_role_level("GENERAL") == 0
        assert get_role_level("Pro") == 1
        assert get_role_level("ANALYTICS") == 2
    
    def test_unknown_role_returns_default(self):
        """Unknown roles should return default level 0."""
        assert get_role_level("unknown") == 0
        assert get_role_level("") == 0
        assert get_role_level(None) == 0
    
    def test_max_role_level_single_role(self):
        """Test max level with single role."""
        assert get_max_role_level([ROLE_GENERAL]) == 0
        assert get_max_role_level([ROLE_PRO]) == 1
        assert get_max_role_level([ROLE_ANALYTICS]) == 2
    
    def test_max_role_level_multiple_roles(self):
        """Test max level with multiple roles."""
        assert get_max_role_level([ROLE_GENERAL, ROLE_PRO]) == 1
        assert get_max_role_level([ROLE_PRO, ROLE_ANALYTICS]) == 2
        assert get_max_role_level([ROLE_GENERAL, ROLE_ANALYTICS]) == 2
    
    def test_max_role_level_empty_list(self):
        """Empty role list should return default level."""
        assert get_max_role_level([]) == 0


# ============================================================================
# Test Memory Visibility
# ============================================================================

class TestMemoryVisibility:
    """Test can_view_memory function."""
    
    def test_general_can_only_see_level_0(self):
        """General role can only see level 0 memories."""
        assert can_view_memory([ROLE_GENERAL], 0) is True
        assert can_view_memory([ROLE_GENERAL], 1) is False
        assert can_view_memory([ROLE_GENERAL], 2) is False
    
    def test_pro_can_see_level_0_and_1(self):
        """Pro role can see level 0 and 1 memories."""
        assert can_view_memory([ROLE_PRO], 0) is True
        assert can_view_memory([ROLE_PRO], 1) is True
        assert can_view_memory([ROLE_PRO], 2) is False
    
    def test_scholars_same_as_pro(self):
        """Scholars should have same visibility as pro."""
        assert can_view_memory([ROLE_SCHOLARS], 0) is True
        assert can_view_memory([ROLE_SCHOLARS], 1) is True
        assert can_view_memory([ROLE_SCHOLARS], 2) is False
    
    def test_analytics_can_see_all_levels(self):
        """Analytics role can see all levels."""
        assert can_view_memory([ROLE_ANALYTICS], 0) is True
        assert can_view_memory([ROLE_ANALYTICS], 1) is True
        assert can_view_memory([ROLE_ANALYTICS], 2) is True
    
    def test_ops_can_see_all_levels(self):
        """Ops role can see all levels."""
        assert can_view_memory([ROLE_OPS], 0) is True
        assert can_view_memory([ROLE_OPS], 1) is True
        assert can_view_memory([ROLE_OPS], 2) is True
    
    def test_multiple_roles_use_highest_level(self):
        """With multiple roles, use highest level for visibility."""
        # General + Pro = level 1
        assert can_view_memory([ROLE_GENERAL, ROLE_PRO], 1) is True
        
        # Pro + Analytics = level 2
        assert can_view_memory([ROLE_PRO, ROLE_ANALYTICS], 2) is True


# ============================================================================
# Test Memory Filtering
# ============================================================================

class TestMemoryFiltering:
    """Test filter_memories_by_level function."""
    
    @pytest.fixture
    def sample_memories(self):
        """Sample memories with different visibility levels."""
        return [
            {"id": "m1", "text": "Public memory", "role_view_level": 0},
            {"id": "m2", "text": "Pro memory", "role_view_level": 1},
            {"id": "m3", "text": "Analytics memory", "role_view_level": 2},
            {"id": "m4", "text": "Another public", "role_view_level": 0},
            {"id": "m5", "text": "Another pro", "role_view_level": 1},
        ]
    
    def test_general_sees_only_level_0(self, sample_memories):
        """General role should only see level 0 memories."""
        filtered = filter_memories_by_level(sample_memories, [ROLE_GENERAL])
        
        assert len(filtered) == 2
        assert all(m["role_view_level"] == 0 for m in filtered)
        assert {m["id"] for m in filtered} == {"m1", "m4"}
    
    def test_pro_sees_level_0_and_1(self, sample_memories):
        """Pro role should see level 0 and 1 memories."""
        filtered = filter_memories_by_level(sample_memories, [ROLE_PRO])
        
        assert len(filtered) == 4
        assert all(m["role_view_level"] <= 1 for m in filtered)
        assert {m["id"] for m in filtered} == {"m1", "m2", "m4", "m5"}
    
    def test_analytics_sees_all(self, sample_memories):
        """Analytics role should see all memories."""
        filtered = filter_memories_by_level(sample_memories, [ROLE_ANALYTICS])
        
        assert len(filtered) == 5
        assert {m["id"] for m in filtered} == {"m1", "m2", "m3", "m4", "m5"}
    
    def test_scholars_same_as_pro(self, sample_memories):
        """Scholars should see same memories as pro."""
        pro_filtered = filter_memories_by_level(sample_memories, [ROLE_PRO])
        scholars_filtered = filter_memories_by_level(sample_memories, [ROLE_SCHOLARS])
        
        assert len(pro_filtered) == len(scholars_filtered)
        assert {m["id"] for m in pro_filtered} == {m["id"] for m in scholars_filtered}
    
    def test_empty_memories_returns_empty(self):
        """Filtering empty list should return empty list."""
        filtered = filter_memories_by_level([], [ROLE_GENERAL])
        assert filtered == []
    
    def test_custom_level_field(self):
        """Should support custom level field name."""
        memories = [
            {"id": "m1", "custom_level": 0},
            {"id": "m2", "custom_level": 1},
        ]
        
        filtered = filter_memories_by_level(
            memories,
            [ROLE_GENERAL],
            level_field="custom_level"
        )
        
        assert len(filtered) == 1
        assert filtered[0]["id"] == "m1"


# ============================================================================
# Test Trace Summary Processing
# ============================================================================

class TestTraceSummaryProcessing:
    """Test process_trace_summary function."""
    
    def test_general_gets_capped_summary(self):
        """General role should get max 4 lines."""
        long_summary = "\n".join([f"Line {i}" for i in range(10)])
        
        processed = process_trace_summary(long_summary, [ROLE_GENERAL])
        
        lines = processed.split('\n')
        assert len(lines) == 5  # 4 lines + "... (6 more lines)"
        assert "Line 0" in processed
        assert "Line 3" in processed
        assert "6 more lines" in processed
        assert "Line 9" not in processed
    
    def test_pro_gets_full_summary(self):
        """Pro role should get full summary."""
        long_summary = "\n".join([f"Line {i}" for i in range(10)])
        
        processed = process_trace_summary(long_summary, [ROLE_PRO])
        
        lines = processed.split('\n')
        assert len(lines) == 10
        assert "Line 0" in processed
        assert "Line 9" in processed
    
    def test_scholars_gets_full_summary(self):
        """Scholars role should get full summary."""
        long_summary = "\n".join([f"Line {i}" for i in range(10)])
        
        processed = process_trace_summary(long_summary, [ROLE_SCHOLARS])
        
        lines = processed.split('\n')
        assert len(lines) == 10
    
    def test_analytics_gets_full_summary(self):
        """Analytics role should get full summary."""
        long_summary = "\n".join([f"Line {i}" for i in range(10)])
        
        processed = process_trace_summary(long_summary, [ROLE_ANALYTICS])
        
        lines = processed.split('\n')
        assert len(lines) == 10
    
    def test_short_summary_not_capped(self):
        """Short summaries should not be capped even for general."""
        short_summary = "Line 1\nLine 2\nLine 3"
        
        processed = process_trace_summary(short_summary, [ROLE_GENERAL])
        
        assert processed == short_summary
        assert "more lines" not in processed
    
    def test_none_summary_returns_none(self):
        """None summary should return None."""
        assert process_trace_summary(None, [ROLE_GENERAL]) is None
    
    def test_empty_summary_returns_empty(self):
        """Empty summary should return empty."""
        assert process_trace_summary("", [ROLE_GENERAL]) == ""


# ============================================================================
# Test Sensitive Provenance Stripping
# ============================================================================

class TestSensitiveProvenanceStripping:
    """Test strip_sensitive_provenance function."""
    
    def test_strip_uuids(self):
        """Should strip UUID patterns."""
        text = "ID: 123e4567-e89b-12d3-a456-426614174000"
        
        stripped = strip_sensitive_provenance(text)
        
        assert "123e4567-e89b-12d3-a456-426614174000" not in stripped
        assert "[ID]" in stripped
    
    def test_strip_internal_markers(self):
        """Should strip [internal] markers."""
        text = "This is [internal] information"
        
        stripped = strip_sensitive_provenance(text)
        
        assert "[internal]" not in stripped
    
    def test_strip_system_markers(self):
        """Should strip [system] markers."""
        text = "This is [system] data"
        
        stripped = strip_sensitive_provenance(text)
        
        assert "[system]" not in stripped
    
    def test_strip_database_references(self):
        """Should strip database references."""
        text = "Query: db.users.find()"
        
        stripped = strip_sensitive_provenance(text)
        
        assert "db." not in stripped
    
    def test_preserve_normal_text(self):
        """Should preserve normal text."""
        text = "This is normal user-facing text"
        
        stripped = strip_sensitive_provenance(text)
        
        assert "normal user-facing text" in stripped


# ============================================================================
# Test Helper Functions
# ============================================================================

class TestHelperFunctions:
    """Test helper utility functions."""
    
    def test_get_level_description(self):
        """Test level description strings."""
        assert "Public" in get_level_description(0)
        assert "Professional" in get_level_description(1)
        assert "Internal" in get_level_description(2)
    
    def test_get_roles_with_level(self):
        """Test getting roles by level."""
        level_0_roles = get_roles_with_level(0)
        assert ROLE_GENERAL in level_0_roles
        assert len(level_0_roles) == 1
        
        level_1_roles = get_roles_with_level(1)
        assert ROLE_PRO in level_1_roles
        assert ROLE_SCHOLARS in level_1_roles
        assert len(level_1_roles) == 2
        
        level_2_roles = get_roles_with_level(2)
        assert ROLE_ANALYTICS in level_2_roles
        assert ROLE_OPS in level_2_roles
        assert len(level_2_roles) == 2
    
    def test_get_roles_with_min_level(self):
        """Test getting roles with minimum level."""
        # Level 0+ (all roles)
        roles = get_roles_with_min_level(0)
        assert len(roles) == 5
        
        # Level 1+ (pro, scholars, analytics, ops)
        roles = get_roles_with_min_level(1)
        assert len(roles) == 4
        assert ROLE_GENERAL not in roles
        
        # Level 2+ (analytics, ops)
        roles = get_roles_with_min_level(2)
        assert len(roles) == 2
        assert ROLE_ANALYTICS in roles
        assert ROLE_OPS in roles


# ============================================================================
# Integration Tests
# ============================================================================

class TestRetrievalFilteringIntegration:
    """Integration tests for retrieval filtering."""
    
    @pytest.fixture
    def mixed_memories(self):
        """Mixed memories with different levels and trace summaries."""
        return [
            {
                "id": "public-1",
                "text": "Public information",
                "role_view_level": 0,
                "process_trace_summary": "\n".join([f"Public trace {i}" for i in range(6)]),
            },
            {
                "id": "pro-1",
                "text": "Professional information",
                "role_view_level": 1,
                "process_trace_summary": "\n".join([f"Pro trace {i}" for i in range(6)]),
            },
            {
                "id": "analytics-1",
                "text": "Analytics information",
                "role_view_level": 2,
                "process_trace_summary": "\n".join([f"Analytics trace {i}" for i in range(6)]),
            },
        ]
    
    def test_general_user_workflow(self, mixed_memories):
        """Test complete workflow for general user."""
        # Filter memories
        filtered = filter_memories_by_level(mixed_memories, [ROLE_GENERAL])
        
        # Should only see level 0
        assert len(filtered) == 1
        assert filtered[0]["id"] == "public-1"
        
        # Process trace summary (should be capped)
        summary = process_trace_summary(
            filtered[0]["process_trace_summary"],
            [ROLE_GENERAL]
        )
        lines = summary.split('\n')
        assert len(lines) == 5  # 4 + ellipsis line
        assert "2 more lines" in summary
    
    def test_pro_user_workflow(self, mixed_memories):
        """Test complete workflow for pro user."""
        # Filter memories
        filtered = filter_memories_by_level(mixed_memories, [ROLE_PRO])
        
        # Should see level 0 and 1
        assert len(filtered) == 2
        assert {m["id"] for m in filtered} == {"public-1", "pro-1"}
        
        # Process trace summary (should be full)
        summary = process_trace_summary(
            filtered[0]["process_trace_summary"],
            [ROLE_PRO]
        )
        lines = summary.split('\n')
        assert len(lines) == 6  # Full summary
        assert "more lines" not in summary
    
    def test_analytics_user_workflow(self, mixed_memories):
        """Test complete workflow for analytics user."""
        # Filter memories
        filtered = filter_memories_by_level(mixed_memories, [ROLE_ANALYTICS])
        
        # Should see all levels
        assert len(filtered) == 3
        
        # Process trace summary (should be full)
        summary = process_trace_summary(
            filtered[2]["process_trace_summary"],
            [ROLE_ANALYTICS]
        )
        lines = summary.split('\n')
        assert len(lines) == 6  # Full summary
    
    def test_multi_role_user_workflow(self, mixed_memories):
        """Test workflow for user with multiple roles."""
        # User with general + pro roles
        filtered = filter_memories_by_level(
            mixed_memories,
            [ROLE_GENERAL, ROLE_PRO]
        )
        
        # Should see up to level 1 (highest role)
        assert len(filtered) == 2
        
        # Trace summary should use highest level (full)
        summary = process_trace_summary(
            filtered[0]["process_trace_summary"],
            [ROLE_GENERAL, ROLE_PRO]
        )
        lines = summary.split('\n')
        assert len(lines) == 6  # Full (pro overrides general)


# ============================================================================
# Test Edge Cases
# ============================================================================

class TestEdgeCases:
    """Test edge cases and error handling."""
    
    def test_missing_role_view_level_defaults_to_0(self):
        """Memories without role_view_level should default to 0."""
        memories = [
            {"id": "m1", "text": "No level specified"},
        ]
        
        # General can see it
        filtered = filter_memories_by_level(memories, [ROLE_GENERAL])
        assert len(filtered) == 1
    
    def test_very_high_memory_level(self):
        """Memories with high levels should be filtered correctly."""
        memories = [
            {"id": "m1", "role_view_level": 99},
        ]
        
        # Even analytics can't see level 99
        filtered = filter_memories_by_level(memories, [ROLE_ANALYTICS])
        assert len(filtered) == 0
    
    def test_negative_memory_level(self):
        """Negative levels should be handled."""
        memories = [
            {"id": "m1", "role_view_level": -1},
        ]
        
        # Everyone can see negative levels (lower than any role)
        filtered = filter_memories_by_level(memories, [ROLE_GENERAL])
        assert len(filtered) == 1


# ============================================================================
# Summary Test
# ============================================================================

class TestCompleteCoverage:
    """Comprehensive test to verify complete filtering system."""
    
    def test_all_role_visibility_combinations(self):
        """Test all role × memory level combinations."""
        roles = [ROLE_GENERAL, ROLE_PRO, ROLE_SCHOLARS, ROLE_ANALYTICS, ROLE_OPS]
        levels = [0, 1, 2]
        
        # Expected visibility matrix
        expected = {
            (ROLE_GENERAL, 0): True,
            (ROLE_GENERAL, 1): False,
            (ROLE_GENERAL, 2): False,
            (ROLE_PRO, 0): True,
            (ROLE_PRO, 1): True,
            (ROLE_PRO, 2): False,
            (ROLE_SCHOLARS, 0): True,
            (ROLE_SCHOLARS, 1): True,
            (ROLE_SCHOLARS, 2): False,
            (ROLE_ANALYTICS, 0): True,
            (ROLE_ANALYTICS, 1): True,
            (ROLE_ANALYTICS, 2): True,
            (ROLE_OPS, 0): True,
            (ROLE_OPS, 1): True,
            (ROLE_OPS, 2): True,
        }
        
        for role in roles:
            for level in levels:
                actual = can_view_memory([role], level)
                assert actual == expected[(role, level)], (
                    f"Role '{role}' viewing level {level} should be "
                    f"{expected[(role, level)]}, got {actual}"
                )
