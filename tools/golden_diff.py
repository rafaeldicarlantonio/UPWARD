#!/usr/bin/env python3
"""
Golden Set Diff Tool

Show differences between golden sets, highlighting changes to evidence IDs,
expected values, and metadata.

Usage:
    # Diff two versions of a suite
    python tools/golden_diff.py --suite implicate_lift
    
    # Diff specific item
    python tools/golden_diff.py --suite pareto_gate --id golden_pareto_005
    
    # Diff against git commit
    python tools/golden_diff.py --suite contradictions --git-ref HEAD~1
    
    # Show detailed diff with evidence IDs
    python tools/golden_diff.py --suite implicate_lift --verbose
"""

import os
import sys
import json
import argparse
import subprocess
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime

# Add workspace to path
sys.path.insert(0, '/workspace')


class GoldenDiff:
    """Diff golden test sets."""
    
    def __init__(self, base_dir: str = "evals/golden"):
        """
        Initialize golden diff tool.
        
        Args:
            base_dir: Base directory for golden sets
        """
        self.base_dir = Path(base_dir)
    
    def load_golden_set(self, suite: str, git_ref: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Load golden set for suite.
        
        Args:
            suite: Suite name
            git_ref: Optional git reference (e.g., HEAD~1, main)
        
        Returns:
            List of golden items
        """
        golden_file = self.base_dir / suite / "golden_set.jsonl"
        
        if git_ref:
            # Load from git
            try:
                result = subprocess.run(
                    ["git", "show", f"{git_ref}:{golden_file}"],
                    capture_output=True,
                    text=True,
                    check=True
                )
                lines = result.stdout.strip().split('\n')
            except subprocess.CalledProcessError:
                print(f"⚠️  Could not load {suite} from {git_ref}")
                return []
        else:
            # Load from filesystem
            if not golden_file.exists():
                return []
            
            with open(golden_file, 'r') as f:
                lines = [line.strip() for line in f if line.strip()]
        
        items = []
        for line in lines:
            if line:
                items.append(json.loads(line))
        
        return items
    
    def diff_items(
        self,
        old_items: List[Dict[str, Any]],
        new_items: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Compute diff between old and new items.
        
        Returns:
            Dict with added, removed, modified items
        """
        old_by_id = {item["id"]: item for item in old_items}
        new_by_id = {item["id"]: item for item in new_items}
        
        old_ids = set(old_by_id.keys())
        new_ids = set(new_by_id.keys())
        
        added = new_ids - old_ids
        removed = old_ids - new_ids
        common = old_ids & new_ids
        
        modified = []
        for item_id in common:
            old_item = old_by_id[item_id]
            new_item = new_by_id[item_id]
            
            if old_item != new_item:
                changes = self.compute_changes(old_item, new_item)
                modified.append({
                    "id": item_id,
                    "old": old_item,
                    "new": new_item,
                    "changes": changes
                })
        
        return {
            "added": [new_by_id[item_id] for item_id in added],
            "removed": [old_by_id[item_id] for item_id in removed],
            "modified": modified
        }
    
    def compute_changes(
        self,
        old_item: Dict[str, Any],
        new_item: Dict[str, Any]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Compute field-level changes between items.
        
        Returns:
            Dict mapping field names to {old, new} values
        """
        changes = {}
        
        all_keys = set(old_item.keys()) | set(new_item.keys())
        
        for key in all_keys:
            old_val = old_item.get(key)
            new_val = new_item.get(key)
            
            if old_val != new_val:
                changes[key] = {
                    "old": old_val,
                    "new": new_val
                }
        
        return changes
    
    def format_diff(
        self,
        suite: str,
        diff: Dict[str, Any],
        verbose: bool = False
    ) -> str:
        """
        Format diff for display.
        
        Args:
            suite: Suite name
            diff: Diff result
            verbose: Show detailed changes
        
        Returns:
            Formatted diff string
        """
        lines = []
        
        lines.append("=" * 80)
        lines.append(f"Golden Set Diff: {suite}")
        lines.append("=" * 80)
        lines.append("")
        
        # Summary
        lines.append("Summary:")
        lines.append(f"  Added:    {len(diff['added'])} items")
        lines.append(f"  Removed:  {len(diff['removed'])} items")
        lines.append(f"  Modified: {len(diff['modified'])} items")
        lines.append("")
        
        # Added items
        if diff["added"]:
            lines.append("➕ Added Items:")
            lines.append("-" * 80)
            for item in diff["added"]:
                lines.append(f"  + {item['id']}")
                if verbose:
                    lines.extend(self.format_item(item, indent=4))
                else:
                    lines.append(f"    Added by: {item.get('approved_by', 'N/A')}")
                    lines.append(f"    Rationale: {item.get('rationale', 'N/A')}")
                lines.append("")
        
        # Removed items
        if diff["removed"]:
            lines.append("➖ Removed Items:")
            lines.append("-" * 80)
            for item in diff["removed"]:
                lines.append(f"  - {item['id']}")
                if verbose:
                    lines.extend(self.format_item(item, indent=4))
                lines.append("")
        
        # Modified items
        if diff["modified"]:
            lines.append("📝 Modified Items:")
            lines.append("-" * 80)
            for mod in diff["modified"]:
                lines.append(f"  ~ {mod['id']}")
                lines.append(f"    Version: {mod['old'].get('version', 1)} → {mod['new'].get('version', 2)}")
                
                if "updated_by" in mod["new"]:
                    lines.append(f"    Updated by: {mod['new']['updated_by']}")
                if "update_rationale" in mod["new"]:
                    lines.append(f"    Rationale: {mod['new']['update_rationale']}")
                
                lines.append("")
                lines.append("    Changes:")
                for field, change in mod["changes"].items():
                    # Skip metadata fields
                    if field in ["updated_at", "updated_by", "update_rationale", "version"]:
                        continue
                    
                    lines.append(f"      {field}:")
                    
                    # Special formatting for evidence IDs
                    if field == "expected_sources" or "source" in field.lower():
                        old_sources = change["old"] if isinstance(change["old"], list) else []
                        new_sources = change["new"] if isinstance(change["new"], list) else []
                        
                        removed_sources = set(old_sources) - set(new_sources)
                        added_sources = set(new_sources) - set(old_sources)
                        
                        if removed_sources:
                            lines.append(f"        - Removed: {', '.join(removed_sources)}")
                        if added_sources:
                            lines.append(f"        + Added: {', '.join(added_sources)}")
                    else:
                        lines.append(f"        - Old: {self.format_value(change['old'])}")
                        lines.append(f"        + New: {self.format_value(change['new'])}")
                
                lines.append("")
        
        if not diff["added"] and not diff["removed"] and not diff["modified"]:
            lines.append("✅ No changes detected")
        
        return "\n".join(lines)
    
    def format_item(self, item: Dict[str, Any], indent: int = 0) -> List[str]:
        """Format a single item with indentation."""
        lines = []
        prefix = " " * indent
        
        # Key fields
        important_fields = ["query", "hypothesis", "expected_sources", "expected_score", 
                          "expected_persisted", "expected_contradiction", "category"]
        
        for field in important_fields:
            if field in item:
                lines.append(f"{prefix}{field}: {self.format_value(item[field])}")
        
        return lines
    
    def format_value(self, value: Any) -> str:
        """Format a value for display."""
        if isinstance(value, list):
            if len(value) <= 3:
                return ", ".join(str(v) for v in value)
            else:
                return f"{', '.join(str(v) for v in value[:3])}, ... ({len(value)} total)"
        elif isinstance(value, str) and len(value) > 60:
            return value[:60] + "..."
        else:
            return str(value)
    
    def diff_suite(
        self,
        suite: str,
        git_ref: Optional[str] = None,
        item_id: Optional[str] = None,
        verbose: bool = False
    ) -> str:
        """
        Diff a suite.
        
        Args:
            suite: Suite name
            git_ref: Optional git reference to compare against
            item_id: Optional specific item to diff
            verbose: Show detailed changes
        
        Returns:
            Formatted diff
        """
        # Load old and new versions
        old_items = self.load_golden_set(suite, git_ref=git_ref or "HEAD")
        new_items = self.load_golden_set(suite)
        
        # Filter to specific item if requested
        if item_id:
            old_items = [item for item in old_items if item["id"] == item_id]
            new_items = [item for item in new_items if item["id"] == item_id]
            
            if not old_items and not new_items:
                return f"❌ Item '{item_id}' not found in {suite}"
        
        # Compute diff
        diff = self.diff_items(old_items, new_items)
        
        # Format
        return self.format_diff(suite, diff, verbose=verbose)
    
    def generate_review_summary(self, suite: str) -> str:
        """
        Generate a summary for review.
        
        Args:
            suite: Suite name
        
        Returns:
            Review summary with approval checklist
        """
        lines = []
        
        lines.append("=" * 80)
        lines.append(f"Golden Set Review Summary: {suite}")
        lines.append("=" * 80)
        lines.append("")
        
        # Get current items
        items = self.load_golden_set(suite)
        
        lines.append(f"Total Items: {len(items)}")
        lines.append("")
        
        # Recent changes
        recent = sorted(
            [item for item in items if "updated_at" in item or "added_at" in item],
            key=lambda x: x.get("updated_at", x.get("added_at", "")),
            reverse=True
        )[:10]
        
        if recent:
            lines.append("Recent Changes (last 10):")
            lines.append("-" * 80)
            for item in recent:
                timestamp = item.get("updated_at", item.get("added_at", "N/A"))
                approver = item.get("updated_by", item.get("approved_by", "N/A"))
                lines.append(f"  {item['id']}")
                lines.append(f"    Timestamp: {timestamp}")
                lines.append(f"    Approver: {approver}")
                lines.append(f"    Version: {item.get('version', 1)}")
                lines.append("")
        
        # Review checklist
        lines.append("Review Checklist:")
        lines.append("-" * 80)
        lines.append("  [ ] All IDs follow 'golden_*' naming convention")
        lines.append("  [ ] All changes have human approval (approved_by field)")
        lines.append("  [ ] All changes have clear rationale")
        lines.append("  [ ] Evidence IDs are valid and accessible")
        lines.append("  [ ] Expected values match actual system behavior")
        lines.append("  [ ] No duplicate IDs")
        lines.append("  [ ] Version numbers are sequential")
        lines.append("")
        
        return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Diff golden test sets",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Diff current vs HEAD
  python tools/golden_diff.py --suite implicate_lift
  
  # Diff against specific commit
  python tools/golden_diff.py --suite pareto_gate --git-ref HEAD~3
  
  # Diff specific item
  python tools/golden_diff.py --suite contradictions --id golden_contra_002
  
  # Verbose diff with full details
  python tools/golden_diff.py --suite implicate_lift --verbose
  
  # Generate review summary
  python tools/golden_diff.py --suite pareto_gate --review
        """
    )
    
    parser.add_argument("--suite", required=True,
                       choices=["implicate_lift", "contradictions", "external_compare", "pareto_gate"],
                       help="Suite name")
    parser.add_argument("--id", dest="item_id", help="Specific item ID to diff")
    parser.add_argument("--git-ref", help="Git reference to compare against (default: HEAD)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show detailed changes")
    parser.add_argument("--review", action="store_true", help="Generate review summary")
    parser.add_argument("--base-dir", default="evals/golden", help="Base directory for golden sets")
    
    args = parser.parse_args()
    
    # Create differ
    differ = GoldenDiff(base_dir=args.base_dir)
    
    try:
        if args.review:
            # Generate review summary
            output = differ.generate_review_summary(args.suite)
        else:
            # Generate diff
            output = differ.diff_suite(
                args.suite,
                git_ref=args.git_ref,
                item_id=args.item_id,
                verbose=args.verbose
            )
        
        print(output)
    
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
