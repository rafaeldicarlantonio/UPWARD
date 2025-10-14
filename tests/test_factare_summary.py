# tests/test_factare_summary.py — Comprehensive tests for Factare summary functionality

import unittest
import sys
import os
import json
from datetime import datetime, timedelta
from unittest.mock import patch

# Add workspace to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.factare.summary import (
    EvidenceItem,
    Decision,
    CompareSummary,
    normalize_evidence,
    create_compare_summary,
    validate_compare_summary,
    get_summary_stats,
    export_summary_json,
    import_summary_json,
    _is_external_source,
    _normalize_snippet_text,
    _generate_text_hash,
    _parse_timestamp,
    MAX_EVIDENCE_ITEMS,
    MAX_EXTERNAL_TEXT_LENGTH,
    MAX_INTERNAL_TEXT_LENGTH
)

class TestEvidenceItem(unittest.TestCase):
    """Test EvidenceItem dataclass."""
    
    def test_evidence_item_creation(self):
        """Test creating EvidenceItem with all fields."""
        item = EvidenceItem(
            id="test_001",
            snippet="This is a test snippet",
            source="Test Source",
            score=0.85,
            is_external=True,
            url="https://example.com",
            timestamp=datetime.now(),
            metadata={"type": "research"}
        )
        
        self.assertEqual(item.id, "test_001")
        self.assertEqual(item.snippet, "This is a test snippet")
        self.assertEqual(item.source, "Test Source")
        self.assertEqual(item.score, 0.85)
        self.assertTrue(item.is_external)
        self.assertEqual(item.url, "https://example.com")
        self.assertIsInstance(item.timestamp, datetime)
        self.assertEqual(item.metadata["type"], "research")
    
    def test_evidence_item_minimal(self):
        """Test creating EvidenceItem with minimal fields."""
        item = EvidenceItem(
            id="test_002",
            snippet="Minimal snippet",
            source="Minimal Source",
            score=0.5
        )
        
        self.assertEqual(item.id, "test_002")
        self.assertEqual(item.snippet, "Minimal snippet")
        self.assertEqual(item.source, "Minimal Source")
        self.assertEqual(item.score, 0.5)
        self.assertFalse(item.is_external)
        self.assertIsNone(item.url)
        self.assertIsNone(item.timestamp)
        self.assertIsNone(item.metadata)

class TestDecision(unittest.TestCase):
    """Test Decision dataclass."""
    
    def test_decision_creation(self):
        """Test creating Decision with all fields."""
        decision = Decision(
            verdict="stance_a",
            confidence=0.9,
            rationale="Strong evidence supports stance A"
        )
        
        self.assertEqual(decision.verdict, "stance_a")
        self.assertEqual(decision.confidence, 0.9)
        self.assertEqual(decision.rationale, "Strong evidence supports stance A")
    
    def test_decision_confidence_clamping(self):
        """Test that confidence is properly clamped."""
        # This would be handled by create_compare_summary
        decision = Decision(
            verdict="stance_b",
            confidence=1.5,  # Above 1.0
            rationale="Test rationale"
        )
        
        # The dataclass itself doesn't clamp, but create_compare_summary does
        self.assertEqual(decision.confidence, 1.5)

