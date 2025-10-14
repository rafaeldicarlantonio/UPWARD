# core/factare/summary.py — Compare summary schema and normalization utilities

import hashlib
import json
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional, Union
from datetime import datetime
from urllib.parse import urlparse

# Configuration constants
MAX_EVIDENCE_ITEMS = 50
MAX_EXTERNAL_TEXT_LENGTH = 500
MAX_INTERNAL_TEXT_LENGTH = 1000
HASH_LENGTH = 8

@dataclass
class EvidenceItem:
    """Individual evidence item in a compare summary."""
    id: str
    snippet: str
    source: str
    score: float
    is_external: bool = False
    url: Optional[str] = None
    timestamp: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None

@dataclass
class Decision:
    """Decision made in a compare summary."""
    verdict: str  # "stance_a", "stance_b", "inconclusive", "insufficient_evidence"
    confidence: float  # 0.0 to 1.0
    rationale: str

@dataclass
class CompareSummary:
    """Complete compare summary schema."""
    query: str
    stance_a: str
    stance_b: str
    evidence: List[EvidenceItem]
    decision: Decision
    created_at: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = asdict(self)
        
        # Convert datetime objects to ISO strings
        if result.get('created_at'):
            result['created_at'] = result['created_at'].isoformat()
        
        # Convert evidence timestamps
        for item in result.get('evidence', []):
            if item.get('timestamp'):
                item['timestamp'] = item['timestamp'].isoformat()
        
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CompareSummary':
        """Create from dictionary with proper type conversion."""
        # Convert timestamps back to datetime objects
        if data.get('created_at'):
            data['created_at'] = datetime.fromisoformat(data['created_at'])
        
        # Convert evidence items
        evidence_data = data.get('evidence', [])
        evidence_items = []
        for item_data in evidence_data:
            if item_data.get('timestamp'):
                item_data['timestamp'] = datetime.fromisoformat(item_data['timestamp'])
            evidence_items.append(EvidenceItem(**item_data))
        
        data['evidence'] = evidence_items
        
        # Convert decision
        if 'decision' in data:
            data['decision'] = Decision(**data['decision'])
        
        return cls(**data)

def normalize_evidence(
    evidence_items: List[Dict[str, Any]], 
    max_items: int = MAX_EVIDENCE_ITEMS,
    max_external_text: int = MAX_EXTERNAL_TEXT_LENGTH,
    max_internal_text: int = MAX_INTERNAL_TEXT_LENGTH
) -> List[EvidenceItem]:
    """
    Normalize and standardize evidence items.
    
    Args:
        evidence_items: Raw evidence items from various sources
        max_items: Maximum number of evidence items to keep
        max_external_text: Maximum length for external text snippets
        max_internal_text: Maximum length for internal text snippets
        
    Returns:
        List of normalized EvidenceItem objects, ordered by score then recency
    """
    normalized_items = []
    
    for item_data in evidence_items:
        # Extract basic fields
        item_id = item_data.get('id', '')
        snippet = item_data.get('snippet', '')
        source = item_data.get('source', '')
        score = float(item_data.get('score', 0.0))
        
        # Determine if external
        url = item_data.get('url', '')
        is_external = _is_external_source(url, source)
        
        # Normalize snippet text
        normalized_snippet = _normalize_snippet_text(
            snippet, 
            is_external, 
            max_external_text, 
            max_internal_text
        )
        
        # Parse timestamp
        timestamp = _parse_timestamp(item_data.get('timestamp'))
        
        # Create normalized item
        normalized_item = EvidenceItem(
            id=item_id,
            snippet=normalized_snippet,
            source=source,
            score=score,
            is_external=is_external,
            url=url if url else None,
            timestamp=timestamp,
            metadata=item_data.get('metadata')
        )
        
        normalized_items.append(normalized_item)
    
    # Sort by score (descending) then by recency (descending)
    # Items without timestamps are treated as oldest (use a very old date)
    def sort_key(item):
        score = -item.score  # Negative for descending order
        if item.timestamp:
            # Use negative timestamp for descending order (newest first)
            timestamp = -item.timestamp.timestamp()
        else:
            # Use a very old timestamp for items without timestamps
            timestamp = -datetime(1900, 1, 1).timestamp()
        return (score, timestamp)
    
    normalized_items.sort(key=sort_key)
    
    # Limit to max_items
    return normalized_items[:max_items]

