"""Tokenization utilities with optional POS/dep backends and time budgeting."""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Iterable, List, Optional, Protocol, Sequence, Tuple, Dict, Callable


class TokenizationBackend(Protocol):
    """Interface definition for tokenization backends."""

    def tokenize(self, text: str) -> Iterable["Token"]:
        """Yield tokens for the provided text."""


@dataclass(frozen=True)
class Token:
    """Structured token information."""

    text: str
    lemma: str
    pos: str
    dep: str
    head: Optional[int]


class SpacyBackend:
    """spaCy-based backend that exposes lemma/POS/dep/head attributes."""

    def __init__(self, model: str = "en_core_web_sm", disable: Optional[Sequence[str]] = None):
        try:
            import spacy  # type: ignore
        except ImportError as exc:  # pragma: no cover - exercised in runtime only
            raise RuntimeError(
                "spaCy is not installed. Install it or use NullBackend for testing."
            ) from exc

        components = list(disable or ("ner", "textcat"))

        try:
            self._nlp = spacy.load(model, disable=components)  # type: ignore[attr-defined]
        except OSError as exc:  # pragma: no cover - depends on runtime model availability
            raise RuntimeError(
                f"spaCy model '{model}' is not installed. Run 'python -m spacy download {model}'."
            ) from exc

    def tokenize(self, text: str) -> Iterable[Token]:
        doc = self._nlp(text)
        for token in doc:
            head_index = token.head.i if token.head is not None else None
            yield Token(
                text=token.text,
                lemma=token.lemma_,
                pos=token.pos_,
                dep=token.dep_,
                head=head_index,
            )


class NullBackend:
    """Deterministic, dependency-free backend used for tests and fallbacks."""

    _PATTERN = re.compile(r"\w+|[^\w\s]", re.UNICODE)

    _DEFAULT_TAGS: Dict[str, Tuple[str, str]] = {
        "the": ("DET", "det"),
        "quick": ("ADJ", "amod"),
        "brown": ("ADJ", "amod"),
        "fox": ("NOUN", "nsubj"),
        "jumps": ("VERB", "ROOT"),
        "over": ("ADP", "prep"),
        "lazy": ("ADJ", "amod"),
        "dog": ("NOUN", "pobj"),
        "and": ("CCONJ", "cc"),
        "runs": ("VERB", "conj"),
        ",": ("PUNCT", "punct"),
        ".": ("PUNCT", "punct"),
        "?": ("PUNCT", "punct"),
        "!": ("PUNCT", "punct"),
    }

    def __init__(self, tags: Optional[Dict[str, Tuple[str, str]]] = None):
        self._tags = tags or self._DEFAULT_TAGS

    def tokenize(self, text: str) -> Iterable[Token]:
        tokens = list(self._PATTERN.findall(text))
        if not tokens:
            return []

        results: List[Token] = []
        for idx, raw in enumerate(tokens):
            norm = raw.lower()
            lemma = norm
            pos, dep = self._tags.get(norm, ("X", "dep"))
            head = idx - 1 if idx > 0 else idx
            results.append(Token(text=raw, lemma=lemma, pos=pos, dep=dep, head=head))
        return results


def _to_iterable(sequence_or_iterable: Iterable[Token] | List[Token]) -> Iterable[Token]:
    if isinstance(sequence_or_iterable, list):
        for token in sequence_or_iterable:
            yield token
        return
    yield from sequence_or_iterable


def tokenize_text(
    text: str,
    backend: Optional[TokenizationBackend] = None,
    max_ms_per_chunk: Optional[int] = None,
    clock: Optional[Callable[[], float]] = None,
) -> List[Token]:
    """Tokenize text with optional time budget constraints."""

    if max_ms_per_chunk is not None and max_ms_per_chunk <= 0:
        return []

    effective_clock = clock or time.perf_counter
    start = effective_clock()

    active_backend = backend or _load_default_backend()
    if active_backend is None:
        raise RuntimeError("No tokenization backend available.")

    tokens: List[Token] = []
    for token in _to_iterable(active_backend.tokenize(text)):
        if max_ms_per_chunk is not None:
            elapsed_ms = (effective_clock() - start) * 1000
            if elapsed_ms >= max_ms_per_chunk:
                break
        tokens.append(token)
    return tokens


_DEFAULT_BACKEND: Optional[TokenizationBackend] = None


def _load_default_backend() -> Optional[TokenizationBackend]:
    global _DEFAULT_BACKEND
    if _DEFAULT_BACKEND is not None:
        return _DEFAULT_BACKEND

    try:
        _DEFAULT_BACKEND = SpacyBackend()
    except Exception:
        _DEFAULT_BACKEND = NullBackend()
    return _DEFAULT_BACKEND


__all__ = [
    "Token",
    "TokenizationBackend",
    "SpacyBackend",
    "NullBackend",
    "tokenize_text",
]
