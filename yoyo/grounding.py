"""Attach exact name context and correct uniquely matching quote locators.
Never change quote text, assertion text, roles or speaker labels.
Raw model responses remain in run artifacts for comparison.
"""

from .claim_models import Quote


def ground(candidate, segments):
    candidate = candidate.model_copy(deep=True)
    by_id = {s.id: s for s in segments}
    for quote in candidate.quotes:
        segment = by_id.get(quote.segment_id)
        if segment and quote.quote in segment.text:
            continue
        matches = [
            s
            for s in segments
            if quote.quote in s.text
            and (quote.role != "support" or s.speaker == candidate.speaker_label)
        ]
        if len(matches) == 1:
            original = quote.segment_id
            quote.segment_id = matches[0].id
            if candidate.anchor_segment_id == original and quote.role == "support":
                candidate.anchor_segment_id = quote.segment_id
    quoted = " ".join(q.quote for q in candidate.quotes).casefold()
    for participant in candidate.participants:
        if participant.name.casefold() in quoted:
            continue
        # Presence is context only, never independent support for the relationship.
        segment = next(
            (s for s in segments if participant.name.casefold() in s.text.casefold()),
            None,
        )
        if segment:
            candidate.quotes.append(
                Quote(segment_id=segment.id, quote=segment.text, role="context")
            )
            quoted += " " + segment.text.casefold()
    return candidate
