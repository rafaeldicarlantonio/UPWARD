#!/usr/bin/env python3
"""Tests for concept suggestion heuristics."""

from __future__ import annotations

from typing import Dict, Iterable, List

import pytest

from nlp.frames import EventFrame
from nlp.tokenize import Token, TokenizationBackend
from nlp.concepts import suggest_concepts


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

    fixtures["The supply chain network requires rapid logistics planning."] = [
        _tok("The", "the", "DET", "det", 1),
        _tok("supply", "supply", "NOUN", "compound", 2),
        _tok("chain", "chain", "NOUN", "compound", 3),
        _tok("network", "network", "NOUN", "nsubj", 4),
        _tok("requires", "require", "VERB", "ROOT", 4),
        _tok("rapid", "rapid", "ADJ", "amod", 6),
        _tok("logistics", "logistics", "NOUN", "compound", 7),
        _tok("planning", "planning", "NOUN", "dobj", 4),
        _tok(".", ".", "PUNCT", "punct", 4),
    ]

    fixtures["Sensors report temperature variance and climate metrics in warehouse."] = [
        _tok("Sensors", "sensors", "NOUN", "nsubj", 1),
        _tok("report", "report", "VERB", "ROOT", 2),
        _tok("temperature", "temperature", "NOUN", "dobj", 1),
        _tok("variance", "variance", "NOUN", "compound", 2),
        _tok("and", "and", "CCONJ", "cc", 1),
        _tok("climate", "climate", "NOUN", "conj", 2),
        _tok("metrics", "metric", "NOUN", "conj", 2),
        _tok("in", "in", "ADP", "prep", 1),
        _tok("warehouse", "warehouse", "NOUN", "pobj", 7),
        _tok(".", ".", "PUNCT", "punct", 1),
    ]

    return FixtureBackend(fixtures)


@pytest.fixture
def memories() -> List[Dict]:
    return [
        {
            "id": "m1",
            "text": "The supply chain network requires rapid logistics planning.",
            "frames": [
                EventFrame(
                    frame_id="frame-1",
                    type="transfer",
                    roles={"agent": "planner", "patient": None, "instrument": None, "location": None, "time": None},
                    predicates=[],
                )
            ],
        },
        {
            "id": "m2",
            "text": "Sensors report temperature variance and climate metrics in warehouse.",
            "frames": [
                EventFrame(
                    frame_id="frame-2",
                    type="measurement",
                    roles={"agent": "sensor array", "patient": None, "instrument": None, "location": None, "time": None},
                    predicates=[],
                )
            ],
        },
    ]


def test_concept_suggestions_from_multiple_signals(memories: List[Dict], backend: FixtureBackend):
    existing = [{"name": "Logistics Plan"}]

    suggestions = suggest_concepts(
        memories,
        existing,
        backend=backend,
        max_concepts=5,
    )

    names = {s["name"] for s in suggestions}

    assert "Supply Chain Network" in names
    assert "Temperature Variance" in names
    assert "Sensor Array" in names
    assert "Logistics Plan" not in names

    rationale_map = {s["name"]: s["rationale"] for s in suggestions}
    assert "Frame role agent" in rationale_map["Sensor Array"]
    assert "Unseen multiword term" in rationale_map["Supply Chain Network"]
    assert all(s["source_memory_id"] in {"m1", "m2"} for s in suggestions)


def test_deduplicates_against_existing_concepts(memories: List[Dict], backend: FixtureBackend):
    existing = [{"name": "Supply Chain Network"}, {"name": "Sensor Array"}]

    suggestions = suggest_concepts(
        memories,
        existing,
        backend=backend,
        max_concepts=5,
    )

    names = {s["name"] for s in suggestions}
    assert "Supply Chain Network" not in names
    assert "Sensor Array" not in names


def test_max_concepts_limits_output(memories: List[Dict], backend: FixtureBackend):
    suggestions = suggest_concepts(
        memories,
        [],
        backend=backend,
        max_concepts=2,
    )

    assert len(suggestions) == 2
    assert [s["name"] for s in suggestions] == ["Planner", "Sensor Array"]
