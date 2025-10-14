# core/packing.py — contradiction detection and packing

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set, Tuple
from dataclasses import dataclass
from collections import defaultdict

from feature_flags import get_feature_flag

@dataclass
class Contradiction:
    """Represents a detected contradiction between claims."""
    subject: str  # The entity or subject being discussed
    claim_a: str  # First conflicting claim
    claim_b: str  # Second conflicting claim
    evidence_ids: List[str]  # Memory IDs that support each claim
    contradiction_type: str  # Type of contradiction detected
    confidence: float  # Confidence score [0,1]

@dataclass
class PackingResult:
    """Result of packing with contradiction detection."""
    context: List[Dict[str, Any]]
    ranked_ids: List[str]
    contradictions: List[Contradiction]
    contradiction_score: float  # Overall contradiction score [0,1]
    metadata: Dict[str, Any]

class ContradictionDetector:
    """Detects contradictions among top candidates."""
    
    def __init__(self):
        self.opposing_predicates = {
            # Direct opposites
            "supports": "contradicts",
            "contradicts": "supports",
            "affirms": "denies",
            "denies": "affirms",
            "confirms": "refutes",
            "refutes": "confirms",
            "proves": "disproves",
            "disproves": "proves",
            "validates": "invalidates",
            "invalidates": "validates",
            
            # Semantic opposites
            "increases": "decreases",
            "decreases": "increases",
            "improves": "worsens",
            "worsens": "improves",
            "enhances": "diminishes",
            "diminishes": "enhances",
            "strengthens": "weakens",
            "weakens": "strengthens",
            
            # Temporal opposites
            "begins": "ends",
            "ends": "begins",
            "starts": "stops",
            "stops": "starts",
            "continues": "discontinues",
            "discontinues": "continues",
        }
    
    def detect_contradictions(self, 
                            candidates: List[Dict[str, Any]], 
                            top_m: int = 10) -> List[Contradiction]:
        """
        Detect contradictions among top M candidates.
        
        Args:
            candidates: List of candidate records with metadata
            top_m: Number of top candidates to analyze
            
        Returns:
            List of detected contradictions
        """
        if not get_feature_flag("retrieval.contradictions_pack", default=False):
            return []
        
        # Take top M candidates
        top_candidates = candidates[:top_m]
        if len(top_candidates) < 2:
            return []
        
        contradictions = []
        
        # Detect entity-based contradictions
        entity_contradictions = self._detect_entity_contradictions(top_candidates)
        contradictions.extend(entity_contradictions)
        
        # Detect memory-based contradictions
        memory_contradictions = self._detect_memory_contradictions(top_candidates)
        contradictions.extend(memory_contradictions)
        
        # Detect semantic contradictions
        semantic_contradictions = self._detect_semantic_contradictions(top_candidates)
        contradictions.extend(semantic_contradictions)
        
        return contradictions
    
    def _detect_entity_contradictions(self, candidates: List[Dict[str, Any]]) -> List[Contradiction]:
        """Detect contradictions based on same subject entity + opposing predicates."""
        contradictions = []
        
        # Group candidates by subject entities
        entity_groups = defaultdict(list)
        for candidate in candidates:
            metadata = candidate.get("metadata", {})
            entity_id = metadata.get("entity_id")
            entity_name = metadata.get("entity_name")
            
            if entity_id and entity_name:
                entity_groups[entity_id].append({
                    "candidate": candidate,
                    "entity_name": entity_name,
                    "relations": metadata.get("relations", []),
                    "text": candidate.get("text", ""),
                    "id": candidate.get("id")
                })
        
        # Check for opposing predicates within each entity group
        for entity_id, entity_candidates in entity_groups.items():
            if len(entity_candidates) < 2:
                continue
            
            entity_name = entity_candidates[0]["entity_name"]
            
            # Extract predicates from relations and text
            predicates = self._extract_predicates(entity_candidates)
            
            # Find opposing predicate pairs
            for i, pred_a in enumerate(predicates):
                for j, pred_b in enumerate(predicates[i+1:], i+1):
                    if self._are_opposing_predicates(pred_a["predicate"], pred_b["predicate"]):
                        contradiction = Contradiction(
                            subject=entity_name,
                            claim_a=pred_a["claim"],
                            claim_b=pred_b["claim"],
                            evidence_ids=[pred_a["memory_id"], pred_b["memory_id"]],
                            contradiction_type="entity_predicate",
                            confidence=self._calculate_contradiction_confidence(pred_a, pred_b)
                        )
                        contradictions.append(contradiction)
        
        return contradictions
    
    def _detect_memory_contradictions(self, candidates: List[Dict[str, Any]]) -> List[Contradiction]:
        """Detect contradictions based on memories.contradictions cross-references."""
        contradictions = []
        
        # Collect all contradiction references
        contradiction_refs = defaultdict(list)
        
        for candidate in candidates:
            metadata = candidate.get("metadata", {})
            contradictions_list = metadata.get("contradictions", [])
            memory_id = candidate.get("id")
            
            for contradiction_ref in contradictions_list:
                if isinstance(contradiction_ref, dict):
                    ref_id = contradiction_ref.get("id")
                    ref_type = contradiction_ref.get("type", "unknown")
                else:
                    ref_id = str(contradiction_ref)
                    ref_type = "unknown"
                
                if ref_id:
                    contradiction_refs[ref_id].append({
                        "memory_id": memory_id,
                        "text": candidate.get("text", ""),
                        "title": candidate.get("title", ""),
                        "type": ref_type
                    })
        
        # Find contradictions where multiple memories reference the same contradiction
        for ref_id, memories in contradiction_refs.items():
            if len(memories) >= 2:
                # Group memories by type to find opposing claims
                type_groups = defaultdict(list)
                for memory in memories:
                    type_groups[memory["type"]].append(memory)
                
                # Look for opposing types
                for type_a, memories_a in type_groups.items():
                    for type_b, memories_b in type_groups.items():
                        if type_a != type_b and self._are_opposing_types(type_a, type_b):
                            for mem_a in memories_a:
                                for mem_b in memories_b:
                                    contradiction = Contradiction(
                                        subject=f"Contradiction {ref_id}",
                                        claim_a=mem_a["text"][:200],
                                        claim_b=mem_b["text"][:200],
                                        evidence_ids=[mem_a["memory_id"], mem_b["memory_id"]],
                                        contradiction_type="memory_cross_reference",
                                        confidence=0.8  # High confidence for explicit contradictions
                                    )
                                    contradictions.append(contradiction)
        
        return contradictions
    
    def _detect_semantic_contradictions(self, candidates: List[Dict[str, Any]]) -> List[Contradiction]:
        """Detect contradictions based on semantic analysis of text content."""
        contradictions = []
        
        # Simple keyword-based contradiction detection
        contradiction_keywords = {
            "positive": ["good", "beneficial", "effective", "successful", "improves", "increases", "supports"],
            "negative": ["bad", "harmful", "ineffective", "failed", "worsens", "decreases", "contradicts"],
            "certainty": ["definitely", "certainly", "proven", "established", "confirmed"],
            "uncertainty": ["maybe", "possibly", "unclear", "uncertain", "disputed", "controversial"]
        }
        
        # Group candidates by potential subject (extract from text)
        subject_groups = defaultdict(list)
        
        for candidate in candidates:
            text = candidate.get("text", "").lower()
            title = candidate.get("title", "").lower()
            
            # Extract potential subjects (simple heuristic)
            subjects = self._extract_subjects_from_text(text + " " + title)
            
            for subject in subjects:
                subject_groups[subject].append({
                    "candidate": candidate,
                    "text": text,
                    "title": title,
                    "id": candidate.get("id")
                })
        
        # Check for semantic contradictions within each subject group
        for subject, subject_candidates in subject_groups.items():
            if len(subject_candidates) < 2:
                continue
            
            # Analyze sentiment and certainty
            positive_claims = []
            negative_claims = []
            certain_claims = []
            uncertain_claims = []
            
            for candidate in subject_candidates:
                text = candidate["text"]
                title = candidate["title"]
                
                # Check for positive/negative sentiment
                if any(word in text for word in contradiction_keywords["positive"]):
                    positive_claims.append(candidate)
                if any(word in text for word in contradiction_keywords["negative"]):
                    negative_claims.append(candidate)
                
                # Check for certainty/uncertainty
                if any(word in text for word in contradiction_keywords["certainty"]):
                    certain_claims.append(candidate)
                if any(word in text for word in contradiction_keywords["uncertainty"]):
                    uncertain_claims.append(candidate)
            
            # Create contradictions for opposing sentiments
            for pos_claim in positive_claims:
                for neg_claim in negative_claims:
                    if pos_claim["id"] != neg_claim["id"]:
                        contradiction = Contradiction(
                            subject=subject,
                            claim_a=pos_claim["text"][:200],
                            claim_b=neg_claim["text"][:200],
                            evidence_ids=[pos_claim["id"], neg_claim["id"]],
                            contradiction_type="semantic_sentiment",
                            confidence=0.6  # Medium confidence for semantic analysis
                        )
                        contradictions.append(contradiction)
            
            # Create contradictions for certainty vs uncertainty
            for cert_claim in certain_claims:
                for uncert_claim in uncertain_claims:
                    if cert_claim["id"] != uncert_claim["id"]:
                        contradiction = Contradiction(
                            subject=subject,
                            claim_a=cert_claim["text"][:200],
                            claim_b=uncert_claim["text"][:200],
                            evidence_ids=[cert_claim["id"], uncert_claim["id"]],
                            contradiction_type="semantic_certainty",
                            confidence=0.5  # Lower confidence for certainty analysis
                        )
                        contradictions.append(contradiction)
        
        return contradictions
    
    def _extract_predicates(self, entity_candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract predicates from entity candidates."""
        predicates = []
        
        for candidate in entity_candidates:
            # Extract from relations
            for relation in candidate["relations"]:
                if len(relation) >= 2:
                    predicates.append({
                        "predicate": relation[0],  # rel_type
                        "claim": f"{relation[0]} {relation[1]}",  # relation + target
                        "memory_id": candidate["id"]
                    })
            
            # Extract from text using simple patterns
            text = candidate["text"]
            text_predicates = self._extract_predicates_from_text(text)
            for pred in text_predicates:
                predicates.append({
                    "predicate": pred["predicate"],
                    "claim": pred["claim"],
                    "memory_id": candidate["id"]
                })
        
        return predicates
    
    def _extract_predicates_from_text(self, text: str) -> List[Dict[str, str]]:
        """Extract predicates from text using simple patterns."""
        predicates = []
        
        # Simple pattern matching for common predicate structures
        patterns = [
            r"(\w+)\s+(?:is|are|was|were)\s+(\w+)",  # "X is Y"
            r"(\w+)\s+(?:has|have|had)\s+(\w+)",     # "X has Y"
            r"(\w+)\s+(?:supports|contradicts|affirms|denies)\s+(\w+)",  # "X supports Y"
            r"(\w+)\s+(?:increases|decreases|improves|worsens)\s+(\w+)",  # "X increases Y"
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, text.lower())
            for match in matches:
                predicate = match.group(1)
                target = match.group(2)
                predicates.append({
                    "predicate": predicate,
                    "claim": f"{predicate} {target}"
                })
        
        return predicates
    
    def _extract_subjects_from_text(self, text: str) -> List[str]:
        """Extract potential subjects from text."""
        # Simple heuristic: look for capitalized words that might be subjects
        words = text.split()
        subjects = []
        
        for i, word in enumerate(words):
            if word[0].isupper() and len(word) > 2:
                # Check if it's likely a subject (not at start of sentence)
                if i > 0 and not words[i-1].endswith('.'):
                    subjects.append(word.lower())
        
        return list(set(subjects))  # Remove duplicates
    
    def _are_opposing_predicates(self, pred_a: str, pred_b: str) -> bool:
        """Check if two predicates are opposing."""
        pred_a_lower = pred_a.lower()
        pred_b_lower = pred_b.lower()
        
        # Direct opposition check
        if pred_a_lower in self.opposing_predicates:
            return self.opposing_predicates[pred_a_lower] == pred_b_lower
        
        # Check for negation patterns
        negation_words = ["not", "no", "never", "none", "neither", "nor", "does not", "do not", "did not", "will not"]
        for neg_word in negation_words:
            if (neg_word in pred_a_lower and neg_word not in pred_b_lower) or \
               (neg_word in pred_b_lower and neg_word not in pred_a_lower):
                return True
        
        # Check for specific negation patterns - one contains negation, the other doesn't
        has_negation_a = any(neg_word in pred_a_lower for neg_word in negation_words)
        has_negation_b = any(neg_word in pred_b_lower for neg_word in negation_words)
        
        if has_negation_a != has_negation_b:
            # Check if they're talking about the same thing (simple heuristic)
            # Remove negation words and compare
            clean_a = pred_a_lower
            clean_b = pred_b_lower
            for neg_word in negation_words:
                clean_a = clean_a.replace(neg_word, "").strip()
                clean_b = clean_b.replace(neg_word, "").strip()
            
            # Clean up extra spaces
            clean_a = " ".join(clean_a.split())
            clean_b = " ".join(clean_b.split())
            
            # If they're similar after removing negation, they're opposing
            if clean_a and clean_b:
                # Check for word overlap
                words_a = set(clean_a.split())
                words_b = set(clean_b.split())
                if words_a & words_b:  # If there's any word overlap
                    return True
                
                # Check for substring overlap
                if clean_a in clean_b or clean_b in clean_a:
                    return True
                
                # Check for similar words (simple stemming)
                def stem_word(word):
                    if len(word) > 3:
                        if word.endswith('s'):
                            return word[:-1]
                        if word.endswith('ed'):
                            return word[:-2]
                        if word.endswith('ing'):
                            return word[:-3]
                    return word
                
                stemmed_a = {stem_word(word) for word in words_a}
                stemmed_b = {stem_word(word) for word in words_b}
                if stemmed_a & stemmed_b:  # If there's any stemmed word overlap
                    return True
        
        return False
    
    def _are_opposing_types(self, type_a: str, type_b: str) -> bool:
        """Check if two types are opposing."""
        opposing_types = {
            "supports": "contradicts",
            "contradicts": "supports",
            "affirms": "denies",
            "denies": "affirms",
            "positive": "negative",
            "negative": "positive",
            "pro": "con",
            "con": "pro"
        }
        
        type_a_lower = type_a.lower()
        type_b_lower = type_b.lower()
        
        return opposing_types.get(type_a_lower) == type_b_lower
    
    def _calculate_contradiction_confidence(self, pred_a: Dict[str, Any], pred_b: Dict[str, Any]) -> float:
        """Calculate confidence score for a contradiction."""
        confidence = 0.5  # Base confidence
        
        # Increase confidence for direct predicate opposition
        if self._are_opposing_predicates(pred_a["predicate"], pred_b["predicate"]):
            confidence += 0.3
        
        # Increase confidence for explicit contradiction keywords
        contradiction_words = ["contradicts", "opposes", "refutes", "denies", "disagrees"]
        for word in contradiction_words:
            if word in pred_a["claim"].lower() or word in pred_b["claim"].lower():
                confidence += 0.2
                break
        
        return min(confidence, 1.0)
    
    def calculate_contradiction_score(self, contradictions: List[Contradiction]) -> float:
        """Calculate overall contradiction score [0,1]."""
        if not contradictions:
            return 0.0
        
        # Weight by confidence and type
        type_weights = {
            "entity_predicate": 1.0,
            "memory_cross_reference": 0.9,
            "semantic_sentiment": 0.7,
            "semantic_certainty": 0.5
        }
        
        weighted_scores = []
        for contradiction in contradictions:
            weight = type_weights.get(contradiction.contradiction_type, 0.5)
            weighted_scores.append(contradiction.confidence * weight)
        
        # Return average weighted score
        return sum(weighted_scores) / len(weighted_scores) if weighted_scores else 0.0

class ContradictionPacker:
    """Packs results with contradiction detection."""
    
    def __init__(self):
        self.detector = ContradictionDetector()
    
    def pack_with_contradictions(self, 
                                context: List[Dict[str, Any]], 
                                ranked_ids: List[str],
                                top_m: int = 10) -> PackingResult:
        """
        Pack results with contradiction detection.
        
        Args:
            context: List of context items
            ranked_ids: List of ranked IDs
            top_m: Number of top candidates to analyze for contradictions
            
        Returns:
            PackingResult with contradictions included
        """
        # Detect contradictions among top candidates
        contradictions = self.detector.detect_contradictions(context, top_m)
        
        # Calculate overall contradiction score
        contradiction_score = self.detector.calculate_contradiction_score(contradictions)
        
        # Add contradiction information to context items
        enhanced_context = self._enhance_context_with_contradictions(context, contradictions)
        
        return PackingResult(
            context=enhanced_context,
            ranked_ids=ranked_ids,
            contradictions=contradictions,
            contradiction_score=contradiction_score,
            metadata={
                "contradiction_count": len(contradictions),
                "contradiction_score": contradiction_score,
                "top_m_analyzed": min(top_m, len(context))
            }
        )
    
    def _enhance_context_with_contradictions(self, 
                                           context: List[Dict[str, Any]], 
                                           contradictions: List[Contradiction]) -> List[Dict[str, Any]]:
        """Enhance context items with contradiction information."""
        enhanced_context = []
        
        # Create a mapping of memory IDs to contradictions
        memory_contradictions = defaultdict(list)
        for contradiction in contradictions:
            for evidence_id in contradiction.evidence_ids:
                memory_contradictions[evidence_id].append(contradiction)
        
        for item in context:
            enhanced_item = item.copy()
            item_id = item.get("id")
            
            # Add contradiction information if this item is involved in contradictions
            if item_id in memory_contradictions:
                enhanced_item["contradictions"] = [
                    {
                        "subject": c.subject,
                        "claim_a": c.claim_a,
                        "claim_b": c.claim_b,
                        "type": c.contradiction_type,
                        "confidence": c.confidence
                    }
                    for c in memory_contradictions[item_id]
                ]
                enhanced_item["has_contradictions"] = True
            else:
                enhanced_item["contradictions"] = []
                enhanced_item["has_contradictions"] = False
            
            enhanced_context.append(enhanced_item)
        
        return enhanced_context

# Convenience function for backward compatibility
def pack_with_contradictions(context: List[Dict[str, Any]], 
                           ranked_ids: List[str],
                           top_m: int = 10) -> PackingResult:
    """Pack results with contradiction detection."""
    packer = ContradictionPacker()
    return packer.pack_with_contradictions(context, ranked_ids, top_m)