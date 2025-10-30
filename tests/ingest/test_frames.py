#!/usr/bin/env python3
"""Tests for event frame clustering heuristics."""

from __future__ import annotations

from typing import Dict, Iterable, List

import pytest

from nlp.frames import EventFrame, build_event_frames, extract_event_frames
from nlp.verbs import PredicateFrame


def _pred(
    verb: str,
    *,
    subject: str | None = None,
    obj: str | None = None,
    modifiers: List[str] | None = None,
    polarity: str = "positive",
    numeric_args: Dict[str, List[float]] | None = None,
) -> PredicateFrame:
    return PredicateFrame(
        verb_lemma=verb,
        subject_entity=subject,
        object_entity=obj,
        modifiers=list(modifiers or []),
        polarity=polarity,
        numeric_args=numeric_args or {},
    )


@pytest.fixture
def transfer_batch() -> List[PredicateFrame]:
    return [
        _pred(
            "give",
            subject="alice",
            obj="bob",
            modifiers=["with:note", "location:office"],
        )
    ]


@pytest.fixture
def measurement_batch() -> List[PredicateFrame]:
    return [
        _pred(
            "measure",
            subject="sensor",
            obj="temperature",
            modifiers=["=", "time:morning"],
            numeric_args={"attr": [23.0]},
        )
    ]


@pytest.fixture
def causation_batch() -> List[PredicateFrame]:
    return [
        _pred(
            "cause",
            subject="storm",
            obj="outage",
            modifiers=["location:grid"],
        )
    ]


def test_transfer_frame_roles_and_type(transfer_batch: List[PredicateFrame]):
    frames = build_event_frames([(0, transfer_batch)])

    assert len(frames) == 1
    frame = frames[0]
    assert frame.type == "transfer"
    assert frame.roles["agent"] == "alice"
    assert frame.roles["patient"] == "bob"
    assert frame.roles["instrument"] == "note"
    assert frame.roles["location"] == "office"
    assert frame.roles["time"] is None


def test_measurement_frame_classification(measurement_batch: List[PredicateFrame]):
    frames = build_event_frames([(0, measurement_batch)])

    frame = frames[0]
    assert frame.type == "measurement"
    assert frame.roles["agent"] == "sensor"
    assert frame.roles["patient"] == "temperature"
    assert frame.roles["time"] == "morning"


def test_causation_frame_classification(causation_batch: List[PredicateFrame]):
    frames = build_event_frames([(0, causation_batch)])

    frame = frames[0]
    assert frame.type == "causation"
    assert frame.roles["agent"] == "storm"
    assert frame.roles["patient"] == "outage"
    assert frame.roles["location"] == "grid"


def test_max_frames_limit(
    transfer_batch: List[PredicateFrame],
    measurement_batch: List[PredicateFrame],
    causation_batch: List[PredicateFrame],
):
    frames = build_event_frames(
        [
            (0, transfer_batch),
            (1, measurement_batch),
            (2, causation_batch),
        ],
        max_frames=2,
    )

    assert len(frames) == 2
    assert frames[0].frame_id == "frame-1"
    assert frames[1].frame_id == "frame-2"


def test_extract_event_frames_groups_by_sentence(monkeypatch):
    sentence_map: Dict[str, List[PredicateFrame]] = {
        "Alice gives Bob a gift.": [
            _pred("give", subject="alice", obj="bob", modifiers=["with:flowers"])
        ],
        "Sensors record 10 units.": [
            _pred(
                "record",
                subject="sensors",
                obj="units",
                modifiers=["=", "time:0900"],
                numeric_args={"attr": [10.0]},
            )
        ],
    }

    def fake_extract(sentence: str, backend=None, max_verbs=None):
        return list(sentence_map.get(sentence, []))

    monkeypatch.setattr("nlp.frames.extract_predicates", fake_extract)

    frames = extract_event_frames(
        "Alice gives Bob a gift. Sensors record 10 units.",
        max_frames=None,
    )

    assert len(frames) == 2
    assert frames[0].type == "transfer"
    assert frames[1].type == "measurement"
    assert frames[1].roles["time"] == "0900"
