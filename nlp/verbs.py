"""Verb predicate extraction utilities built atop token metadata."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional

from .tokenize import Token, tokenize_text, TokenizationBackend


@dataclass(frozen=True)
class PredicateFrame:
    verb_lemma: str
    subject_entity: Optional[str]
    object_entity: Optional[str]
    modifiers: List[str] = field(default_factory=list)
    polarity: str = "positive"
    numeric_args: Dict[str, List[float]] = field(default_factory=dict)

NEGATION_DEPS = {"neg"}
NEGATION_WORDS = {"no", "not", "never", "none", "n't"}

SUBJECT_DEPS = {"nsubj", "csubj", "expl"}
PASSIVE_OBJECT_DEPS = {"nsubjpass"}
OBJECT_DEPS = {"dobj", "obj", "pobj", "attr", "oprd", "dative"}
AGENT_DEPS = {"agent"}

COMPARISON_TOKENS = {"<", ">", "=", "<=", ">=", "==", "!="}
NUMERIC_DEPS = {"nummod", "quantmod", "attr", "dobj", "pobj", "obj"}


def _extract_numeric_value(text: str) -> Optional[float]:
    try:
        return float(text)
    except (ValueError, TypeError):
        return None


def _collect_children(tokens: List[Token], verb_index: int) -> Dict[str, List[int]]:
    children: Dict[str, List[int]] = {}
    for idx, token in enumerate(tokens):
        if token.head == verb_index and token.dep:
            children.setdefault(token.dep, []).append(idx)
    return children


def _record_numeric(target: Dict[str, List[float]], key: str, token: Token) -> None:
    value = _extract_numeric_value(token.lemma or token.text)
    if value is None:
        return
    target.setdefault(key, []).append(value)


def extract_predicates(
    text: str,
    backend: Optional[TokenizationBackend] = None,
    max_verbs: Optional[int] = None,
) -> List[PredicateFrame]:
    tokens = tokenize_text(text, backend=backend)
    frames: List[PredicateFrame] = []

    for idx, token in enumerate(tokens):
        if token.pos == "AUX" and token.dep not in {"ROOT"}:
            continue
        if token.pos not in {"VERB", "AUX"}:
            continue

        children = _collect_children(tokens, idx)
        subject = None
        obj = None
        modifiers: List[str] = []
        polarity = "positive"
        numeric_args: Dict[str, List[float]] = {}

        for dep, child_indices in children.items():
            for child_idx in child_indices:
                child = tokens[child_idx]
                child_text_lower = child.text.lower()
                child_lemma_lower = child.lemma.lower()

                if dep in NEGATION_DEPS or child_text_lower in NEGATION_WORDS or child_lemma_lower in NEGATION_WORDS:
                    polarity = "negative"
                elif dep in SUBJECT_DEPS and subject is None:
                    subject = child.lemma
                elif dep in PASSIVE_OBJECT_DEPS and obj is None:
                    obj = child.lemma
                elif dep in OBJECT_DEPS and obj is None:
                    obj = child.lemma
                elif dep in AGENT_DEPS and subject is None:
                    subject = child.lemma

                if child.text in COMPARISON_TOKENS or child.lemma in COMPARISON_TOKENS:
                    modifiers.append(child.text)
                    comparator_children = _collect_children(tokens, child_idx)
                    for sub_dep, sub_indices in comparator_children.items():
                        for sub_idx in sub_indices:
                            sub_token = tokens[sub_idx]
                            _record_numeric(numeric_args, child.text, sub_token)

                if dep in NUMERIC_DEPS or child.pos == "NUM":
                    _record_numeric(numeric_args, dep or child.text, child)

                # Also inspect auxiliary children for negations or numerics
                if dep in {"aux", "auxpass"}:
                    aux_children = _collect_children(tokens, child_idx)
                    for aux_dep, aux_indices in aux_children.items():
                        for aux_idx in aux_indices:
                            aux_token = tokens[aux_idx]
                            aux_text_lower = aux_token.text.lower()
                            aux_lemma_lower = aux_token.lemma.lower()
                            if aux_dep in NEGATION_DEPS or aux_text_lower in NEGATION_WORDS or aux_lemma_lower in NEGATION_WORDS:
                                polarity = "negative"
                            if aux_dep in NUMERIC_DEPS or aux_token.pos == "NUM":
                                _record_numeric(numeric_args, aux_dep or aux_token.text, aux_token)

        frame = PredicateFrame(
            verb_lemma=token.lemma,
            subject_entity=subject,
            object_entity=obj,
            modifiers=modifiers,
            polarity=polarity,
            numeric_args=numeric_args,
        )
        frames.append(frame)

        if max_verbs is not None and len(frames) >= max_verbs:
            break

    return frames


__all__ = ["PredicateFrame", "extract_predicates"]
