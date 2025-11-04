#!/usr/bin/env python3
"""
Unit tests for golden set curation tools.

Tests:
1. Golden set addition
2. ID validation
3. Update functionality
4. Diff generation
5. Review summary
"""

import os
import sys
import json
import unittest
import tempfile
import shutil
from pathlib import Path

# Add workspace to path
sys.path.insert(0, '/workspace')

# Import after path setup
sys.path.insert(0, '/workspace/tools')
from golden_add import GoldenSetManager, validate_email
from golden_diff import GoldenDiff


class TestGoldenSetManager(unittest.TestCase):
    """Test golden set manager."""
    
    def setUp(self):
        """Set up test environment."""
        # Create temporary directory
        self.temp_dir = tempfile.mkdtemp()
        self.manager = GoldenSetManager(base_dir=self.temp_dir)
    
    def tearDown(self):
        """Clean up test environment."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_create_directories(self):
        """Test that manager creates suite directories."""
        for suite in ["implicate_lift", "contradictions", "external_compare", "pareto_gate"]:
            suite_dir = Path(self.temp_dir) / suite
            self.assertTrue(suite_dir.exists())
    
    def test_add_item(self):
        """Test adding a golden item."""
        item = self.manager.add_item(
            suite="implicate_lift",
            item_id="golden_test_001",
            data={
                "query": "Test query",
                "expected_sources": ["src_001", "src_002"],
                "category": "implicate_lift"
            },
            approved_by="test@example.com",
            rationale="Test item"
        )
        
        self.assertEqual(item["id"], "golden_test_001")
        self.assertEqual(item["suite"], "implicate_lift")
        self.assertEqual(item["version"], 1)
        self.assertIn("added_at", item)
    
    def test_validate_id_format(self):
        """Test ID format validation."""
        # Valid ID
        self.assertTrue(
            self.manager.validate_id("implicate_lift", "golden_test_001")
        )
        
        # Invalid - doesn't start with golden_
        with self.assertRaises(ValueError):
            self.manager.validate_id("implicate_lift", "invalid_001")
        
        # Invalid - special characters
        with self.assertRaises(ValueError):
            self.manager.validate_id("implicate_lift", "golden_test@001")
    
    def test_validate_id_uniqueness(self):
        """Test ID uniqueness validation."""
        # Add first item
        self.manager.add_item(
            suite="implicate_lift",
            item_id="golden_test_001",
            data={"query": "Test"},
            approved_by="test@example.com",
            rationale="Test"
        )
        
        # Try to add duplicate
        with self.assertRaises(ValueError) as cm:
            self.manager.validate_id("implicate_lift", "golden_test_001", is_update=False)
        
        self.assertIn("already exists", str(cm.exception))
    
    def test_update_item(self):
        """Test updating an existing item."""
        # Add item
        self.manager.add_item(
            suite="implicate_lift",
            item_id="golden_test_001",
            data={
                "query": "Original query",
                "expected_sources": ["src_001"]
            },
            approved_by="original@example.com",
            rationale="Original"
        )
        
        # Update item
        updated = self.manager.update_item(
            suite="implicate_lift",
            item_id="golden_test_001",
            updates={
                "query": "Updated query",
                "expected_sources": ["src_001", "src_002"]
            },
            approved_by="updater@example.com",
            rationale="Added source"
        )
        
        self.assertEqual(updated["query"], "Updated query")
        self.assertEqual(updated["version"], 2)
        self.assertIn("updated_at", updated)
        self.assertEqual(updated["updated_by"], "updater@example.com")
    
    def test_update_nonexistent_item(self):
        """Test updating non-existent item fails."""
        with self.assertRaises(ValueError) as cm:
            self.manager.validate_id("implicate_lift", "golden_nonexistent", is_update=True)
        
        self.assertIn("does not exist", str(cm.exception))
    
    def test_get_item(self):
        """Test retrieving an item."""
        # Add item
        self.manager.add_item(
            suite="implicate_lift",
            item_id="golden_test_001",
            data={"query": "Test"},
            approved_by="test@example.com",
            rationale="Test"
        )
        
        # Retrieve item
        item = self.manager.get_item("implicate_lift", "golden_test_001")
        
        self.assertIsNotNone(item)
        self.assertEqual(item["id"], "golden_test_001")
    
    def test_list_items(self):
        """Test listing all items."""
        # Add multiple items
        for i in range(3):
            self.manager.add_item(
                suite="implicate_lift",
                item_id=f"golden_test_{i:03d}",
                data={"query": f"Test {i}"},
                approved_by="test@example.com",
                rationale=f"Test {i}"
            )
        
        items = self.manager.list_items("implicate_lift")
        
        self.assertEqual(len(items), 3)
        self.assertEqual(items[0]["id"], "golden_test_000")
        self.assertEqual(items[2]["id"], "golden_test_002")


class TestEmailValidation(unittest.TestCase):
    """Test email validation."""
    
    def test_valid_email(self):
        """Test valid email passes."""
        self.assertTrue(validate_email("user@example.com"))
    
    def test_invalid_email_no_at(self):
        """Test email without @ fails."""
        with self.assertRaises(ValueError):
            validate_email("invalid.email.com")
    
    def test_invalid_email_empty(self):
        """Test empty email fails."""
        with self.assertRaises(ValueError):
            validate_email("")


class TestGoldenDiff(unittest.TestCase):
    """Test golden diff tool."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.manager = GoldenSetManager(base_dir=self.temp_dir)
        self.differ = GoldenDiff(base_dir=self.temp_dir)
    
    def tearDown(self):
        """Clean up test environment."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_diff_items_added(self):
        """Test diff detects added items."""
        old_items = []
        new_items = [
            {"id": "golden_test_001", "query": "Test"}
        ]
        
        diff = self.differ.diff_items(old_items, new_items)
        
        self.assertEqual(len(diff["added"]), 1)
        self.assertEqual(len(diff["removed"]), 0)
        self.assertEqual(len(diff["modified"]), 0)
    
    def test_diff_items_removed(self):
        """Test diff detects removed items."""
        old_items = [
            {"id": "golden_test_001", "query": "Test"}
        ]
        new_items = []
        
        diff = self.differ.diff_items(old_items, new_items)
        
        self.assertEqual(len(diff["added"]), 0)
        self.assertEqual(len(diff["removed"]), 1)
        self.assertEqual(len(diff["modified"]), 0)
    
    def test_diff_items_modified(self):
        """Test diff detects modified items."""
        old_items = [
            {"id": "golden_test_001", "query": "Old query", "version": 1}
        ]
        new_items = [
            {"id": "golden_test_001", "query": "New query", "version": 2}
        ]
        
        diff = self.differ.diff_items(old_items, new_items)
        
        self.assertEqual(len(diff["added"]), 0)
        self.assertEqual(len(diff["removed"]), 0)
        self.assertEqual(len(diff["modified"]), 1)
        
        mod = diff["modified"][0]
        self.assertEqual(mod["id"], "golden_test_001")
        self.assertIn("query", mod["changes"])
        self.assertEqual(mod["changes"]["query"]["old"], "Old query")
        self.assertEqual(mod["changes"]["query"]["new"], "New query")
    
    def test_compute_changes(self):
        """Test computing field-level changes."""
        old_item = {
            "id": "golden_test_001",
            "query": "Old",
            "expected_sources": ["src_001"]
        }
        new_item = {
            "id": "golden_test_001",
            "query": "New",
            "expected_sources": ["src_001", "src_002"]
        }
        
        changes = self.differ.compute_changes(old_item, new_item)
        
        self.assertIn("query", changes)
        self.assertIn("expected_sources", changes)
        self.assertNotIn("id", changes)
    
    def test_format_diff(self):
        """Test diff formatting."""
        diff = {
            "added": [{"id": "golden_new_001", "approved_by": "test@example.com", "rationale": "Test"}],
            "removed": [{"id": "golden_old_001"}],
            "modified": [
                {
                    "id": "golden_test_001",
                    "old": {"version": 1, "query": "Old"},
                    "new": {"version": 2, "query": "New", "updated_by": "test@example.com"},
                    "changes": {"query": {"old": "Old", "new": "New"}}
                }
            ]
        }
        
        output = self.differ.format_diff("implicate_lift", diff)
        
        self.assertIn("Golden Set Diff", output)
        self.assertIn("Added:    1 items", output)
        self.assertIn("Removed:  1 items", output)
        self.assertIn("Modified: 1 items", output)
        self.assertIn("golden_new_001", output)
        self.assertIn("golden_old_001", output)
        self.assertIn("golden_test_001", output)


class TestWorkflow(unittest.TestCase):
    """Test complete curation workflow."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.manager = GoldenSetManager(base_dir=self.temp_dir)
        self.differ = GoldenDiff(base_dir=self.temp_dir)
    
    def tearDown(self):
        """Clean up test environment."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_add_review_update_workflow(self):
        """Test full workflow: add, review, update."""
        # Step 1: Add item
        item1 = self.manager.add_item(
            suite="implicate_lift",
            item_id="golden_workflow_001",
            data={
                "query": "Initial query",
                "expected_sources": ["src_001", "src_002"],
                "category": "implicate_lift"
            },
            approved_by="creator@example.com",
            rationale="Initial item"
        )
        
        self.assertEqual(item1["version"], 1)
        
        # Step 2: Review (diff)
        items_v1 = self.manager.list_items("implicate_lift")
        self.assertEqual(len(items_v1), 1)
        
        # Step 3: Update item
        item2 = self.manager.update_item(
            suite="implicate_lift",
            item_id="golden_workflow_001",
            updates={
                "expected_sources": ["src_001", "src_002", "src_003"]
            },
            approved_by="updater@example.com",
            rationale="Added src_003"
        )
        
        self.assertEqual(item2["version"], 2)
        self.assertEqual(len(item2["expected_sources"]), 3)
        
        # Step 4: Diff
        diff = self.differ.diff_items([item1], [item2])
        
        self.assertEqual(len(diff["modified"]), 1)
        self.assertIn("expected_sources", diff["modified"][0]["changes"])


class TestAcceptanceCriteria(unittest.TestCase):
    """Test acceptance criteria."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.manager = GoldenSetManager(base_dir=self.temp_dir)
        self.differ = GoldenDiff(base_dir=self.temp_dir)
    
    def tearDown(self):
        """Clean up test environment."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_unique_id_enforcement(self):
        """Test that adding enforces unique IDs."""
        # Add first item
        self.manager.add_item(
            suite="implicate_lift",
            item_id="golden_unique_001",
            data={"query": "Test"},
            approved_by="test@example.com",
            rationale="Test"
        )
        
        # Try to add duplicate
        with self.assertRaises(ValueError) as cm:
            self.manager.add_item(
                suite="implicate_lift",
                item_id="golden_unique_001",
                data={"query": "Duplicate"},
                approved_by="test@example.com",
                rationale="Duplicate"
            )
        
        self.assertIn("already exists", str(cm.exception))
    
    def test_diff_shows_evidence_id_changes(self):
        """Test that diffs show before/after evidence IDs."""
        # Create old and new versions
        old_item = {
            "id": "golden_evidence_001",
            "expected_sources": ["src_old_001", "src_old_002"],
            "version": 1
        }
        new_item = {
            "id": "golden_evidence_001",
            "expected_sources": ["src_old_002", "src_new_003"],
            "version": 2
        }
        
        # Compute diff
        diff = self.differ.diff_items([old_item], [new_item])
        
        # Check changes
        self.assertEqual(len(diff["modified"]), 1)
        mod = diff["modified"][0]
        
        self.assertIn("expected_sources", mod["changes"])
        old_sources = mod["changes"]["expected_sources"]["old"]
        new_sources = mod["changes"]["expected_sources"]["new"]
        
        self.assertIn("src_old_001", old_sources)
        self.assertNotIn("src_old_001", new_sources)
        self.assertIn("src_new_003", new_sources)
        self.assertNotIn("src_new_003", old_sources)
    
    def test_human_approval_required(self):
        """Test that human approval is required."""
        # Should succeed with approval
        item = self.manager.add_item(
            suite="implicate_lift",
            item_id="golden_approval_001",
            data={"query": "Test"},
            approved_by="approver@example.com",
            rationale="Approved"
        )
        
        self.assertEqual(item["approved_by"], "approver@example.com")
        self.assertEqual(item["rationale"], "Approved")


if __name__ == "__main__":
    unittest.main()
