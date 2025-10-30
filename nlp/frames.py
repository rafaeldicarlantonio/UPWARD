"""Clustering of predicate frames into higher-level event frames."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from .verbs import PredicateFrame, extract_predicates


FRAME_TYPES = {"transfer", "causation", "measurement", "claim"}

TRANSFER_VERBS = {
    "give",
    "send",
    "deliver",
    "share",
    "transfer",
    "sell",
    "loan",
}

CAUSATION_VERBS = {
    "cause",
    "trigger",
    "create",
    "make",
    "force",
    "lead",
}

MEASUREMENT_VERBS = {
    "measure",
    "record",
    "report",
    "log",
    "count",
}

CLAIM_VERBS = {
    "claim",
    "state",
    "say",
    "report",
    "announce",
}

COMPARATORS = {"<", ">", "=", "<=", ">=", "==", "!=", "≈"}

MOD_PREFIX_TIME = {"time", "when"}
MOD_PREFIX_LOCATION = {"loc", "location", "where"}
MOD_PREFIX_INSTRUMENT = {"with", "using", "via", "instrument"}


@dataclass(frozen=True)
class EventFrame:
    frame_id: str
    type: str
    roles: Dict[str, Optional[str]] = field(default_factory=dict)
    predicates: Sequence[PredicateFrame] = field(default_factory=list)


def _split_sentences(text: str) -> List[str]:
    sentences: List[str] = []
    start = 0
    for match in re.finditer(r"[^.!?]+[.!?]", text):
        segment = match.group(0).strip()
        if segment:
            sentences.append(segment)
        start = match.end()
    # Capture trailing text without punctuation
    if start < len(text):
        tail = text[start:].strip()
        if tail:
            sentences.append(tail)
    return sentences


def _initial_roles() -> Dict[str, Optional[str]]:
    return {
        "agent": None,
        "patient": None,
        "instrument": None,
        "time": None,
        "location": None,
    }


def _apply_modifier_roles(modifier: str, roles: Dict[str, Optional[str]]) -> None:
    lower = modifier.lower()
    prefix, value = None, None
    if ":" in modifier:
        prefix, remainder = modifier.split(":", 1)
        prefix = prefix.lower()
        value = remainder.strip()

    def assign(key: str, val: Optional[str]) -> None:
        if roles[key] is None and val:
            roles[key] = val

    if prefix and prefix in MOD_PREFIX_TIME:
        assign("time", value)
        return
    if prefix and prefix in MOD_PREFIX_LOCATION:
        assign("location", value)
        return
    if prefix and prefix in MOD_PREFIX_INSTRUMENT:
        assign("instrument", value)
        return

    # Fallback heuristics without prefix
    if lower in {"yesterday", "today", "tomorrow"} and roles["time"] is None:
        roles["time"] = modifier
    elif lower in {"office", "warehouse", "factory", "lab", "park"} and roles["location"] is None:
        roles["location"] = modifier


def _classify_frame(predicates: Sequence[PredicateFrame], roles: Dict[str, Optional[str]]) -> str:
    has_numeric = any(pred.numeric_args for pred in predicates)
    has_comparator = any(mod in COMPARATORS for pred in predicates for mod in pred.modifiers)
    verb_lemmas = {pred.verb_lemma for pred in predicates}

    if has_numeric or has_comparator or verb_lemmas & MEASUREMENT_VERBS:
        return "measurement"
    if verb_lemmas & CAUSATION_VERBS:
        return "causation"
    if verb_lemmas & TRANSFER_VERBS or (
        roles.get("agent") and roles.get("patient")
    ):
        return "transfer"
    if verb_lemmas & CLAIM_VERBS:
        return "claim"
    return "claim"


def _group_key(sentence_idx: int, predicate: PredicateFrame) -> Tuple[int, str]:
    entity = predicate.subject_entity or predicate.object_entity or predicate.verb_lemma
    return sentence_idx, entity


def _derive_roles(predicates: Sequence[PredicateFrame]) -> Dict[str, Optional[str]]:
    roles = _initial_roles()
    for predicate in predicates:
        if predicate.subject_entity and roles["agent"] is None:
            roles["agent"] = predicate.subject_entity
        if predicate.object_entity and roles["patient"] is None:
            roles["patient"] = predicate.object_entity

        for modifier in predicate.modifiers:
            _apply_modifier_roles(modifier, roles)

        if "instrument" in predicate.numeric_args and roles["instrument"] is None:
            values = predicate.numeric_args.get("instrument")
            if values:
                roles["instrument"] = str(values[0])

        if "time" in predicate.numeric_args and roles["time"] is None:
            values = predicate.numeric_args.get("time")
            if values:
                roles["time"] = str(values[0])
    return roles


def build_event_frames(
    predicate_batches: Sequence[Tuple[int, Sequence[PredicateFrame]]],
    *,
    max_frames: Optional[int] = None,
) -> List[EventFrame]:
    frames: List[EventFrame] = []
    frame_counter = 1

    for sentence_idx, predicates in predicate_batches:
        if not predicates:
            continue

        groups: Dict[Tuple[int, str], List[PredicateFrame]] = {}
        for predicate in predicates:
            key = _group_key(sentence_idx, predicate)
            groups.setdefault(key, []).append(predicate)

        for _, grouped_predicates in groups.items():
            roles = _derive_roles(grouped_predicates)
            frame_type = _classify_frame(grouped_predicates, roles)
            frame = EventFrame(
                frame_id=f"frame-{frame_counter}",
                type=frame_type,
                roles=roles,
                predicates=list(grouped_predicates),
            )
            frames.append(frame)
            frame_counter += 1

            if max_frames is not None and len(frames) >= max_frames:
                return frames

    return frames


def extract_event_frames(
    text: str,
    *,
    backend=None,
    max_frames: Optional[int] = None,
) -> List[EventFrame]:
    sentences = _split_sentences(text)
    predicate_batches: List[Tuple[int, Sequence[PredicateFrame]]] = []

    for idx, sentence in enumerate(sentences):
        predicates = extract_predicates(sentence, backend=backend)
        if predicates:
            predicate_batches.append((idx, predicates))
        if max_frames is not None and len(predicate_batches) >= max_frames:
            # We still build via builder to honor grouping rules but early exit if no more frames desired.
            break

    return build_event_frames(predicate_batches, max_frames=max_frames)


__all__ = ["EventFrame", "build_event_frames", "extract_event_frames"]
