#!/usr/bin/env python3
"""
Golden Set Addition Tool

Add or update golden test cases with stable IDs, validation, and human approval.

Usage:
    # Add a new golden item
    python tools/golden_add.py \
        --suite implicate_lift \
        --id golden_bridge_001 \
        --query "How are entity A and B related?" \
        --expected-sources "src_123,src_456" \
        --rationale "Tests entity bridging via temporal link" \
        --approved-by "jane.doe@example.com"
    
    # Update existing item
    python tools/golden_add.py \
        --suite pareto_gate \
        --id golden_pareto_005 \
        --update \
        --expected-score 0.75 \
        --rationale "Updated threshold after model improvements" \
        --approved-by "john.smith@example.com"
    
    # Interactive mode
    python tools/golden_add.py --interactive
"""

import os
import sys
import json
import argparse
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

# Add workspace to path
sys.path.insert(0, '/workspace')


class GoldenSetManager:
    """Manages golden test set additions and updates."""
    
    def __init__(self, base_dir: str = "evals/golden"):
        """
        Initialize golden set manager.
        
        Args:
            base_dir: Base directory for golden sets
        """
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        
        # Suite-specific directories
        self.suites = {
            "implicate_lift": self.base_dir / "implicate_lift",
            "contradictions": self.base_dir / "contradictions",
            "external_compare": self.base_dir / "external_compare",
            "pareto_gate": self.base_dir / "pareto_gate"
        }
        
        # Create suite directories
        for suite_dir in self.suites.values():
            suite_dir.mkdir(parents=True, exist_ok=True)
    
    def get_golden_file(self, suite: str) -> Path:
        """Get path to golden set file for suite."""
        if suite not in self.suites:
            raise ValueError(f"Unknown suite: {suite}")
        return self.suites[suite] / "golden_set.jsonl"
    
    def load_golden_set(self, suite: str) -> List[Dict[str, Any]]:
        """Load golden set for suite."""
        golden_file = self.get_golden_file(suite)
        
        if not golden_file.exists():
            return []
        
        items = []
        with open(golden_file, 'r') as f:
            for line in f:
                if line.strip():
                    items.append(json.loads(line))
        
        return items
    
    def save_golden_set(self, suite: str, items: List[Dict[str, Any]]):
        """Save golden set for suite."""
        golden_file = self.get_golden_file(suite)
        
        with open(golden_file, 'w') as f:
            for item in items:
                f.write(json.dumps(item) + '\n')
    
    def validate_id(self, suite: str, item_id: str, is_update: bool = False) -> bool:
        """
        Validate golden item ID.
        
        Args:
            suite: Suite name
            item_id: Item ID to validate
            is_update: Whether this is an update (ID must exist)
        
        Returns:
            True if valid, raises ValueError otherwise
        """
        # Check ID format
        if not item_id.startswith("golden_"):
            raise ValueError("Golden item IDs must start with 'golden_'")
        
        if not item_id.replace("_", "").replace("golden", "").isalnum():
            raise ValueError("Golden item IDs must be alphanumeric (with underscores)")
        
        # Check uniqueness
        existing = self.load_golden_set(suite)
        existing_ids = {item["id"] for item in existing}
        
        if is_update:
            if item_id not in existing_ids:
                raise ValueError(f"Cannot update: ID '{item_id}' does not exist")
        else:
            if item_id in existing_ids:
                raise ValueError(f"ID '{item_id}' already exists. Use --update to modify.")
        
        return True
    
    def add_item(
        self,
        suite: str,
        item_id: str,
        data: Dict[str, Any],
        approved_by: str,
        rationale: str
    ) -> Dict[str, Any]:
        """
        Add a new golden item.
        
        Args:
            suite: Suite name
            item_id: Unique item ID
            data: Item data
            approved_by: Email of approver
            rationale: Reason for addition
        
        Returns:
            The added item with metadata
        """
        # Validate ID
        self.validate_id(suite, item_id, is_update=False)
        
        # Create item with metadata
        item = {
            "id": item_id,
            "suite": suite,
            "added_at": datetime.utcnow().isoformat() + "Z",
            "approved_by": approved_by,
            "rationale": rationale,
            "version": 1,
            **data
        }
        
        # Load existing and append
        items = self.load_golden_set(suite)
        items.append(item)
        
        # Save
        self.save_golden_set(suite, items)
        
        print(f"✅ Added golden item '{item_id}' to {suite}")
        print(f"   Approved by: {approved_by}")
        print(f"   Rationale: {rationale}")
        
        return item
    
    def update_item(
        self,
        suite: str,
        item_id: str,
        updates: Dict[str, Any],
        approved_by: str,
        rationale: str
    ) -> Dict[str, Any]:
        """
        Update an existing golden item.
        
        Args:
            suite: Suite name
            item_id: Item ID to update
            updates: Fields to update
            approved_by: Email of approver
            rationale: Reason for update
        
        Returns:
            The updated item
        """
        # Validate ID exists
        self.validate_id(suite, item_id, is_update=True)
        
        # Load existing
        items = self.load_golden_set(suite)
        
        # Find and update item
        updated_item = None
        for i, item in enumerate(items):
            if item["id"] == item_id:
                # Preserve history
                old_version = item.get("version", 1)
                
                # Update item
                item.update(updates)
                item["updated_at"] = datetime.utcnow().isoformat() + "Z"
                item["updated_by"] = approved_by
                item["update_rationale"] = rationale
                item["version"] = old_version + 1
                
                items[i] = item
                updated_item = item
                break
        
        # Save
        self.save_golden_set(suite, items)
        
        print(f"✅ Updated golden item '{item_id}' in {suite}")
        print(f"   Version: {updated_item['version']}")
        print(f"   Approved by: {approved_by}")
        print(f"   Rationale: {rationale}")
        
        return updated_item
    
    def get_item(self, suite: str, item_id: str) -> Optional[Dict[str, Any]]:
        """Get a golden item by ID."""
        items = self.load_golden_set(suite)
        for item in items:
            if item["id"] == item_id:
                return item
        return None
    
    def list_items(self, suite: str) -> List[Dict[str, Any]]:
        """List all golden items in suite."""
        return self.load_golden_set(suite)


