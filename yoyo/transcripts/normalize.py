"""Provider-independent seconds and stable segment IDs; never invent speaker names."""

import hashlib
import json

from .models import Segment, Transcript, Word
from .ttml import parse_ttml


def normalize(
    data: bytes,
    *,
    external_id: str,
    provider="apple",
    format="json",
    duration_seconds=None,
    coverage="full",
    timing_unit="seconds",
):
    if format not in {"json", "ttml"}:
        raise ValueError("Unsupported transcript format")
    raw = (
        parse_ttml(data, episode_id=external_id)
        if format == "ttml"
        else json.loads(data)
    )
    embedded_id = raw.get("episodeId")
    if embedded_id is not None and str(embedded_id) != external_id:
        raise ValueError("Transcript episode ID does not match metadata")
    if timing_unit not in {"seconds", "milliseconds"}:
        raise ValueError("Unknown timing unit")
    scale = 1000 if timing_unit == "milliseconds" else 1
    if format == "ttml":
        scale = 1

    def seconds(value):
        return value / scale if value is not None else None

    version = hashlib.sha256(data).hexdigest()[:12]
    segments = []
    for i, item in enumerate(raw.get("segments", raw.get("sentences", []))):
        index = item.get("index", i)
        words = [
            Word(
                text=w["text"], start=seconds(w.get("start")), end=seconds(w.get("end"))
            )
            for w in item.get("words") or []
        ]
        segments.append(
            Segment(
                id=f"{version}:{index}",
                index=index,
                start=seconds(item.get("start")),
                end=seconds(item.get("end")),
                text=item["text"],
                speaker=item.get("speaker"),
                words=words,
            )
        )
    if not segments:
        raise ValueError("Transcript has no segments")
    timed = sum(s.start is not None for s in segments)
    timing = (
        "available"
        if timed == len(segments)
        else "missing"
        if timed == 0
        else "partial"
    )
    return Transcript(
        provider=provider,
        external_id=external_id,
        language=raw.get("language"),
        duration_seconds=duration_seconds or raw.get("durationSeconds"),
        coverage=coverage,
        timing_status=timing,
        segments=segments,
    )