def _is_external_source(url: str, source: str) -> bool:
    """Determine if a source is external based on URL or source name."""
    if not url and not source:
        return False
    
    # Check URL patterns
    if url:
        try:
            parsed = urlparse(url)
            if parsed.netloc:
                # External if it has a domain
                return True
        except Exception:
            pass
    
    # Check source patterns
    if source:
        external_indicators = [
            'http://', 'https://', 'www.', '.com', '.org', '.edu', '.gov',
            'arxiv', 'pubmed', 'nature', 'science', 'ieee', 'acm'
        ]
        source_lower = source.lower()
        if any(indicator in source_lower for indicator in external_indicators):
            return True
    
    return False

def _normalize_snippet_text(
    snippet: str, 
    is_external: bool, 
    max_external_text: int, 
    max_internal_text: int
) -> str:
    """Normalize snippet text with appropriate truncation and hashing."""
    if not snippet:
        return ""
    
    max_length = max_external_text if is_external else max_internal_text
    
    if len(snippet) <= max_length:
        return snippet
    
    # Truncate and add hash
    truncated = snippet[:max_length]
    hash_suffix = _generate_text_hash(snippet)
    
    return f"{truncated}... [hash:{hash_suffix}]"

def _generate_text_hash(text: str) -> str:
    """Generate a short hash for text content."""
    return hashlib.md5(text.encode('utf-8')).hexdigest()[:HASH_LENGTH]

def _parse_timestamp(timestamp: Union[str, datetime, None]) -> Optional[datetime]:
    """Parse timestamp from various formats."""
    if timestamp is None:
        return None
    
    if isinstance(timestamp, datetime):
        return timestamp
    
    if isinstance(timestamp, str):
        try:
            # Try ISO format first
            return datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        except ValueError:
            try:
                # Try common formats
                for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d', '%d/%m/%Y']:
                    try:
                        return datetime.strptime(timestamp, fmt)
                    except ValueError:
                        continue
            except Exception:
                pass
    
    return None

def create_compare_summary(
    query: str,
    stance_a: str,
    stance_b: str,
    evidence_items: List[Dict[str, Any]],
    decision_verdict: str,
    decision_confidence: float,
    decision_rationale: str,
    max_evidence_items: int = MAX_EVIDENCE_ITEMS
) -> CompareSummary:
    """
    Create a normalized compare summary from raw data.
    
    Args:
        query: The query being compared
        stance_a: First stance to compare
        stance_b: Second stance to compare
        evidence_items: Raw evidence items
        decision_verdict: Decision verdict
        decision_confidence: Decision confidence (0.0 to 1.0)
        decision_rationale: Decision rationale
        max_evidence_items: Maximum evidence items to include
        
    Returns:
        Normalized CompareSummary object
    """
    # Normalize evidence
    normalized_evidence = normalize_evidence(
        evidence_items, 
        max_items=max_evidence_items
    )
    
    # Create decision
    decision = Decision(
        verdict=decision_verdict,
        confidence=max(0.0, min(1.0, decision_confidence)),  # Clamp to [0, 1]
        rationale=decision_rationale
    )
    
    # Create summary
    summary = CompareSummary(
        query=query,
        stance_a=stance_a,
        stance_b=stance_b,
        evidence=normalized_evidence,
        decision=decision,
        created_at=datetime.now(),
        metadata={}
    )
    
    return summary