def validate_email(email: str) -> bool:
    """Validate email format."""
    if not email or '@' not in email:
        raise ValueError("Invalid email format")
    return True


def interactive_add(manager: GoldenSetManager):
    """Interactive mode for adding golden items."""
    print("=" * 60)
    print("Golden Set Interactive Addition")
    print("=" * 60)
    print()
    
    # Select suite
    print("Available suites:")
    suites = list(manager.suites.keys())
    for i, suite in enumerate(suites, 1):
        print(f"  {i}. {suite}")
    
    suite_idx = int(input("\nSelect suite (1-4): ")) - 1
    suite = suites[suite_idx]
    
    # Get ID
    item_id = input("\nGolden item ID (must start with 'golden_'): ")
    
    # Check if update
    existing = manager.get_item(suite, item_id)
    is_update = existing is not None
    
    if is_update:
        print(f"\n⚠️  Item '{item_id}' already exists!")
        print(f"Current version: {existing.get('version', 1)}")
        update = input("Update existing item? (yes/no): ").lower() == 'yes'
        if not update:
            print("Cancelled.")
            return
    
    # Get data based on suite
    data = {}
    
    if suite == "implicate_lift":
        data["query"] = input("\nQuery: ")
        sources = input("Expected source IDs (comma-separated): ")
        data["expected_sources"] = [s.strip() for s in sources.split(",")]
        data["category"] = "implicate_lift"
    
    elif suite == "contradictions":
        data["query"] = input("\nQuery: ")
        data["expected_contradiction"] = input("Expected contradiction? (yes/no): ").lower() == 'yes'
        if data["expected_contradiction"]:
            claims = input("Conflicting claims (comma-separated): ")
            data["expected_claims"] = [c.strip() for c in claims.split(",")]
        data["category"] = "contradiction"
    
    elif suite == "external_compare":
        data["query"] = input("\nQuery: ")
        data["expected_mode"] = input("Expected mode (off/on): ")
        data["expected_parity"] = input("Expected parity? (yes/no): ").lower() == 'yes'
        data["category"] = "external_compare"
    
    elif suite == "pareto_gate":
        data["hypothesis"] = input("\nHypothesis: ")
        data["expected_score"] = float(input("Expected score (0-1): "))
        data["expected_persisted"] = input("Expected persisted? (yes/no): ").lower() == 'yes'
        data["category"] = "pareto_gate"
    
    # Get approval info
    print()
    rationale = input("Rationale for this change: ")
    approved_by = input("Your email: ")
    
    try:
        validate_email(approved_by)
    except ValueError as e:
        print(f"\n❌ {e}")
        return
    
    # Confirm
    print("\n" + "=" * 60)
    print("Confirm Addition/Update")
    print("=" * 60)
    print(f"Suite: {suite}")
    print(f"ID: {item_id}")
    print(f"Action: {'Update' if is_update else 'Add'}")
    print(f"Data: {json.dumps(data, indent=2)}")
    print(f"Rationale: {rationale}")
    print(f"Approved by: {approved_by}")
    print()
    
    confirm = input("Proceed? (yes/no): ").lower()
    
    if confirm == 'yes':
        if is_update:
            manager.update_item(suite, item_id, data, approved_by, rationale)
        else:
            manager.add_item(suite, item_id, data, approved_by, rationale)
    else:
        print("Cancelled.")


