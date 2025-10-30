#!/usr/bin/env python3
"""Tests for the ingest tokenization helpers."""

from __future__ import annotations

import pytest

from nlp.tokenize import NullBackend, Token, tokenize_text


@pytest.fixture
def sample_text() -> str:
    return "The quick brown fox jumps over the lazy dog."


@pytest.fixture
def null_backend() -> NullBackend:
    return NullBackend()


def test_null_backend_is_deterministic(sample_text: str, null_backend: NullBackend):
    tokens = tokenize_text(sample_text, backend=null_backend)

    expected = [
        Token(text="The", lemma="the", pos="DET", dep="det", head=0),
        Token(text="quick", lemma="quick", pos="ADJ", dep="amod", head=0),
        Token(text="brown", lemma="brown", pos="ADJ", dep="amod", head=1),
        Token(text="fox", lemma="fox", pos="NOUN", dep="nsubj", head=2),
        Token(text="jumps", lemma="jumps", pos="VERB", dep="ROOT", head=3),
        Token(text="over", lemma="over", pos="ADP", dep="prep", head=4),
        Token(text="the", lemma="the", pos="DET", dep="det", head=5),
        Token(text="lazy", lemma="lazy", pos="ADJ", dep="amod", head=6),
        Token(text="dog", lemma="dog", pos="NOUN", dep="pobj", head=7),
        Token(text=".", lemma=".", pos="PUNCT", dep="punct", head=8),
    ]

    assert tokens == expected


def test_zero_budget_returns_no_tokens(sample_text: str, null_backend: NullBackend):
    tokens = tokenize_text(sample_text, backend=null_backend, max_ms_per_chunk=0)
    assert tokens == []


class FakeClock:
    def __init__(self) -> None:
        self._current = 0.0

    def __call__(self) -> float:
        return self._current

    def advance(self, ms: float) -> None:
        self._current += ms / 1000.0


class SlowBackend(NullBackend):
    def __init__(self, clock: FakeClock, step_ms: float = 5.0):
        super().__init__()
        self._clock = clock
        self._step_ms = step_ms

    def tokenize(self, text: str):  # type: ignore[override]
        for token in super().tokenize(text):
            self._clock.advance(self._step_ms)
            yield token


def test_time_budget_causes_early_exit(sample_text: str):
    clock = FakeClock()
    backend = SlowBackend(clock=clock, step_ms=5.0)

    tokens = tokenize_text(
        sample_text,
        backend=backend,
        max_ms_per_chunk=7,
        clock=clock,
    )

    assert len(tokens) == 1
    assert tokens[0].text == "The"


def test_tokens_are_structured(sample_text: str, null_backend: NullBackend):
    tokens = tokenize_text(sample_text, backend=null_backend)

    for token in tokens:
        assert isinstance(token, Token)
        assert token.text
        assert token.lemma is not None
        assert token.pos is not None
        assert token.dep is not None