def validate_compare_summary(summary: CompareSummary) -> List[str]:
    """
    Validate a compare summary and return any issues found.
    
    Args:
        summary: CompareSummary to validate
        
    Returns:
        List of validation error messages
    """
    errors = []
    
    # Validate required fields
    if not summary.query.strip():
        errors.append("Query cannot be empty")
    
    if not summary.stance_a.strip():
        errors.append("Stance A cannot be empty")
    
    if not summary.stance_b.strip():
        errors.append("Stance B cannot be empty")
    
    # Validate evidence
    if not summary.evidence:
        errors.append("Evidence list cannot be empty")
    else:
        for i, item in enumerate(summary.evidence):
            if not item.id.strip():
                errors.append(f"Evidence item {i} missing ID")
            
            if not item.snippet.strip():
                errors.append(f"Evidence item {i} missing snippet")
            
            if not item.source.strip():
                errors.append(f"Evidence item {i} missing source")
            
            if not (0.0 <= item.score <= 1.0):
                errors.append(f"Evidence item {i} score must be between 0.0 and 1.0")
    
    # Validate decision
    if not summary.decision.verdict.strip():
        errors.append("Decision verdict cannot be empty")
    
    valid_verdicts = ["stance_a", "stance_b", "inconclusive", "insufficient_evidence"]
    if summary.decision.verdict not in valid_verdicts:
        errors.append(f"Decision verdict must be one of: {valid_verdicts}")
    
    if not (0.0 <= summary.decision.confidence <= 1.0):
        errors.append("Decision confidence must be between 0.0 and 1.0")
    
    if not summary.decision.rationale.strip():
        errors.append("Decision rationale cannot be empty")
    
    return errors

def get_summary_stats(summary: CompareSummary) -> Dict[str, Any]:
    """
    Get statistics about a compare summary.
    
    Args:
        summary: CompareSummary to analyze
        
    Returns:
        Dictionary with summary statistics
    """
    evidence = summary.evidence
    
    # Count by type
    internal_count = sum(1 for item in evidence if not item.is_external)
    external_count = sum(1 for item in evidence if item.is_external)
    
    # Score statistics
    scores = [item.score for item in evidence]
    avg_score = sum(scores) / len(scores) if scores else 0.0
    max_score = max(scores) if scores else 0.0
    min_score = min(scores) if scores else 0.0
    
    # Text length statistics
    snippet_lengths = [len(item.snippet) for item in evidence]
    avg_snippet_length = sum(snippet_lengths) / len(snippet_lengths) if snippet_lengths else 0
    
    # Truncation statistics
    truncated_count = sum(1 for item in evidence if '... [hash:' in item.snippet)
    
    return {
        "total_evidence_items": len(evidence),
        "internal_items": internal_count,
        "external_items": external_count,
        "truncated_items": truncated_count,
        "score_stats": {
            "average": round(avg_score, 3),
            "maximum": round(max_score, 3),
            "minimum": round(min_score, 3)
        },
        "text_stats": {
            "average_snippet_length": round(avg_snippet_length, 1),
            "total_text_length": sum(snippet_lengths)
        },
        "decision": {
            "verdict": summary.decision.verdict,
            "confidence": summary.decision.confidence,
            "rationale_length": len(summary.decision.rationale)
        }
    }

def export_summary_json(summary: CompareSummary, pretty: bool = True) -> str:
    """
    Export compare summary as JSON string.
    
    Args:
        summary: CompareSummary to export
        pretty: Whether to format JSON with indentation
        
    Returns:
        JSON string representation
    """
    data = summary.to_dict()
    
    if pretty:
        return json.dumps(data, indent=2, ensure_ascii=False)
    else:
        return json.dumps(data, ensure_ascii=False)

def import_summary_json(json_str: str) -> CompareSummary:
    """
    Import compare summary from JSON string.
    
    Args:
        json_str: JSON string to parse
        
    Returns:
        CompareSummary object
    """
    data = json.loads(json_str)
    return CompareSummary.from_dict(data)