def main():
    parser = argparse.ArgumentParser(
        description="Add or update golden test cases",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Add implicate lift item
  python tools/golden_add.py \\
    --suite implicate_lift \\
    --id golden_bridge_001 \\
    --query "How are A and B related?" \\
    --expected-sources "src_123,src_456" \\
    --rationale "Entity bridging test" \\
    --approved-by "user@example.com"
  
  # Update pareto gate item
  python tools/golden_add.py \\
    --suite pareto_gate \\
    --id golden_pareto_005 \\
    --update \\
    --expected-score 0.75 \\
    --rationale "Threshold adjustment" \\
    --approved-by "user@example.com"
  
  # Interactive mode
  python tools/golden_add.py --interactive
        """
    )
    
    parser.add_argument("--suite", choices=["implicate_lift", "contradictions", "external_compare", "pareto_gate"],
                       help="Suite name")
    parser.add_argument("--id", dest="item_id", help="Unique golden item ID (must start with 'golden_')")
    parser.add_argument("--update", action="store_true", help="Update existing item instead of adding")
    parser.add_argument("--interactive", action="store_true", help="Interactive mode")
    
    # Common fields
    parser.add_argument("--approved-by", help="Email of approver (required)")
    parser.add_argument("--rationale", help="Reason for addition/update (required)")
    
    # Suite-specific fields
    parser.add_argument("--query", help="Query text")
    parser.add_argument("--hypothesis", help="Hypothesis text (pareto_gate)")
    parser.add_argument("--expected-sources", help="Comma-separated source IDs (implicate_lift)")
    parser.add_argument("--expected-contradiction", type=bool, help="Expected contradiction (contradictions)")
    parser.add_argument("--expected-claims", help="Comma-separated claims (contradictions)")
    parser.add_argument("--expected-mode", help="Expected mode (external_compare)")
    parser.add_argument("--expected-parity", type=bool, help="Expected parity (external_compare)")
    parser.add_argument("--expected-score", type=float, help="Expected score (pareto_gate)")
    parser.add_argument("--expected-persisted", type=bool, help="Expected persisted (pareto_gate)")
    
    # Other
    parser.add_argument("--base-dir", default="evals/golden", help="Base directory for golden sets")
    
    args = parser.parse_args()
    
    # Create manager
    manager = GoldenSetManager(base_dir=args.base_dir)
    
    # Interactive mode
    if args.interactive:
        interactive_add(manager)
        return
    
    # Validate required args
    if not args.suite or not args.item_id:
        parser.error("--suite and --id are required (or use --interactive)")
    
    if not args.approved_by or not args.rationale:
        parser.error("--approved-by and --rationale are required")
    
    try:
        validate_email(args.approved_by)
    except ValueError as e:
        parser.error(str(e))
    
    # Build data based on suite
    data = {}
    
    if args.suite == "implicate_lift":
        if not args.query or not args.expected_sources:
            parser.error("--query and --expected-sources required for implicate_lift")
        data["query"] = args.query
        data["expected_sources"] = [s.strip() for s in args.expected_sources.split(",")]
        data["category"] = "implicate_lift"
    
    elif args.suite == "contradictions":
        if not args.query:
            parser.error("--query required for contradictions")
        data["query"] = args.query
        if args.expected_contradiction is not None:
            data["expected_contradiction"] = args.expected_contradiction
        if args.expected_claims:
            data["expected_claims"] = [c.strip() for c in args.expected_claims.split(",")]
        data["category"] = "contradiction"
    
    elif args.suite == "external_compare":
        if not args.query:
            parser.error("--query required for external_compare")
        data["query"] = args.query
        if args.expected_mode:
            data["expected_mode"] = args.expected_mode
        if args.expected_parity is not None:
            data["expected_parity"] = args.expected_parity
        data["category"] = "external_compare"
    
    elif args.suite == "pareto_gate":
        if not args.hypothesis:
            parser.error("--hypothesis required for pareto_gate")
        data["hypothesis"] = args.hypothesis
        if args.expected_score is not None:
            data["expected_score"] = args.expected_score
        if args.expected_persisted is not None:
            data["expected_persisted"] = args.expected_persisted
        data["category"] = "pareto_gate"
    
    # Add or update
    try:
        if args.update:
            manager.update_item(args.suite, args.item_id, data, args.approved_by, args.rationale)
        else:
            manager.add_item(args.suite, args.item_id, data, args.approved_by, args.rationale)
    except ValueError as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
