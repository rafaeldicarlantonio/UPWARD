"""Simple contradiction detection heuristics over predicate frames."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence

from .verbs import PredicateFrame


@dataclass(frozen=True)
class Claim:
    subject: str
    predicate: str
    polarity: str
    value: Optional[float] = None
    text: str = ""
    evidence_id: Optional[str] = None


@dataclass(frozen=True)
class ContradictionCandidate:
    subject_entity_id: Optional[str]
    subject_text: str
    claim_a: str
    claim_b: str
    evidence_ids: Sequence[str]


def _hash_subject(subject_text: Optional[str], subject_entity_id: Optional[str]) -> Optional[str]:
    if subject_entity_id:
        return subject_entity_id
    if subject_text:
        return subject_text.lower()
    return None


def _normalize_text(text: str) -> str:
    return text.strip().rstrip('.')


def _claim_text(frame: PredicateFrame) -> str:
    subject = frame.subject_entity or "Unknown"
    obj = frame.object_entity or ""
    polarity_prefix = "not " if frame.polarity == "negative" else ""
    if obj:
        return _normalize_text(f"{subject} {polarity_prefix}{frame.verb_lemma} {obj}")
    return _normalize_text(f"{subject} {polarity_prefix}{frame.verb_lemma}")


def detect_contradictions(
    predicates: Sequence[PredicateFrame],
    *,
    subject_entity_id: Optional[str] = None,
    subject_text: Optional[str] = None,
    tolerance: float = 0.05,
) -> List[ContradictionCandidate]:
    subject_key = _hash_subject(subject_text, subject_entity_id)

    claims: List[Claim] = []
    for predicate in predicates:
        subject = predicate.subject_entity or subject_text or ""
        if not subject:
            continue

        claim_text = _claim_text(predicate)
        numeric_value = None
        if predicate.numeric_args:
            for values in predicate.numeric_args.values():
                if values:
                    numeric_value = values[0]
                    break

        claims.append(
            Claim(
                subject=subject,
                predicate=predicate.verb_lemma,
                polarity=predicate.polarity,
                value=numeric_value,
                text=claim_text,
            )
        )

    contradictions: List[ContradictionCandidate] = []

    for i, claim_a in enumerate(claims):
        for claim_b in claims[i + 1 :]:
            if claim_a.subject.lower() != claim_b.subject.lower():
                continue
            if claim_a.predicate != claim_b.predicate:
                continue

            if claim_a.polarity != claim_b.polarity:
                contradictions.append(
                    ContradictionCandidate(
                        subject_entity_id=subject_entity_id,
                        subject_text=claim_a.subject,
                        claim_a=claim_a.text,
                        claim_b=claim_b.text,
                        evidence_ids=[],
                    )
                )
                continue

            if claim_a.value is not None and claim_b.value is not None:
                diff = abs(claim_a.value - claim_b.value)
                base = max(abs(claim_a.value), abs(claim_b.value), tolerance)
                if diff > tolerance * base:
                    contradictions.append(
                        ContradictionCandidate(
                            subject_entity_id=subject_entity_id,
                            subject_text=claim_a.subject,
                            claim_a=claim_a.text,
                            claim_b=claim_b.text,
                            evidence_ids=[],
                        )
                    )

    return contradictions


__all__ = ["ContradictionCandidate", "detect_contradictions"]
