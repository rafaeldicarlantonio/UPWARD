#!/usr/bin/env python3
"""Tests for predicate extraction."""

from __future__ import annotations

from typing import Dict, Iterable, List

import pytest

from nlp.tokenize import Token, TokenizationBackend
from nlp.verbs import extract_predicates


def _tok(text: str, lemma: str, pos: str, dep: str, head: int) -> Token:
    return Token(text=text, lemma=lemma, pos=pos, dep=dep, head=head)


class FixtureBackend(TokenizationBackend):
    def __init__(self, fixtures: Dict[str, List[Token]]):
        self._fixtures = fixtures

    def tokenize(self, text: str) -> Iterable[Token]:
        try:
            return list(self._fixtures[text])
        except KeyError:
            raise AssertionError(f"No fixture tokens provided for text: '{text}'")


@pytest.fixture
def backend() -> FixtureBackend:
    fixtures: Dict[str, List[Token]] = {}

    fixtures["The fox jumps over the log."] = [
        _tok("The", "the", "DET", "det", 1),
        _tok("fox", "fox", "NOUN", "nsubj", 2),
        _tok("jumps", "jump", "VERB", "ROOT", 2),
        _tok("over", "over", "ADP", "prep", 2),
        _tok("the", "the", "DET", "det", 5),
        _tok("log", "log", "NOUN", "dobj", 2),
        _tok(".", ".", "PUNCT", "punct", 2),
    ]

    fixtures["The log was jumped by the fox."] = [
        _tok("The", "the", "DET", "det", 1),
        _tok("log", "log", "NOUN", "nsubjpass", 3),
        _tok("was", "be", "AUX", "auxpass", 3),
        _tok("jumped", "jump", "VERB", "ROOT", 3),
        _tok("by", "by", "ADP", "prep", 3),
        _tok("the", "the", "DET", "det", 6),
        _tok("fox", "fox", "NOUN", "agent", 3),
        _tok(".", ".", "PUNCT", "punct", 3),
    ]

    fixtures["The fox does not jump over the log."] = [
        _tok("The", "the", "DET", "det", 1),
        _tok("fox", "fox", "NOUN", "nsubj", 4),
        _tok("does", "do", "AUX", "aux", 4),
        _tok("not", "not", "PART", "neg", 4),
        _tok("jump", "jump", "VERB", "ROOT", 4),
        _tok("over", "over", "ADP", "prep", 4),
        _tok("the", "the", "DET", "det", 7),
        _tok("log", "log", "NOUN", "dobj", 4),
        _tok(".", ".", "PUNCT", "punct", 4),
    ]

    fixtures["The fox has no fear."] = [
        _tok("The", "the", "DET", "det", 1),
        _tok("fox", "fox", "NOUN", "nsubj", 2),
        _tok("has", "have", "VERB", "ROOT", 2),
        _tok("no", "no", "PART", "neg", 2),
        _tok("fear", "fear", "NOUN", "dobj", 2),
        _tok(".", ".", "PUNCT", "punct", 2),
    ]

    for op in (">", "<", "="):
        text = f"Sales is {op} 5."
        fixtures[text] = [
            _tok("Sales", "sales", "NOUN", "nsubj", 1),
            _tok("is", "be", "VERB", "ROOT", 1),
            _tok(op, op, "SYM", "advmod", 1),
            _tok("5", "5", "NUM", "attr", 2),
            _tok(".", ".", "PUNCT", "punct", 1),
        ]

    fixtures["The fox jumps and runs."] = [
        _tok("The", "the", "DET", "det", 1),
        _tok("fox", "fox", "NOUN", "nsubj", 2),
        _tok("jumps", "jump", "VERB", "ROOT", 2),
        _tok("and", "and", "CCONJ", "cc", 2),
        _tok("runs", "run", "VERB", "conj", 2),
        _tok(".", ".", "PUNCT", "punct", 2),
    ]

    return FixtureBackend(fixtures)


def test_active_voice_predicate(backend: FixtureBackend):
    frames = extract_predicates("The fox jumps over the log.", backend=backend)

    assert len(frames) == 1
    frame = frames[0]
    assert frame.verb_lemma == "jump"
    assert frame.subject_entity == "fox"
    assert frame.object_entity == "log"
    assert frame.polarity == "positive"


def test_passive_voice_predicate(backend: FixtureBackend):
    frames = extract_predicates("The log was jumped by the fox.", backend=backend)

    assert len(frames) == 1
    frame = frames[0]
    assert frame.verb_lemma == "jump"
    assert frame.subject_entity == "fox"
    assert frame.object_entity == "log"


def test_negation_detection_not(backend: FixtureBackend):
    frames = extract_predicates("The fox does not jump over the log.", backend=backend)

    assert frames[0].polarity == "negative"


def test_negation_detection_no(backend: FixtureBackend):
    frames = extract_predicates("The fox has no fear.", backend=backend)

    assert frames[0].polarity == "negative"


@pytest.mark.parametrize("operator", [">", "<", "="])
def test_numeric_comparisons(operator: str, backend: FixtureBackend):
    frames = extract_predicates(f"Sales is {operator} 5.", backend=backend)

    assert len(frames) == 1
    frame = frames[0]
    assert operator in frame.modifiers
    assert operator in frame.numeric_args
    assert frame.numeric_args[operator] == [5.0]


def test_max_verbs_limit(backend: FixtureBackend):
    frames = extract_predicates("The fox jumps and runs.", backend=backend, max_verbs=1)
    assert len(frames) == 1
