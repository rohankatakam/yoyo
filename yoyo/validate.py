"""Structural evidence checks plus conservative checks for meaning changes.
These are not entailment proofs. All model findings remain pending human review.
"""

import re

from .claim_models import Annotation, Candidate
from .transcripts.models import Transcript

QUALIFIERS = (
    r"\baim\w*",
    r"\bwill\b",
    r"\bwould\b",
    r"\bshould\b",
    r"\bhope\w*",
    r"\bmay\b",
    r"\bmight\b",
    r"\bcould\b",
    r"\bexpect\w*",
    r"\bplan\w*",
    r"\bintend\w*",
    r"\bapproximately\b",
    r"\babout\b",
    r"\bnot\b",
    r"n't\b",
)


def validate_claim(claim: Candidate, transcript: Transcript):
    segments = {s.id: s for s in transcript.segments}
    if claim.anchor_segment_id not in segments:
        raise ValueError("Unknown anchor segment")
    if not any(q.role == "support" for q in claim.quotes):
        raise ValueError("No supporting quote")
    if not any(
        q.segment_id == claim.anchor_segment_id and q.role == "support"
        for q in claim.quotes
    ):
        raise ValueError("Anchor must have a supporting quote")
    if segments[claim.anchor_segment_id].speaker != claim.speaker_label:
        raise ValueError("Claim speaker does not match anchor")
    locators = []
    for q in claim.quotes:
        segment = segments.get(q.segment_id)
        if segment is None or q.quote not in segment.text:
            raise ValueError("Quote must match stored segment exactly")
        if q.role == "support" and segment.speaker != claim.speaker_label:
            raise ValueError(
                "Supporting quotes cross speakers; use context or separate claims"
            )
        offset = segment.text.index(q.quote)
        locators.append(
            {
                "segment_id": segment.id,
                "char_start": offset,
                "char_end": offset + len(q.quote),
            }
        )
    quoted = " ".join(q.quote for q in claim.quotes)
    for p in claim.participants:
        if p.name.casefold() not in quoted.casefold():
            raise ValueError("Participant name needs quoted context")
    support = " ".join(q.quote for q in claim.quotes if q.role == "support").lower()
    text = claim.text.lower()
    for pattern in QUALIFIERS:
        if re.search(pattern, support) and not re.search(pattern, text):
            raise ValueError("Claim drops a qualification or negation")

    def numbers(s):
        return set(re.findall(r"\b\d[\d,.%]*", s))

    if not numbers(text) <= numbers(quoted):
        raise ValueError("Claim introduces unsupported numbers")
    return locators


def validate_annotation(annotation: Annotation, claim: Candidate):
    allowed = {q.segment_id for q in claim.quotes}
    if not set(annotation.supporting_segment_ids) <= allowed:
        raise ValueError("Annotation refers to evidence outside the claim")
