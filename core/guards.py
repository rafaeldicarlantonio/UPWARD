"""
Core guards for data integrity and security.

Provides functions to enforce business rules and prevent unauthorized operations.
"""

import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)
audit_logger = logging.getLogger("audit.external_persistence")


class ExternalPersistenceError(Exception):
    """Raised when attempting to persist external content."""
    pass


def forbid_external_persistence(
    items: List[Dict[str, Any]],
    item_type: str = "item",
    raise_on_external: bool = True
) -> Dict[str, Any]:
    """
    Guard function that prevents external content from being persisted.
    
    Checks if any items contain external provenance (URL markers) and either
    raises an exception or returns a report of blocked items.
    
    Args:
        items: List of items to check (memories, entities, edges, etc.)
        item_type: Type of items being checked (for logging)
        raise_on_external: If True, raises exception on external items.
                          If False, returns report without raising.
        
    Returns:
        Dictionary with check results:
        {
            "checked": int,
            "external_count": int,
            "internal_count": int,
            "external_items": List[Dict],
            "allowed": bool
        }
        
    Raises:
        ExternalPersistenceError: If external items found and raise_on_external=True
        
    Examples:
        >>> # Internal items only - succeeds
        >>> items = [
        ...     {"id": "mem_1", "text": "Internal content"},
        ...     {"id": "mem_2", "text": "More internal content"}
        ... ]
        >>> result = forbid_external_persistence(items)
        >>> # Returns: {"checked": 2, "external_count": 0, "allowed": True}
        
        >>> # External item present - raises
        >>> items = [
        ...     {"id": "mem_1", "text": "Internal"},
        ...     {
        ...         "id": "ext_1", 
        ...         "text": "External",
        ...         "provenance": {"url": "https://example.com"}
        ...     }
        ... ]
        >>> forbid_external_persistence(items)
        >>> # Raises: ExternalPersistenceError
        
        >>> # Check without raising
        >>> result = forbid_external_persistence(items, raise_on_external=False)
        >>> # Returns: {"external_count": 1, "allowed": False, ...}
    """
    if not items:
        return {
            "checked": 0,
            "external_count": 0,
            "internal_count": 0,
            "external_items": [],
            "allowed": True
        }
    
    external_items = []
    
    # Check each item for external provenance markers
    for item in items:
        if _is_external_item(item):
            external_items.append({
                "id": item.get("id", "unknown"),
                "url": _extract_url(item),
                "type": item_type
            })
    
    external_count = len(external_items)
    internal_count = len(items) - external_count
    
    result = {
        "checked": len(items),
        "external_count": external_count,
        "internal_count": internal_count,
        "external_items": external_items,
        "allowed": external_count == 0
    }
    
    # Log the check
    logger.info(
        f"External persistence check: {item_type}, "
        f"total={len(items)}, external={external_count}, internal={internal_count}"
    )
    
    # If external items found, audit and optionally raise
    if external_count > 0:
        audit_logger.warning(
            f"BLOCKED: Attempt to persist {external_count} external {item_type}(s)",
            extra={
                "event": "external_persistence_blocked",
                "item_type": item_type,
                "external_count": external_count,
                "internal_count": internal_count,
                "external_items": external_items,
                "severity": "high"
            }
        )
        
        if raise_on_external:
            raise ExternalPersistenceError(
                f"Cannot persist external content: found {external_count} "
                f"external {item_type}(s) with provenance URLs. "
                f"External content must not be written to internal storage."
            )
    
    return result


def _is_external_item(item: Dict[str, Any]) -> bool:
    """
    Check if an item is external (has provenance URL).
    
    Checks for:
    - provenance.url field
    - source_url field
    - external=True flag
    - metadata.external=True flag
    
    Args:
        item: Item dictionary to check
        
    Returns:
        True if item appears to be external, False otherwise
    """
    # Check for provenance.url
    if isinstance(item.get("provenance"), dict):
        if item["provenance"].get("url"):
            return True
    
    # Check for direct source_url field
    if item.get("source_url"):
        return True
    
    # Check for external flag
    if item.get("external") is True:
        return True
    
    # Check for metadata.external flag
    if isinstance(item.get("metadata"), dict):
        if item["metadata"].get("external") is True:
            return True
    
    # Check for url in metadata
    if isinstance(item.get("metadata"), dict):
        if item["metadata"].get("url"):
            return True
    
    return False


def _extract_url(item: Dict[str, Any]) -> Optional[str]:
    """
    Extract URL from external item.
    
    Args:
        item: Item dictionary
        
    Returns:
        URL string if found, None otherwise
    """
    # Try provenance.url
    if isinstance(item.get("provenance"), dict):
        url = item["provenance"].get("url")
        if url:
            return url
    
    # Try direct source_url
    if item.get("source_url"):
        return item["source_url"]
    
    # Try metadata.url
    if isinstance(item.get("metadata"), dict):
        url = item["metadata"].get("url")
        if url:
            return url
    
    return None


def check_for_external_content(
    memories: Optional[List[Dict[str, Any]]] = None,
    entities: Optional[List[Dict[str, Any]]] = None,
    edges: Optional[List[Dict[str, Any]]] = None,
    raise_on_external: bool = True
) -> Dict[str, Any]:
    """
    Check multiple content types for external items.
    
    Convenience function to check memories, entities, and edges in one call.
    
    Args:
        memories: List of memory items to check
        entities: List of entity items to check
        edges: List of edge items to check
        raise_on_external: If True, raises on first external item found
        
    Returns:
        Dictionary with results for each type:
        {
            "memories": {...result...},
            "entities": {...result...},
            "edges": {...result...},
            "total_external": int,
            "allowed": bool
        }
        
    Raises:
        ExternalPersistenceError: If any external items found and raise_on_external=True
    """
    results = {}
    total_external = 0
    
    # Check memories
    if memories is not None:
        result = forbid_external_persistence(
            memories, 
            item_type="memory",
            raise_on_external=raise_on_external
        )
        results["memories"] = result
        total_external += result["external_count"]
    
    # Check entities
    if entities is not None:
        result = forbid_external_persistence(
            entities,
            item_type="entity", 
            raise_on_external=raise_on_external
        )
        results["entities"] = result
        total_external += result["external_count"]
    
    # Check edges
    if edges is not None:
        result = forbid_external_persistence(
            edges,
            item_type="edge",
            raise_on_external=raise_on_external
        )
        results["edges"] = result
        total_external += result["external_count"]
    
    results["total_external"] = total_external
    results["allowed"] = total_external == 0
    
    return results


def filter_external_items(items: List[Dict[str, Any]]) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Split items into internal and external lists.
    
    Args:
        items: List of items to filter
        
    Returns:
        Tuple of (internal_items, external_items)
    """
    internal = []
    external = []
    
    for item in items:
        if _is_external_item(item):
            external.append(item)
        else:
            internal.append(item)
    
    return internal, external
