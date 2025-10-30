#!/usr/bin/env python3
"""Tests for simple contradiction detection."""

from __future__ import annotations

from typing import List

from nlp.contradictions import detect_contradictions
from nlp.verbs import PredicateFrame


def _pred(
    verb: str,
    *,
    subject: str,
    obj: str | None = None,
    polarity: str = "positive",
    numeric: float | None = None,
) -> PredicateFrame:
    numeric_args = {}
    if numeric is not None:
        numeric_args = {"attr": [numeric]}
    return PredicateFrame(
        verb_lemma=verb,
        subject_entity=subject,
        object_entity=obj,
        modifiers=[],
        polarity=polarity,
        numeric_args=numeric_args,
    )


def test_negation_contradiction_detected():
    predicates = [
        _pred("be", subject="Widget", obj="available", polarity="positive"),
        _pred("be", subject="Widget", obj="available", polarity="negative"),
    ]

    contradictions = detect_contradictions(predicates)

    assert len(contradictions) == 1
    contradiction = contradictions[0]
    assert contradiction.subject_text == "Widget"
    assert "not" in contradiction.claim_b.lower()


def test_numeric_contradiction_with_tolerance():
    predicates = [
        _pred("measure", subject="Sensor", numeric=100.0),
        _pred("measure", subject="Sensor", numeric=120.0),
    ]

    contradictions = detect_contradictions(predicates, tolerance=0.1)

    assert len(contradictions) == 1
    contradiction = contradictions[0]
    assert "Sensor" in contradiction.claim_a
    assert "Sensor" in contradiction.claim_b


def test_numeric_within_tolerance_not_flagged():
    predicates = [
        _pred("measure", subject="Sensor", numeric=100.0),
        _pred("measure", subject="Sensor", numeric=103.0),
    ]

    contradictions = detect_contradictions(predicates, tolerance=0.1)

    assert contradictions == []
