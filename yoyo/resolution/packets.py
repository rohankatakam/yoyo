"""Small source-linked packets; original metadata remains in the source snapshot."""

import re
from html.parser import HTMLParser
from ..artifacts import digest


class Notes(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts, self.links = [], []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self.hidden += 1
        if tag in {"p", "br", "li", "div"}:
            self.parts.append("\n")
        if tag == "a":
            self.links.extend(v for k, v in attrs if k == "href" and v)

    def handle_endtag(self, tag):
        if tag in {"script", "style"}:
            self.hidden = max(0, self.hidden - 1)
        if tag in {"p", "li", "div"}:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def episode_context(source, name):
    meta = source.get("metadata", {})
    raw = meta.get("description") or meta.get("showNotes") or ""
    parser = Notes()
    parser.feed(raw)
    paragraphs = [p.strip() for p in "".join(parser.parts).splitlines() if p.strip()]
    # Keep short notes intact; select matching paragraphs in long notes.
    terms = set(re.findall(r"[a-z0-9]+", name.lower())) - {"inc", "the", "company"}
    selected = (
        paragraphs
        if len("\n".join(paragraphs)) <= 6000
        else [p for p in paragraphs if terms & set(re.findall(r"[a-z0-9]+", p.lower()))]
    )
    text = "\n".join(selected)[:6000]
    links = list(dict.fromkeys(parser.links + re.findall(r"https?://[^\s<>]+", text)))
    retrieved = source.get("retrieved_at")
    return {
        "source_id": source["id"],
        "source_url": source.get("url"),
        "retrieved_at": str(retrieved) if retrieved else None,
        "title": source.get("title"),
        "published_at": str(source.get("published_at")),
        "description_excerpt": text,
        "original_description_hash": digest(raw),
        "truncated": text != "\n".join(paragraphs),
        "candidate_links": [
            u.rstrip(".,;)") for u in links if u.startswith(("https://", "http://"))
        ],
        "role": "supplementary_identity_context_not_transcript_evidence",
    }


def transcript_packet(source, name, claims):
    segments = source["content"]["segments"]
    selected, anchors = set(), []
    for claim in claims:
        if not any(p.kind == "company" and p.name == name for p in claim.participants):
            continue
        for q in claim.quotes:
            if name.casefold() in q.quote.casefold():
                anchors.append(q.segment_id)
    positions = {s["id"]: i for i, s in enumerate(segments)}
    # Three distinct target occurrences, complete adjacent segments, source order.
    for anchor in list(dict.fromkeys(anchors))[:3]:
        i = positions[anchor]
        selected.update(range(max(0, i - 1), min(len(segments), i + 2)))
    return [
        {k: s.get(k) for k in ("id", "text", "speaker", "start", "end")}
        for i, s in enumerate(segments)
        if i in selected
    ]