class TestCompareSummary(unittest.TestCase):
    """Test CompareSummary dataclass."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.evidence = [
            EvidenceItem(
                id="ev_001",
                snippet="Evidence 1",
                source="Source 1",
                score=0.9
            ),
            EvidenceItem(
                id="ev_002",
                snippet="Evidence 2",
                source="Source 2",
                score=0.8
            )
        ]
        
        self.decision = Decision(
            verdict="stance_a",
            confidence=0.85,
            rationale="Evidence supports stance A"
        )
    
    def test_compare_summary_creation(self):
        """Test creating CompareSummary with all fields."""
        summary = CompareSummary(
            query="Test query",
            stance_a="Stance A",
            stance_b="Stance B",
            evidence=self.evidence,
            decision=self.decision,
            created_at=datetime.now(),
            metadata={"test": True}
        )
        
        self.assertEqual(summary.query, "Test query")
        self.assertEqual(summary.stance_a, "Stance A")
        self.assertEqual(summary.stance_b, "Stance B")
        self.assertEqual(len(summary.evidence), 2)
        self.assertEqual(summary.decision.verdict, "stance_a")
        self.assertIsInstance(summary.created_at, datetime)
        self.assertEqual(summary.metadata["test"], True)
    
    def test_to_dict_conversion(self):
        """Test converting CompareSummary to dictionary."""
        summary = CompareSummary(
            query="Test query",
            stance_a="Stance A",
            stance_b="Stance B",
            evidence=self.evidence,
            decision=self.decision,
            created_at=datetime(2023, 1, 1, 12, 0, 0)
        )
        
        data = summary.to_dict()
        
        self.assertIsInstance(data, dict)
        self.assertEqual(data["query"], "Test query")
        self.assertEqual(data["stance_a"], "Stance A")
        self.assertEqual(data["stance_b"], "Stance B")
        self.assertEqual(len(data["evidence"]), 2)
        self.assertEqual(data["decision"]["verdict"], "stance_a")
        self.assertEqual(data["created_at"], "2023-01-01T12:00:00")
    
    def test_from_dict_conversion(self):
        """Test creating CompareSummary from dictionary."""
        data = {
            "query": "Test query",
            "stance_a": "Stance A",
            "stance_b": "Stance B",
            "evidence": [
                {
                    "id": "ev_001",
                    "snippet": "Evidence 1",
                    "source": "Source 1",
                    "score": 0.9,
                    "is_external": False,
                    "url": None,
                    "timestamp": None,
                    "metadata": None
                }
            ],
            "decision": {
                "verdict": "stance_a",
                "confidence": 0.85,
                "rationale": "Evidence supports stance A"
            },
            "created_at": "2023-01-01T12:00:00",
            "metadata": None
        }
        
        summary = CompareSummary.from_dict(data)
        
        self.assertEqual(summary.query, "Test query")
        self.assertEqual(summary.stance_a, "Stance A")
        self.assertEqual(summary.stance_b, "Stance B")
        self.assertEqual(len(summary.evidence), 1)
        self.assertEqual(summary.evidence[0].id, "ev_001")
        self.assertEqual(summary.decision.verdict, "stance_a")
        self.assertEqual(summary.created_at, datetime(2023, 1, 1, 12, 0, 0))

class TestNormalizeEvidence(unittest.TestCase):
    """Test evidence normalization functionality."""
    
    def test_normalize_evidence_basic(self):
        """Test basic evidence normalization."""
        raw_evidence = [
            {
                "id": "ev_001",
                "snippet": "Test snippet 1",
                "source": "Test Source 1",
                "score": 0.9,
                "url": "https://example.com"
            },
            {
                "id": "ev_002",
                "snippet": "Test snippet 2",
                "source": "Test Source 2",
                "score": 0.8
            }
        ]
        
        normalized = normalize_evidence(raw_evidence)
        
        self.assertEqual(len(normalized), 2)
        self.assertIsInstance(normalized[0], EvidenceItem)
        self.assertEqual(normalized[0].id, "ev_001")
        self.assertEqual(normalized[0].snippet, "Test snippet 1")
        self.assertEqual(normalized[0].source, "Test Source 1")
        self.assertEqual(normalized[0].score, 0.9)
        self.assertTrue(normalized[0].is_external)  # Has URL
        self.assertFalse(normalized[1].is_external)  # No URL
    
    def test_normalize_evidence_ordering(self):
        """Test that evidence is ordered by score then recency."""
        now = datetime.now()
        raw_evidence = [
            {
                "id": "ev_001",
                "snippet": "Lower score, newer",
                "source": "Source 1",
                "score": 0.7,
                "timestamp": (now - timedelta(hours=1)).isoformat()
            },
            {
                "id": "ev_002",
                "snippet": "Higher score, older",
                "source": "Source 2",
                "score": 0.9,
                "timestamp": (now - timedelta(hours=2)).isoformat()
            },
            {
                "id": "ev_003",
                "snippet": "Same score, newer",
                "source": "Source 3",
                "score": 0.9,
                "timestamp": (now - timedelta(minutes=30)).isoformat()
            }
        ]
        
        normalized = normalize_evidence(raw_evidence)
        
        # Should be ordered by score (desc) then recency (desc)
        self.assertEqual(normalized[0].id, "ev_003")  # Score 0.9, newest
        self.assertEqual(normalized[1].id, "ev_002")  # Score 0.9, older
        self.assertEqual(normalized[2].id, "ev_001")  # Score 0.7, newest
    
    def test_normalize_evidence_max_items(self):
        """Test that evidence is limited to max_items."""
        raw_evidence = []
        for i in range(100):
            raw_evidence.append({
                "id": f"ev_{i:03d}",
                "snippet": f"Snippet {i}",
                "source": f"Source {i}",
                "score": 0.5 + (i * 0.001)  # Increasing scores
            })
        
        normalized = normalize_evidence(raw_evidence, max_items=10)
        
        self.assertEqual(len(normalized), 10)
        # Should be the highest scoring items
        self.assertEqual(normalized[0].id, "ev_099")
        self.assertEqual(normalized[9].id, "ev_090")
    
    def test_normalize_evidence_text_truncation(self):
        """Test text truncation for external and internal sources."""
        long_text = "A" * 1000
        
        raw_evidence = [
            {
                "id": "ev_external",
                "snippet": long_text,
                "source": "External Source",
                "url": "https://example.com"
            },
            {
                "id": "ev_internal",
                "snippet": long_text,
                "source": "Internal Source"
            }
        ]
        
        normalized = normalize_evidence(
            raw_evidence,
            max_external_text=100,
            max_internal_text=200
        )
        
        # External should be truncated to 100 chars + hash
        external_item = next(item for item in normalized if item.id == "ev_external")
        self.assertLessEqual(len(external_item.snippet), 100 + 20)  # 100 + "... [hash:12345678]"
        self.assertIn("... [hash:", external_item.snippet)
        
        # Internal should be truncated to 200 chars + hash
        internal_item = next(item for item in normalized if item.id == "ev_internal")
        self.assertLessEqual(len(internal_item.snippet), 200 + 20)  # 200 + "... [hash:12345678]"
        self.assertIn("... [hash:", internal_item.snippet)
    
    def test_normalize_evidence_timestamp_parsing(self):
        """Test timestamp parsing from various formats."""
        now = datetime.now()
        
        raw_evidence = [
            {
                "id": "ev_iso",
                "snippet": "ISO format",
                "source": "Source 1",
                "score": 0.8,
                "timestamp": now.isoformat()
            },
            {
                "id": "ev_datetime",
                "snippet": "Datetime object",
                "source": "Source 2",
                "score": 0.8,
                "timestamp": now
            },
            {
                "id": "ev_string",
                "snippet": "String format",
                "source": "Source 3",
                "score": 0.8,
                "timestamp": now.strftime("%Y-%m-%d %H:%M:%S")
            },
            {
                "id": "ev_none",
                "snippet": "No timestamp",
                "source": "Source 4",
                "score": 0.8,
                "timestamp": None
            }
        ]
        
        normalized = normalize_evidence(raw_evidence)
        
        # All should have valid timestamps or None
        for item in normalized:
            if item.timestamp is not None:
                self.assertIsInstance(item.timestamp, datetime)

class TestUtilityFunctions(unittest.TestCase):
    """Test utility functions."""
    
    def test_is_external_source(self):
        """Test external source detection."""
        # Test with URLs
        self.assertTrue(_is_external_source("https://example.com", ""))
        self.assertTrue(_is_external_source("http://arxiv.org/abs/1234", ""))
        self.assertFalse(_is_external_source("", ""))
        
        # Test with source names
        self.assertTrue(_is_external_source("", "https://example.com"))
        self.assertTrue(_is_external_source("", "www.nature.com"))
        self.assertTrue(_is_external_source("", "arxiv.org"))
        self.assertFalse(_is_external_source("", "Internal Database"))
    
    def test_normalize_snippet_text(self):
        """Test snippet text normalization."""
        long_text = "A" * 1000
        
        # Test external truncation
        result = _normalize_snippet_text(long_text, True, 100, 200)
        self.assertLessEqual(len(result), 120)  # 100 + hash suffix
        self.assertIn("... [hash:", result)
        
        # Test internal truncation
        result = _normalize_snippet_text(long_text, False, 100, 200)
        self.assertLessEqual(len(result), 220)  # 200 + hash suffix
        self.assertIn("... [hash:", result)
        
        # Test no truncation needed
        short_text = "Short text"
        result = _normalize_snippet_text(short_text, True, 100, 200)
        self.assertEqual(result, short_text)
    
    def test_generate_text_hash(self):
        """Test text hash generation."""
        text1 = "Test text 1"
        text2 = "Test text 2"
        
        hash1 = _generate_text_hash(text1)
        hash2 = _generate_text_hash(text2)
        
        self.assertEqual(len(hash1), 8)
        self.assertEqual(len(hash2), 8)
        self.assertNotEqual(hash1, hash2)
        
        # Same text should produce same hash
        hash1_again = _generate_text_hash(text1)
        self.assertEqual(hash1, hash1_again)
    
    def test_parse_timestamp(self):
        """Test timestamp parsing."""
        now = datetime.now()
        
        # Test ISO format
        iso_str = now.isoformat()
        parsed = _parse_timestamp(iso_str)
        self.assertIsInstance(parsed, datetime)
        
        # Test datetime object
        parsed = _parse_timestamp(now)
        self.assertEqual(parsed, now)
        
        # Test None
        parsed = _parse_timestamp(None)
        self.assertIsNone(parsed)
        
        # Test invalid format
        parsed = _parse_timestamp("invalid")
        self.assertIsNone(parsed)

class TestCreateCompareSummary(unittest.TestCase):
    """Test create_compare_summary function."""
    
    def test_create_compare_summary_basic(self):
        """Test basic compare summary creation."""
        evidence_items = [
            {
                "id": "ev_001",
                "snippet": "Evidence 1",
                "source": "Source 1",
                "score": 0.9
            },
            {
                "id": "ev_002",
                "snippet": "Evidence 2",
                "source": "Source 2",
                "score": 0.8
            }
        ]
        
        summary = create_compare_summary(
            query="Test query",
            stance_a="Stance A",
            stance_b="Stance B",
            evidence_items=evidence_items,
            decision_verdict="stance_a",
            decision_confidence=0.85,
            decision_rationale="Evidence supports stance A"
        )
        
        self.assertEqual(summary.query, "Test query")
        self.assertEqual(summary.stance_a, "Stance A")
        self.assertEqual(summary.stance_b, "Stance B")
        self.assertEqual(len(summary.evidence), 2)
        self.assertEqual(summary.decision.verdict, "stance_a")
        self.assertEqual(summary.decision.confidence, 0.85)
        self.assertEqual(summary.decision.rationale, "Evidence supports stance A")
        self.assertIsInstance(summary.created_at, datetime)
    
    def test_create_compare_summary_confidence_clamping(self):
        """Test that confidence is clamped to [0, 1]."""
        summary = create_compare_summary(
            query="Test query",
            stance_a="Stance A",
            stance_b="Stance B",
            evidence_items=[],
            decision_verdict="stance_a",
            decision_confidence=1.5,  # Above 1.0
            decision_rationale="Test rationale"
        )
        
        self.assertEqual(summary.decision.confidence, 1.0)
        
        summary = create_compare_summary(
            query="Test query",
            stance_a="Stance A",
            stance_b="Stance B",
            evidence_items=[],
            decision_verdict="stance_a",
            decision_confidence=-0.5,  # Below 0.0
            decision_rationale="Test rationale"
        )
        
        self.assertEqual(summary.decision.confidence, 0.0)

class TestValidateCompareSummary(unittest.TestCase):
    """Test compare summary validation."""
    
    def test_validate_compare_summary_valid(self):
        """Test validation of valid compare summary."""
        evidence = [
            EvidenceItem(
                id="ev_001",
                snippet="Valid snippet",
                source="Valid source",
                score=0.8
            )
        ]
        
        decision = Decision(
            verdict="stance_a",
            confidence=0.9,
            rationale="Valid rationale"
        )
        
        summary = CompareSummary(
            query="Valid query",
            stance_a="Valid stance A",
            stance_b="Valid stance B",
            evidence=evidence,
            decision=decision
        )
        
        errors = validate_compare_summary(summary)
        self.assertEqual(len(errors), 0)
    
    def test_validate_compare_summary_invalid(self):
        """Test validation of invalid compare summary."""
        evidence = [
            EvidenceItem(
                id="",  # Empty ID
                snippet="",  # Empty snippet
                source="",  # Empty source
                score=1.5  # Invalid score
            )
        ]
        
        decision = Decision(
            verdict="invalid_verdict",  # Invalid verdict
            confidence=1.5,  # Invalid confidence
            rationale=""  # Empty rationale
        )
        
        summary = CompareSummary(
            query="",  # Empty query
            stance_a="",  # Empty stance A
            stance_b="",  # Empty stance B
            evidence=evidence,
            decision=decision
        )
        
        errors = validate_compare_summary(summary)
        self.assertGreater(len(errors), 0)
        
        # Check for specific errors
        error_messages = " ".join(errors)
        self.assertIn("Query cannot be empty", error_messages)
        self.assertIn("Stance A cannot be empty", error_messages)
        self.assertIn("Stance B cannot be empty", error_messages)
        self.assertIn("Evidence item 0 missing ID", error_messages)
        self.assertIn("Evidence item 0 missing snippet", error_messages)
        self.assertIn("Evidence item 0 missing source", error_messages)
        self.assertIn("Evidence item 0 score must be between 0.0 and 1.0", error_messages)
        self.assertIn("Decision verdict must be one of:", error_messages)
        self.assertIn("Decision confidence must be between 0.0 and 1.0", error_messages)
        self.assertIn("Decision rationale cannot be empty", error_messages)

class TestGetSummaryStats(unittest.TestCase):
    """Test get_summary_stats function."""
    
    def test_get_summary_stats_basic(self):
        """Test basic summary statistics."""
        evidence = [
            EvidenceItem(
                id="ev_001",
                snippet="Short snippet",
                source="Internal Source",
                score=0.9,
                is_external=False
            ),
            EvidenceItem(
                id="ev_002",
                snippet="Another short snippet",
                source="External Source",
                score=0.8,
                is_external=True
            )
        ]
        
        decision = Decision(
            verdict="stance_a",
            confidence=0.85,
            rationale="Test rationale"
        )
        
        summary = CompareSummary(
            query="Test query",
            stance_a="Stance A",
            stance_b="Stance B",
            evidence=evidence,
            decision=decision
        )
        
        stats = get_summary_stats(summary)
        
        self.assertEqual(stats["total_evidence_items"], 2)
        self.assertEqual(stats["internal_items"], 1)
        self.assertEqual(stats["external_items"], 1)
        self.assertEqual(stats["truncated_items"], 0)
        self.assertEqual(stats["score_stats"]["average"], 0.85)
        self.assertEqual(stats["score_stats"]["maximum"], 0.9)
        self.assertEqual(stats["score_stats"]["minimum"], 0.8)
        self.assertEqual(stats["decision"]["verdict"], "stance_a")
        self.assertEqual(stats["decision"]["confidence"], 0.85)
    
    def test_get_summary_stats_with_truncation(self):
        """Test summary statistics with truncated items."""
        long_text = "A" * 1000
        
        evidence = [
            EvidenceItem(
                id="ev_001",
                snippet=long_text + "... [hash:12345678]",  # Truncated
                source="External Source",
                score=0.9,
                is_external=True
            ),
            EvidenceItem(
                id="ev_002",
                snippet="Short snippet",  # Not truncated
                source="Internal Source",
                score=0.8,
                is_external=False
            )
        ]
        
        decision = Decision(
            verdict="stance_b",
            confidence=0.7,
            rationale="Test rationale"
        )
        
        summary = CompareSummary(
            query="Test query",
            stance_a="Stance A",
            stance_b="Stance B",
            evidence=evidence,
            decision=decision
        )
        
        stats = get_summary_stats(summary)
        
        self.assertEqual(stats["total_evidence_items"], 2)
        self.assertEqual(stats["internal_items"], 1)
        self.assertEqual(stats["external_items"], 1)
        self.assertEqual(stats["truncated_items"], 1)

class TestJSONSerialization(unittest.TestCase):
    """Test JSON serialization and deserialization."""
    
    def test_export_import_json(self):
        """Test exporting and importing JSON."""
        evidence = [
            EvidenceItem(
                id="ev_001",
                snippet="Test snippet",
                source="Test source",
                score=0.8
            )
        ]
        
        decision = Decision(
            verdict="stance_a",
            confidence=0.9,
            rationale="Test rationale"
        )
        
        original_summary = CompareSummary(
            query="Test query",
            stance_a="Stance A",
            stance_b="Stance B",
            evidence=evidence,
            decision=decision,
            created_at=datetime(2023, 1, 1, 12, 0, 0)
        )
        
        # Export to JSON
        json_str = export_summary_json(original_summary, pretty=True)
        self.assertIsInstance(json_str, str)
        
        # Import from JSON
        imported_summary = import_summary_json(json_str)
        
        # Compare key fields
        self.assertEqual(imported_summary.query, original_summary.query)
        self.assertEqual(imported_summary.stance_a, original_summary.stance_a)
        self.assertEqual(imported_summary.stance_b, original_summary.stance_b)
        self.assertEqual(len(imported_summary.evidence), len(original_summary.evidence))
        self.assertEqual(imported_summary.evidence[0].id, original_summary.evidence[0].id)
        self.assertEqual(imported_summary.decision.verdict, original_summary.decision.verdict)
        self.assertEqual(imported_summary.decision.confidence, original_summary.decision.confidence)
        self.assertEqual(imported_summary.created_at, original_summary.created_at)
    
    def test_export_json_pretty_vs_compact(self):
        """Test pretty vs compact JSON export."""
        evidence = [EvidenceItem(id="ev_001", snippet="Test", source="Source", score=0.8)]
        decision = Decision(verdict="stance_a", confidence=0.9, rationale="Test")
        summary = CompareSummary(
            query="Test", stance_a="A", stance_b="B", evidence=evidence, decision=decision
        )
        
        pretty_json = export_summary_json(summary, pretty=True)
        compact_json = export_summary_json(summary, pretty=False)
        
        self.assertIn("\n", pretty_json)  # Pretty should have newlines
        self.assertNotIn("\n", compact_json)  # Compact should not have newlines
        self.assertGreater(len(pretty_json), len(compact_json))  # Pretty should be longer

class TestDeterministicOrdering(unittest.TestCase):
    """Test deterministic ordering by score then recency."""
    
    def test_deterministic_ordering_by_score(self):
        """Test that items are ordered by score (descending)."""
        now = datetime.now()
        
        raw_evidence = [
            {"id": "ev_001", "snippet": "Low score", "source": "Source 1", "score": 0.3},
            {"id": "ev_002", "snippet": "High score", "source": "Source 2", "score": 0.9},
            {"id": "ev_003", "snippet": "Medium score", "source": "Source 3", "score": 0.6},
        ]
        
        normalized = normalize_evidence(raw_evidence)
        
        # Should be ordered by score (descending)
        self.assertEqual(normalized[0].id, "ev_002")  # 0.9
        self.assertEqual(normalized[1].id, "ev_003")  # 0.6
        self.assertEqual(normalized[2].id, "ev_001")  # 0.3
    
    def test_deterministic_ordering_by_recency(self):
        """Test that items with same score are ordered by recency (descending)."""
        now = datetime.now()
        
        raw_evidence = [
            {
                "id": "ev_001",
                "snippet": "Old item",
                "source": "Source 1",
                "score": 0.8,
                "timestamp": (now - timedelta(hours=2)).isoformat()
            },
            {
                "id": "ev_002",
                "snippet": "New item",
                "source": "Source 2",
                "score": 0.8,
                "timestamp": (now - timedelta(minutes=30)).isoformat()
            },
            {
                "id": "ev_003",
                "snippet": "Middle item",
                "source": "Source 3",
                "score": 0.8,
                "timestamp": (now - timedelta(hours=1)).isoformat()
            }
        ]
        
        normalized = normalize_evidence(raw_evidence)
        
        # Should be ordered by recency (descending) for same score
        self.assertEqual(normalized[0].id, "ev_002")  # Newest
        self.assertEqual(normalized[1].id, "ev_003")  # Middle
        self.assertEqual(normalized[2].id, "ev_001")  # Oldest
    
    def test_deterministic_ordering_mixed_scores_and_times(self):
        """Test ordering with mixed scores and timestamps."""
        now = datetime.now()
        
        raw_evidence = [
            {
                "id": "ev_001",
                "snippet": "High score, old",
                "source": "Source 1",
                "score": 0.9,
                "timestamp": (now - timedelta(hours=2)).isoformat()
            },
            {
                "id": "ev_002",
                "snippet": "High score, new",
                "source": "Source 2",
                "score": 0.9,
                "timestamp": (now - timedelta(minutes=30)).isoformat()
            },
            {
                "id": "ev_003",
                "snippet": "Low score, new",
                "source": "Source 3",
                "score": 0.7,
                "timestamp": (now - timedelta(minutes=15)).isoformat()
            },
            {
                "id": "ev_004",
                "snippet": "Medium score, old",
                "source": "Source 4",
                "score": 0.8,
                "timestamp": (now - timedelta(hours=1)).isoformat()
            }
        ]
        
        normalized = normalize_evidence(raw_evidence)
        
        # Should be ordered by score first, then by recency within same score
        self.assertEqual(normalized[0].id, "ev_002")  # 0.9, newest
        self.assertEqual(normalized[1].id, "ev_001")  # 0.9, oldest
        self.assertEqual(normalized[2].id, "ev_004")  # 0.8, oldest
        self.assertEqual(normalized[3].id, "ev_003")  # 0.7, newest


def main():
    """Run all tests."""
    print("Running Factare summary tests...")
    
    # Create test suite
    suite = unittest.TestSuite()
    
    # Add test cases
    test_classes = [
        TestEvidenceItem,
        TestDecision,
        TestCompareSummary,
        TestNormalizeEvidence,
        TestUtilityFunctions,
        TestCreateCompareSummary,
        TestValidateCompareSummary,
        TestGetSummaryStats,
        TestJSONSerialization,
        TestDeterministicOrdering
    ]
    
    for test_class in test_classes:
        suite.addTest(unittest.TestLoader().loadTestsFromTestCase(test_class))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    if result.wasSuccessful():
        print("\n🎉 All Factare summary tests passed!")
    else:
        print(f"\n❌ {len(result.failures)} test(s) failed, {len(result.errors)} error(s)")
        for failure in result.failures:
            print(f"FAIL: {failure[0]}")
            print(failure[1])
        for error in result.errors:
            print(f"ERROR: {error[0]}")
            print(error[1])
    
    return result.wasSuccessful()


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)