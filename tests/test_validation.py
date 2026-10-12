import json

import pytest

from yoyo.claim_models import Annotation, Candidate
from yoyo.transcripts.normalize import normalize
from yoyo.validate import validate_annotation, validate_claim


def transcript(**changes):
    segment = dict(text="Acme may expand.", start=0, end=5, words=[])
    segment.update(changes)
    return normalize(json.dumps({"segments": [segment]}).encode(), external_id="test")


def claim(t):
    s = t.segments[0]
    return Candidate(
        text=s.text,
        predicate="may_expand",
        participants=[{"kind": "company", "name": "Acme", "role": "subject"}],
        anchor_segment_id=s.id,
        speaker_label=s.speaker,
        quotes=[{"segment_id": s.id, "quote": s.text}],
        rationale="Explicit possibility",
        context="actual",
    )


def test_empty_words_and_unknown_speaker_remain_unknown():
    t = transcript()
    assert t.segments[0].speaker is None and not t.segments[0].words
    assert validate_claim(claim(t), t)[0]["char_start"] == 0


@pytest.mark.parametrize(
    "changes",
    [
        {"start": float("nan")},
        {"end": -1},
        {"start": 6},
        {"end": None},
        {"words": [{"text": "wrong", "start": 9, "end": 10}]},
    ],
)
def test_bad_timing(changes):
    with pytest.raises(ValueError):
        transcript(**changes)


def test_milliseconds_and_truncation():
    raw = json.dumps(
        {"segments": [{"text": "Acme", "start": 1000, "end": 2000}]}
    ).encode()
    t = normalize(raw, external_id="test", timing_unit="milliseconds")
    assert t.segments[0].start == 1
    with pytest.raises(ValueError, match="truncated"):
        normalize(
            raw, external_id="test", timing_unit="milliseconds", duration_seconds=200
        )


def test_ttml_keeps_native_speaker_and_word_times():
    xml = b"""<tt xmlns="http://www.w3.org/ns/ttml" xmlns:ttm="http://www.w3.org/ns/ttml#metadata"><body><div><p begin="0s" end="5s" ttm:agent="speaker1"><span begin="0s" end="2s">Acme</span><span begin="2s" end="5s">grows.</span></p></div></body></tt>"""
    t = normalize(xml, external_id="test", format="ttml")
    assert t.segments[0].start == 0 and t.segments[0].end == 5
    assert t.segments[0].speaker == "speaker1"


@pytest.mark.parametrize("kind", ["quote", "speaker", "qualifier", "number", "name"])
def test_unsupported_claim_rejected(kind):
    t = transcript(speaker="speaker1")
    c = claim(t)
    if kind == "quote":
        c.quotes[0].quote = "not in transcript"
    if kind == "speaker":
        c.speaker_label = "speaker2"
    if kind == "qualifier":
        c.text = "Acme expands."
    if kind == "number":
        c.text = "Acme may expand 20%."
    if kind == "name":
        c.participants[0].name = "Another company"
    with pytest.raises(ValueError):
        validate_claim(c, t)


def test_annotation_cannot_introduce_evidence():
    t = transcript()
    annotation = Annotation(
        time_class="UNCLEAR", supporting_segment_ids=["missing"], rationale="Unclear"
    )
    with pytest.raises(ValueError):
        validate_annotation(annotation, claim(t))


def test_optional_enrichment_is_typed_and_needs_evidence():
    from yoyo.company_models import CompanyProfile, FinancialObservation

    assert CompanyProfile().funding_stage is None
    with pytest.raises(ValueError, match="Evidence required"):
        CompanyProfile(sector_id="industrial")
    value = FinancialObservation(
        type="funding_raised",
        amount="10.50",
        currency="USD",
        date="2026-01-01",
        basis="reported round",
        source_id="source",
        quote="raised",
    )
    assert value.type == "funding_raised" and str(value.date) == "2026-01-01"
    with pytest.raises(ValueError):
        FinancialObservation(
            type="revenue",
            amount=10,
            currency="USD",
            basis="report",
            source_id="source",
            quote="revenue",
        )


def test_grounding_preserves_assertion_and_only_fixes_unique_exact_locators():
    from yoyo.grounding import ground

    t = transcript(speaker="speaker1")
    c = claim(t)
    c.anchor_segment_id = c.quotes[0].segment_id = "wrong"
    fixed = ground(c, t.segments)
    assert fixed.text == c.text and fixed.quotes[0].quote == c.quotes[0].quote
    assert validate_claim(fixed, t)
    c.quotes[0].quote = "invented"
    assert ground(c, t.segments).quotes[0].quote == "invented"


def test_grounding_adds_context_without_claiming_it_supports_relation():
    from yoyo.grounding import ground

    raw = json.dumps(
        {
            "segments": [
                {"text": "Welcome Acme.", "start": 0, "end": 2},
                {"text": "We may expand.", "start": 2, "end": 5},
            ]
        }
    ).encode()
    t = normalize(raw, external_id="test")
    c = claim(t)
    c.anchor_segment_id = t.segments[1].id
    c.quotes[0].segment_id = t.segments[1].id
    c.quotes[0].quote = "We may expand."
    c.text = "Acme may expand."
    fixed = ground(c, t.segments)
    assert fixed.quotes[-1].role == "context"
    assert validate_claim(fixed, t)
