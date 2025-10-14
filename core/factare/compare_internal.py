# core/factare/compare_internal.py — Internal-only comparator using retrieval candidates

import re
import hashlib
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Tuple, Set
from datetime import datetime

from core.factare.summary import CompareSummary, EvidenceItem, Decision, create_compare_summary

@dataclass
class RetrievalCandidate:
    """Individual retrieval candidate from search results."""
    id: str
    content: str
    source: str
    score: float
    metadata: Optional[Dict[str, Any]] = None
    url: Optional[str] = None
    timestamp: Optional[datetime] = None

@dataclass
class ContradictionPair:
    """Pair of contradictory claims."""
    claim_a: str
    claim_b: str
    evidence_a: str
    evidence_b: str
    confidence: float
    contradiction_type: str  # "temporal", "causal", "factual", "evaluative"

@dataclass
class ComparisonResult:
    """Result of internal comparison."""
    has_binary_contrast: bool
    stance_a: Optional[str]
    stance_b: Optional[str]
    evidence_items: List[EvidenceItem]
    contradictions: List[ContradictionPair]
    decision: Decision
    metadata: Dict[str, Any]

class InternalComparator:
    """Internal-only comparator using retrieval candidates and contradiction detection."""
    
    def __init__(self):
        # Binary contrast patterns
        self.binary_patterns = [
            r'\b(should|shouldn\'t|should not)\b',
            r'\b(pros?|cons?)\b',
            r'\b(advantages?|disadvantages?)\b',
            r'\b(benefits?|drawbacks?)\b',
            r'\b(support|oppose|against)\b',
            r'\b(recommend|discourage)\b',
            r'\b(adopt|reject)\b',
            r'\b(implement|avoid)\b',
            r'\b(enable|disable)\b',
            r'\b(allow|prohibit|ban)\b'
        ]
        
        # Contradiction keywords
        self.contradiction_keywords = [
            ('supports', 'opposes', 'evaluative'),
            ('recommends', 'discourages', 'evaluative'),
            ('enables', 'prevents', 'causal'),
            ('allows', 'prohibits', 'evaluative'),
            ('increases', 'decreases', 'causal'),
            ('improves', 'worsens', 'evaluative'),
            ('effective', 'ineffective', 'evaluative'),
            ('safe', 'unsafe', 'evaluative'),
            ('beneficial', 'harmful', 'evaluative'),
            ('successful', 'unsuccessful', 'evaluative'),
            ('proven', 'disproven', 'factual'),
            ('confirmed', 'refuted', 'factual'),
            ('shows', 'contradicts', 'factual'),
            ('indicates', 'suggests otherwise', 'factual'),
            ('demonstrates', 'fails to demonstrate', 'factual'),
            ('always', 'never', 'temporal'),
            ('all', 'none', 'factual'),
            ('every', 'no', 'factual'),
            ('completely', 'partially', 'evaluative'),
            ('fully', 'incompletely', 'evaluative'),
            ('highly', 'poorly', 'evaluative'),
            ('significantly', 'minimally', 'evaluative'),
            ('strongly', 'weakly', 'evaluative'),
            ('clearly', 'unclearly', 'evaluative'),
            ('definitely', 'uncertainly', 'evaluative'),
            ('obviously', 'unobviously', 'evaluative'),
            ('certainly', 'uncertainly', 'evaluative'),
            ('undoubtedly', 'doubtfully', 'evaluative'),
            ('conclusively', 'inconclusively', 'evaluative'),
            ('decisively', 'indecisively', 'evaluative')
        ]
        
        # Entity extraction patterns
        self.entity_patterns = [
            r'\b(?:Dr\.|Prof\.|Mr\.|Ms\.|Mrs\.)\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b',  # Titles with names
            r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b',  # Proper nouns
            r'\b(?:the\s+)?[a-z]+(?:\s+[a-z]+)*\s+(?:method|approach|technique|strategy|policy|system|process|model|framework)\b',
            r'\b(?:new|novel|traditional|conventional|existing|current|proposed|alternative)\s+[a-z]+(?:\s+[a-z]+)*\b',
            r'\b[A-Z]{2,}\b',  # Acronyms
            r'\b\d+(?:\.\d+)?%?\b'  # Numbers and percentages
        ]
        
        # Predicate patterns
        self.predicate_patterns = [
            r'\b(?:is|are|was|were|will be|can be|should be|may be|might be)\s+[a-z]+(?:\s+[a-z]+)*\b',
            r'\b(?:has|have|had|will have|can have|should have|may have)\s+[a-z]+(?:\s+[a-z]+)*\b',
            r'\b(?:does|do|did|will do|can do|should do|may do)\s+[a-z]+(?:\s+[a-z]+)*\b',
            r'\b(?:causes?|leads? to|results? in|enables?|prevents?|increases?|decreases?)\s+[a-z]+(?:\s+[a-z]+)*\b',
            r'\b(?:improves?|worsens?|enhances?|reduces?|optimizes?|degrades?)\s+[a-z]+(?:\s+[a-z]+)*\b'
        ]
    
    def compare(self, query: str, retrieval_candidates: List[RetrievalCandidate]) -> ComparisonResult:
        """
        Compare retrieval candidates to build stance comparison.
        
        Args:
            query: The query being analyzed
            retrieval_candidates: List of retrieval candidates
            
        Returns:
            ComparisonResult with stance analysis and contradictions
        """
        # Check if query suggests binary contrast
        has_binary_contrast = self._detect_binary_contrast(query)
        
        if not has_binary_contrast:
            return self._create_neutral_summary(query, retrieval_candidates)
        
        # Extract entities and predicates from query
        query_entities = self._extract_entities(query)
        query_predicates = self._extract_predicates(query)
        
        # Build stances from retrieval candidates
        stance_a, stance_b = self._build_stances(query, retrieval_candidates, query_entities, query_predicates)
        
        # Detect contradictions
        contradictions = self._detect_contradictions(retrieval_candidates)
        
        # Create evidence items
        evidence_items = self._create_evidence_items(retrieval_candidates)
        
        # Create decision
        decision = self._create_decision(query, stance_a, stance_b, contradictions, evidence_items)
        
        # Create metadata
        metadata = {
            'query_entities': query_entities,
            'query_predicates': query_predicates,
            'binary_contrast_detected': has_binary_contrast,
            'contradiction_count': len(contradictions),
            'evidence_count': len(evidence_items),
            'processing_timestamp': datetime.now().isoformat()
        }
        
        return ComparisonResult(
            has_binary_contrast=has_binary_contrast,
            stance_a=stance_a,
            stance_b=stance_b,
            evidence_items=evidence_items,
            contradictions=contradictions,
            decision=decision,
            metadata=metadata
        )
    
    def _detect_binary_contrast(self, query: str) -> bool:
        """Detect if query suggests binary contrast."""
        query_lower = query.lower()
        
        # Check for binary contrast patterns
        for pattern in self.binary_patterns:
            if re.search(pattern, query_lower):
                return True
        
        # Check for question words that suggest comparison
        comparison_question_words = [
            'should', 'would', 'could', 'might', 'may',
            'pros and cons', 'advantages and disadvantages',
            'benefits and drawbacks', 'support or oppose',
            'recommend or discourage', 'adopt or reject'
        ]
        
        for word in comparison_question_words:
            if word in query_lower:
                return True
        
        return False
    
    def _extract_entities(self, text: str) -> List[str]:
        """Extract entities from text."""
        entities = set()
        
        for pattern in self.entity_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    match = ' '.join(match)
                entities.add(match.strip())
        
        return list(entities)
    
    def _extract_predicates(self, text: str) -> List[str]:
        """Extract predicates from text."""
        predicates = set()
        
        for pattern in self.predicate_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    match = ' '.join(match)
                predicates.add(match.strip())
        
        return list(predicates)
    
    def _build_stances(self, query: str, candidates: List[RetrievalCandidate], 
                      entities: List[str], predicates: List[str]) -> Tuple[Optional[str], Optional[str]]:
        """Build stance_a and stance_b from retrieval candidates."""
        if not candidates:
            return None, None
        
        # Group candidates by sentiment/position
        positive_candidates = []
        negative_candidates = []
        neutral_candidates = []
        
        for candidate in candidates:
            sentiment = self._classify_sentiment(candidate.content)
            if sentiment > 0.1:
                positive_candidates.append(candidate)
            elif sentiment < -0.1:
                negative_candidates.append(candidate)
            else:
                neutral_candidates.append(candidate)
        
        # Build stances from top candidates
        stance_a = self._build_stance_from_candidates(query, positive_candidates, entities, predicates, "positive")
        stance_b = self._build_stance_from_candidates(query, negative_candidates, entities, predicates, "negative")
        
        # If we don't have clear positive/negative split, try other heuristics
        if not stance_a or not stance_b:
            stance_a, stance_b = self._build_stances_alternative(query, candidates, entities, predicates)
        
        return stance_a, stance_b
    
    def _classify_sentiment(self, text: str) -> float:
        """Simple sentiment classification based on keywords."""
        positive_words = [
            'beneficial', 'effective', 'successful', 'improves', 'enhances',
            'supports', 'recommends', 'enables', 'allows', 'increases',
            'safe', 'reliable', 'proven', 'confirmed', 'demonstrates',
            'advantages', 'benefits', 'pros', 'positive', 'good', 'great'
        ]
        
        negative_words = [
            'harmful', 'ineffective', 'unsuccessful', 'worsens', 'degrades',
            'opposes', 'discourages', 'prevents', 'prohibits', 'decreases',
            'unsafe', 'unreliable', 'disproven', 'refuted', 'contradicts',
            'disadvantages', 'drawbacks', 'cons', 'negative', 'bad', 'poor'
        ]
        
        text_lower = text.lower()
        
        positive_count = sum(1 for word in positive_words if word in text_lower)
        negative_count = sum(1 for word in negative_words if word in text_lower)
        
        total_words = len(text.split())
        if total_words == 0:
            return 0.0
        
        return (positive_count - negative_count) / total_words
    
    def _build_stance_from_candidates(self, query: str, candidates: List[RetrievalCandidate], 
                                    entities: List[str], predicates: List[str], position: str) -> Optional[str]:
        """Build a stance from candidates of a specific position."""
        if not candidates:
            return None
        
        # Sort by score and take top candidates
        sorted_candidates = sorted(candidates, key=lambda x: x.score, reverse=True)
        top_candidates = sorted_candidates[:3]
        
        # Extract key phrases from top candidates
        key_phrases = []
        for candidate in top_candidates:
            phrases = self._extract_key_phrases(candidate.content, entities, predicates)
            key_phrases.extend(phrases)
        
        if not key_phrases:
            return None
        
        # Build stance from key phrases
        stance = self._construct_stance(query, key_phrases, position)
        return stance
    
    def _extract_key_phrases(self, text: str, entities: List[str], predicates: List[str]) -> List[str]:
        """Extract key phrases from text."""
        phrases = []
        
        # Look for sentences containing entities or predicates
        sentences = re.split(r'[.!?]+', text)
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            
            # Check if sentence contains relevant entities or predicates
            sentence_lower = sentence.lower()
            has_entity = any(entity.lower() in sentence_lower for entity in entities)
            has_predicate = any(predicate.lower() in sentence_lower for predicate in predicates)
            
            if has_entity or has_predicate:
                # Clean up the sentence
                sentence = re.sub(r'\s+', ' ', sentence).strip()
                if len(sentence) > 20:  # Only include substantial sentences
                    phrases.append(sentence)
        
        return phrases[:5]  # Limit to top 5 phrases
    
    def _construct_stance(self, query: str, key_phrases: List[str], position: str) -> str:
        """Construct a stance from key phrases."""
        if not key_phrases:
            return f"Based on available evidence, the {position} position cannot be clearly established."
        
        # Take the most relevant phrases
        relevant_phrases = key_phrases[:3]
        
        if position == "positive":
            stance = f"Evidence supports the positive position: {' '.join(relevant_phrases[:2])}"
        else:
            stance = f"Evidence supports the negative position: {' '.join(relevant_phrases[:2])}"
        
        # Truncate if too long
        if len(stance) > 200:
            stance = stance[:197] + "..."
        
        return stance
    
    def _build_stances_alternative(self, query: str, candidates: List[RetrievalCandidate], 
                                 entities: List[str], predicates: List[str]) -> Tuple[Optional[str], Optional[str]]:
        """Alternative method to build stances when positive/negative split fails."""
        if not candidates:
            return None, None
        
        # Sort by score and split in half
        sorted_candidates = sorted(candidates, key=lambda x: x.score, reverse=True)
        mid_point = len(sorted_candidates) // 2
        
        stance_a_candidates = sorted_candidates[:mid_point]
        stance_b_candidates = sorted_candidates[mid_point:]
        
        stance_a = self._build_stance_from_candidates(query, stance_a_candidates, entities, predicates, "first")
        stance_b = self._build_stance_from_candidates(query, stance_b_candidates, entities, predicates, "second")
        
        return stance_a, stance_b
    
    def _detect_contradictions(self, candidates: List[RetrievalCandidate]) -> List[ContradictionPair]:
        """Detect contradictions between candidates."""
        contradictions = []
        
        # Compare all pairs of candidates
        for i in range(len(candidates)):
            for j in range(i + 1, len(candidates)):
                candidate_a = candidates[i]
                candidate_b = candidates[j]
                
                contradiction = self._find_contradiction(candidate_a, candidate_b)
                if contradiction:
                    contradictions.append(contradiction)
        
        return contradictions
    
    def _find_contradiction(self, candidate_a: RetrievalCandidate, candidate_b: RetrievalCandidate) -> Optional[ContradictionPair]:
        """Find contradiction between two candidates."""
        content_a = candidate_a.content.lower()
        content_b = candidate_b.content.lower()
        
        # Check for contradiction keywords
        for pos_word, neg_word, contradiction_type in self.contradiction_keywords:
            if pos_word in content_a and neg_word in content_b:
                return ContradictionPair(
                    claim_a=self._extract_claim(content_a, pos_word),
                    claim_b=self._extract_claim(content_b, neg_word),
                    evidence_a=candidate_a.content[:200] + "..." if len(candidate_a.content) > 200 else candidate_a.content,
                    evidence_b=candidate_b.content[:200] + "..." if len(candidate_b.content) > 200 else candidate_b.content,
                    confidence=0.8,  # High confidence for keyword-based detection
                    contradiction_type=contradiction_type
                )
            elif pos_word in content_b and neg_word in content_a:
                return ContradictionPair(
                    claim_a=self._extract_claim(content_b, pos_word),
                    claim_b=self._extract_claim(content_a, neg_word),
                    evidence_a=candidate_b.content[:200] + "..." if len(candidate_b.content) > 200 else candidate_b.content,
                    evidence_b=candidate_a.content[:200] + "..." if len(candidate_a.content) > 200 else candidate_a.content,
                    confidence=0.8,
                    contradiction_type=contradiction_type
                )
        
        # Check for sentiment-based contradictions
        sentiment_a = self._classify_sentiment(candidate_a.content)
        sentiment_b = self._classify_sentiment(candidate_b.content)
        
        # If sentiments are strongly opposed, consider it a contradiction
        if (sentiment_a > 0.2 and sentiment_b < -0.2) or (sentiment_a < -0.2 and sentiment_b > 0.2):
            return ContradictionPair(
                claim_a=self._extract_claim(content_a, "positive" if sentiment_a > 0 else "negative"),
                claim_b=self._extract_claim(content_b, "positive" if sentiment_b > 0 else "negative"),
                evidence_a=candidate_a.content[:200] + "..." if len(candidate_a.content) > 200 else candidate_a.content,
                evidence_b=candidate_b.content[:200] + "..." if len(candidate_b.content) > 200 else candidate_b.content,
                confidence=0.6,  # Medium confidence for sentiment-based detection
                contradiction_type="evaluative"
            )
        
        return None
    
    def _extract_claim(self, content: str, keyword: str) -> str:
        """Extract a claim containing the keyword."""
        sentences = re.split(r'[.!?]+', content)
        
        for sentence in sentences:
            if keyword in sentence.lower():
                sentence = sentence.strip()
                if len(sentence) > 10:  # Only include substantial sentences
                    return sentence
        
        return content[:100] + "..." if len(content) > 100 else content
    
    def _create_evidence_items(self, candidates: List[RetrievalCandidate]) -> List[EvidenceItem]:
        """Create evidence items from retrieval candidates."""
        evidence_items = []
        
        for candidate in candidates:
            # Determine if external based on URL or source
            is_external = bool(candidate.url) or self._is_external_source(candidate.source)
            
            # Truncate content if too long
            snippet = candidate.content
            max_length = 500 if is_external else 1000
            if len(snippet) > max_length:
                snippet = snippet[:max_length] + "..."
            
            evidence_item = EvidenceItem(
                id=candidate.id,
                snippet=snippet,
                source=candidate.source,
                score=candidate.score,
                is_external=is_external,
                url=candidate.url,
                timestamp=candidate.timestamp,
                metadata=candidate.metadata
            )
            
            evidence_items.append(evidence_item)
        
        return evidence_items
    
    def _is_external_source(self, source: str) -> bool:
        """Determine if source is external."""
        external_indicators = [
            'http://', 'https://', 'www.', '.com', '.org', '.edu', '.gov',
            'arxiv', 'pubmed', 'nature', 'science', 'ieee', 'acm'
        ]
        
        source_lower = source.lower()
        return any(indicator in source_lower for indicator in external_indicators)
    
    def _create_decision(self, query: str, stance_a: Optional[str], stance_b: Optional[str], 
                        contradictions: List[ContradictionPair], evidence_items: List[EvidenceItem]) -> Decision:
        """Create decision based on analysis."""
        if not stance_a or not stance_b:
            return Decision(
                verdict="insufficient_evidence",
                confidence=0.3,
                rationale="Insufficient evidence to establish clear opposing stances."
            )
        
        if contradictions:
            return Decision(
                verdict="inconclusive",
                confidence=0.6,
                rationale=f"Evidence contains {len(contradictions)} contradictions, making a clear decision difficult."
            )
        
        # Simple heuristic: choose stance with higher average evidence score
        if evidence_items:
            avg_score = sum(item.score for item in evidence_items) / len(evidence_items)
            if avg_score > 0.7:
                return Decision(
                    verdict="stance_a",
                    confidence=0.8,
                    rationale="Evidence strongly supports the first stance."
                )
            elif avg_score < 0.3:
                return Decision(
                    verdict="stance_b",
                    confidence=0.8,
                    rationale="Evidence strongly supports the second stance."
                )
        
        return Decision(
            verdict="inconclusive",
            confidence=0.5,
            rationale="Evidence is mixed and does not clearly favor either stance."
        )
    
    def _create_neutral_summary(self, query: str, candidates: List[RetrievalCandidate]) -> ComparisonResult:
        """Create neutral summary when no binary contrast is detected."""
        evidence_items = self._create_evidence_items(candidates)
        contradictions = self._detect_contradictions(candidates)
        
        decision = Decision(
            verdict="insufficient_evidence",
            confidence=0.2,
            rationale="Query does not suggest a binary contrast that can be compared."
        )
        
        metadata = {
            'query_entities': self._extract_entities(query),
            'query_predicates': self._extract_predicates(query),
            'binary_contrast_detected': False,
            'contradiction_count': len(contradictions),
            'evidence_count': len(evidence_items),
            'processing_timestamp': datetime.now().isoformat()
        }
        
        return ComparisonResult(
            has_binary_contrast=False,
            stance_a=None,
            stance_b=None,
            evidence_items=evidence_items,
            contradictions=contradictions,
            decision=decision,
            metadata=metadata
        )
    
    def create_compare_summary(self, query: str, retrieval_candidates: List[RetrievalCandidate]) -> CompareSummary:
        """
        Create a CompareSummary from query and retrieval candidates.
        
        Args:
            query: The query being analyzed
            retrieval_candidates: List of retrieval candidates
            
        Returns:
            CompareSummary object
        """
        result = self.compare(query, retrieval_candidates)
        
        # Convert evidence items to the format expected by create_compare_summary
        evidence_items_data = []
        for item in result.evidence_items:
            evidence_items_data.append({
                'id': item.id,
                'snippet': item.snippet,
                'source': item.source,
                'score': item.score,
                'url': item.url,
                'timestamp': item.timestamp.isoformat() if item.timestamp else None,
                'metadata': item.metadata
            })
        
        if not result.has_binary_contrast:
            # Create a neutral summary
            return create_compare_summary(
                query=query,
                stance_a="No clear stance A identified",
                stance_b="No clear stance B identified",
                evidence_items=evidence_items_data,
                decision_verdict=result.decision.verdict,
                decision_confidence=result.decision.confidence,
                decision_rationale=result.decision.rationale
            )
        
        return create_compare_summary(
            query=query,
            stance_a=result.stance_a or "Stance A not identified",
            stance_b=result.stance_b or "Stance B not identified",
            evidence_items=evidence_items_data,
            decision_verdict=result.decision.verdict,
            decision_confidence=result.decision.confidence,
            decision_rationale=result.decision.rationale
        )

def create_retrieval_candidates_from_dicts(candidates_data: List[Dict[str, Any]]) -> List[RetrievalCandidate]:
    """Create RetrievalCandidate objects from dictionary data."""
    candidates = []
    
    for data in candidates_data:
        candidate = RetrievalCandidate(
            id=data.get('id', ''),
            content=data.get('content', ''),
            source=data.get('source', ''),
            score=float(data.get('score', 0.0)),
            metadata=data.get('metadata'),
            url=data.get('url'),
            timestamp=datetime.fromisoformat(data['timestamp']) if data.get('timestamp') else None
        )
        candidates.append(candidate)
    
    return candidates