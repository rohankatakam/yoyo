"""Adapted from human_data/api/transcription/apple_local.py; native labels retained."""

import re
import xml.etree.ElementTree as ET
from typing import Any

TTML_NS = "http://www.w3.org/ns/ttml"
PODCASTS_NS = "http://podcasts.apple.com/transcript-ttml-internal"
TTM_NS = "http://www.w3.org/ns/ttml#metadata"
XML_NS = "http://www.w3.org/XML/1998/namespace"
PARSER_VERSION = "apple-ttml-v1"


def parse_ttml(
    data: bytes | str,
    *,
    episode_id: str | None = None,
    language_hint: str | None = None,
) -> dict[str, Any]:
    """Convert Apple TTML into the common segment/word JSON shape."""
    root = ET.fromstring(data)
    language = root.attrib.get(f"{{{XML_NS}}}lang") or language_hint
    body = root.find(f"{{{TTML_NS}}}body")
    duration = _parse_time(body.attrib.get("dur")) if body is not None else None
    segments: list[dict[str, Any]] = []

    for paragraph in root.findall(f".//{{{TTML_NS}}}p"):
        speaker = paragraph.attrib.get(f"{{{TTM_NS}}}agent")
        sentence_spans = [
            child
            for child in paragraph.findall(f"./{{{TTML_NS}}}span")
            if child.attrib.get(f"{{{PODCASTS_NS}}}unit") == "sentence"
        ]
        if not sentence_spans:
            sentence_spans = [paragraph]

        for sentence in sentence_spans:
            words = []
            for word in sentence.findall(f".//{{{TTML_NS}}}span"):
                if word.attrib.get(f"{{{PODCASTS_NS}}}unit") != "word":
                    continue
                text = "".join(word.itertext()).strip()
                if not text:
                    continue
                words.append(
                    {
                        "start": _parse_time(word.attrib.get("begin")),
                        "end": _parse_time(word.attrib.get("end")),
                        "text": text,
                    }
                )

            text = _join_words(item["text"] for item in words)
            if not text:
                text = " ".join(
                    part.strip() for part in sentence.itertext() if part.strip()
                )
            if not text:
                continue
            segments.append(
                {
                    "start": _parse_time(
                        sentence.attrib.get("begin") or paragraph.attrib.get("begin")
                    ),
                    "end": _parse_time(
                        sentence.attrib.get("end") or paragraph.attrib.get("end")
                    ),
                    "text": text,
                    "speaker": speaker,
                    "words": words,
                }
            )

    if duration is None:
        ends = [item["end"] for item in segments if item["end"] is not None]
        duration = max(ends, default=None)
    return {
        "source": "apple",
        "episodeId": episode_id,
        "language": language,
        "durationSeconds": duration,
        "text": " ".join(item["text"] for item in segments),
        "segments": segments,
    }


def _parse_time(value: str | None) -> float | None:
    if value is None:
        return None
    value = value.strip()
    if value.endswith("ms"):
        return float(value[:-2]) / 1000
    if value.endswith("s"):
        return float(value[:-1])
    if ":" not in value:
        return float(value)
    parts = [float(part) for part in value.split(":")]
    seconds = 0.0
    for part in parts:
        seconds = seconds * 60 + part
    return seconds


def _join_words(words: Any) -> str:
    text = " ".join(words)
    text = re.sub(r"\s+([,.;:!?%\]\)])", r"\1", text)
    text = re.sub(r"([\[\(])\s+", r"\1", text)
    return text
