#!/usr/bin/env python3
"""
Demo script for external sources configuration loader.

Demonstrates loading, validation, and accessing configurations.
"""

import sys
from pathlib import Path

# Add workspace to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.config_loader import get_loader


def main():
    print("=" * 70)
    print("External Sources Configuration Loader Demo")
    print("=" * 70)
    print()
    
    # Get loader instance
    print("Loading configurations...")
    loader = get_loader()
    print("✓ Configurations loaded successfully\n")
    
    # Display whitelist
    print("EXTERNAL SOURCES WHITELIST")
    print("-" * 70)
    sources = loader.get_whitelist()
    print(f"Found {len(sources)} enabled sources (sorted by priority):\n")
    
    for i, source in enumerate(sources, 1):
        print(f"{i}. {source.label}")
        print(f"   ID: {source.source_id}")
        print(f"   Priority: {source.priority}")
        print(f"   URL Pattern: {source.url_pattern}")
        print(f"   Max Snippet: {source.max_snippet_chars} chars")
        print(f"   Enabled: {source.enabled}")
        print()
    
    # Display disabled sources
    all_sources = loader.get_whitelist(enabled_only=False)
    disabled = [s for s in all_sources if not s.enabled]
    if disabled:
        print(f"Disabled sources: {', '.join(s.label for s in disabled)}\n")
    
    # Display policy
    print("COMPARE POLICY")
    print("-" * 70)
    policy = loader.get_compare_policy()
    
    print(f"Max external sources per run: {policy.max_external_sources_per_run}")
    print(f"Max total external chars: {policy.max_total_external_chars}")
    print(f"Timeout per request: {policy.timeout_ms_per_request}ms")
    print(f"Rate limit per domain: {policy.rate_limit_per_domain_per_min}/min")
    print(f"Tie-break strategy: {policy.tie_break}")
    print(f"\nAllowed roles for external:")
    for role in policy.allowed_roles_for_external:
        print(f"  • {role}")
    
    print(f"\nRedaction patterns: {len(policy.redact_patterns)}")
    for i, pattern in enumerate(policy.redact_patterns, 1):
        print(f"  {i}. {pattern}")
    
    print()
    
    # Test specific source lookup
    print("SOURCE LOOKUP")
    print("-" * 70)
    test_id = "wikipedia"
    source = loader.get_source_by_id(test_id)
    if source:
        print(f"✓ Found '{test_id}':")
        print(f"  Label: {source.label}")
        print(f"  Priority: {source.priority}")
        print(f"  Max chars: {source.max_snippet_chars}")
    else:
        print(f"✗ Source '{test_id}' not found")
    
    print()
    
    # Export as dict
    print("EXPORT")
    print("-" * 70)
    config_dict = loader.to_dict()
    print(f"✓ Exported configuration:")
    print(f"  Whitelist entries: {len(config_dict['whitelist'])}")
    print(f"  Policy fields: {len(config_dict['policy'])}")
    
    print()
    print("=" * 70)
    print("Demo complete!")
    print("=" * 70)


if __name__ == "__main__":
    main()
