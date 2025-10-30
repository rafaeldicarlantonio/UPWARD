"""Concept suggestion heuristics using tokens, frames, and tf-idf signals."""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Dict, List, Optional, Sequence, Tuple, Union

from .tokenize import Token, tokenize_text, TokenizationBackend
from .frames import EventFrame


ALLOWED_NOUN_POS = {"NOUN", "PROPN"}
ALLOWED_MULTIWORD_POS = {"NOUN", "PROPN", "ADJ"}
ROLE_ORDER = ["agent", "patient", "instrument", "location", "time"]


def _normalize_name(name: str) -> str:
    return re.sub(r"\s+", " ", name.strip()).lower()


def _title_case(name: str) -> str:
    words = [w for w in re.split(r"\s+", name.strip()) if w]
    return " ".join(w.capitalize() for w in words)


def _has_alpha(value: str) -> bool:
    return any(ch.isalpha() for ch in value)


def _extract_multiword(tokens: Sequence[Token]) -> List[Tuple[str, int]]:
    phrases: List[Tuple[str, int]] = []
    current: List[Token] = []
    start_idx: Optional[int] = None

    for idx, token in enumerate(tokens):
        if token.pos in ALLOWED_MULTIWORD_POS:
            if not current:
                start_idx = idx
            current.append(token)
        else:
            if len(current) >= 2 and start_idx is not None:
                phrase = " ".join(t.lemma for t in current)
                phrases.append((phrase, start_idx))
            current = []
            start_idx = None

    if len(current) >= 2 and start_idx is not None:
        phrase = " ".join(t.lemma for t in current)
        phrases.append((phrase, start_idx))

    return phrases


def _event_frames_from_memory(memory: Dict) -> Sequence[EventFrame]:
    frames = memory.get("frames") or []
    result: List[EventFrame] = []
    for frame in frames:
        if isinstance(frame, EventFrame):
            result.append(frame)
        elif isinstance(frame, dict):
            roles = frame.get("roles", {})
            result.append(
                EventFrame(
                    frame_id=str(frame.get("frame_id", "frame")),
                    type=str(frame.get("type", "claim")),
                    roles=roles,
                    predicates=frame.get("predicates", []),
                )
            )
    return result


def _prepare_existing(existing_concepts: Sequence[Union[str, Dict[str, str]]]) -> set:
    existing: set = set()
    for item in existing_concepts:
        if isinstance(item, dict):
            name = item.get("name")
        else:
            name = str(item)
        if name:
            existing.add(_normalize_name(name))
    return existing


def suggest_concepts(
    memories: Sequence[Dict[str, Union[str, Sequence[EventFrame]]]],
    existing_concepts: Sequence[Union[str, Dict[str, str]]],
    *,
    backend: Optional[TokenizationBackend] = None,
    max_concepts: Optional[int] = None,
) -> List[Dict[str, str]]:
    existing_names = _prepare_existing(existing_concepts)
    seen_names = set(existing_names)
    suggestions: List[Dict[str, str]] = []

    token_data: List[Dict] = []
    doc_freq: Counter[str] = Counter()

    for memory in memories:
        text = str(memory.get("text", ""))
        tokens = tokenize_text(text, backend=backend)
        noun_lemmas = [token.lemma for token in tokens if token.pos in ALLOWED_NOUN_POS and token.lemma]
        noun_counts = Counter(noun_lemmas)
        for lemma in set(noun_lemmas):
            doc_freq[lemma] += 1
        multiword_phrases = _extract_multiword(tokens)
        token_data.append(
            {
                "memory": memory,
                "tokens": tokens,
                "noun_counts": noun_counts,
                "total_nouns": len(noun_lemmas),
                "multiwords": multiword_phrases,
            }
        )

    total_docs = max(len(memories), 1)

    def add_suggestion(name: str, rationale: str, memory_id: str) -> bool:
        normalized = _normalize_name(name)
        if not name or normalized in seen_names or not _has_alpha(name):
            return False
        suggestions.append(
            {
                "name": _title_case(name),
                "rationale": rationale,
                "source_memory_id": memory_id,
            }
        )
        seen_names.add(normalized)
        return bool(max_concepts and len(suggestions) >= max_concepts)

    for data in token_data:
        memory = data["memory"]
        memory_id = str(memory.get("id", ""))

        frames = _event_frames_from_memory(memory)
        for frame in frames:
            for role in ROLE_ORDER:
                value = frame.roles.get(role)
                if not value or not isinstance(value, str) or not _has_alpha(value):
                    continue
                if add_suggestion(value, f"Frame role {role} in {frame.type} frame", memory_id):
                    return suggestions

    for data in token_data:
        memory = data["memory"]
        memory_id = str(memory.get("id", ""))

        multiword_seen = set()
        for phrase, _ in sorted(data["multiwords"], key=lambda x: (x[1], -len(x[0].split()))):
            if phrase in multiword_seen:
                continue
            multiword_seen.add(phrase)
            if add_suggestion(phrase, f"Unseen multiword term in memory {memory_id}", memory_id):
                return suggestions
            if len(multiword_seen) >= 2:
                break

    # TF-IDF derived concepts (processed after structural cues)
    for data in token_data:
        memory = data["memory"]
        memory_id = str(memory.get("id", ""))
        noun_counts: Counter[str] = data["noun_counts"]
        total_nouns: int = data["total_nouns"]
        if not total_nouns:
            continue

        scores: List[Tuple[float, str]] = []
        for lemma, count in noun_counts.items():
            tf = count / total_nouns
            idf = math.log((total_docs + 1) / (doc_freq[lemma] + 1)) + 1
            score = tf * idf
            scores.append((score, lemma))

        scores.sort(key=lambda item: (-item[0], item[1]))
        for _, lemma in scores[:2]:
            rationale = f"High TF-IDF noun in memory {memory_id}"
            if add_suggestion(lemma, rationale, memory_id):
                return suggestions

    if max_concepts is not None:
        return suggestions[: max_concepts]
    return suggestions


__all__ = ["suggest_concepts"]
