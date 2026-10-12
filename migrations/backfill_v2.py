"""Frozen conversion of v1 records. Retain IDs, attribution, proposals and decisions."""

from datetime import datetime
import hashlib
import json


def hashed(value):
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, ensure_ascii=False, separators=(",", ":")
        ).encode()
    ).hexdigest()


def convert(old):
    new = {
        name: []
        for name in ("runs", "companies", "people", "sources", "claims", "evidence")
    }
    for row in old["runs"]:
        new["runs"].append(
            dict(
                id=row["id"],
                status=row["status"],
                input={"origin": row["origin"], "mode": "legacy_reference"},
                operation_key=row["operation_key"],
                progress={"legacy_schema": "0001"},
                result=row["result"],
                cost=0,
                trace_id=row["trace_id"],
                trace_url=row["trace_url"],
                trace_status=row["trace_status"],
                error=row["error"],
                created_at=row["created_at"],
            )
        )
    for row in old["companies"]:
        decisions = [
            {k: str(v) if isinstance(v, datetime) else v for k, v in d.items()}
            for d in old["identity_decisions"]
            if d["company_id"] == row["id"]
        ]
        new["companies"].append(
            dict(
                id=row["id"],
                name=row["name"],
                domain=row["domain"],
                linkedin_url=row["linkedin_url"],
                identity={"status": row["identity_status"], "decisions": decisions},
                field_evidence={},
                created_at=row["created_at"],
            )
        )
    for row in old["people"]:
        new["people"].append(
            dict(
                id=row["id"],
                name=row["name"],
                identity={"status": row["identity_status"]},
                created_at=row["created_at"],
            )
        )
    for row in old["sources"]:
        segments = [
            dict(
                id=p["id"],
                index=p["segment_index"],
                start=p["start"],
                end=p["end"],
                text=p["text"],
                speaker=p["speaker_label"],
                words=[],
            )
            for p in old["passages"]
            if p["source_id"] == row["id"]
        ]
        segments.sort(key=lambda x: x["index"])
        content = dict(
            normalization_version="legacy-segments-v1",
            provider="apple",
            external_id=row["episode_id"],
            language=None,
            duration_seconds=None,
            coverage="partial",
            timing_status="available",
            segments=segments,
        )
        metadata = dict(
            row["provenance"],
            parent_sha256=row["parent_sha256"],
            legacy_sha256=row["sha256"],
        )
        retrieved = metadata.get("retrieved_at")
        new["sources"].append(
            dict(
                id=row["id"],
                kind="transcript",
                provider="apple",
                external_id=row["episode_id"],
                title=row["title"],
                url=row["url"],
                retrieved_at=datetime.fromisoformat(retrieved)
                if retrieved
                else row["created_at"],
                content=content,
                metadata=metadata,
                content_hash=hashed(content),
                version_hash=row["sha256"],
                raw_artifact={"name": row["artifact_name"], "sha256": row["sha256"]},
                run_id=row["run_id"],
                created_at=row["created_at"],
            )
        )
    proposals = {p["id"]: p for p in old["proposals"]}
    companies = {p["id"]: p["name"] for p in old["companies"]}
    people = {p["id"]: p["name"] for p in old["people"]}
    for row in old["claims"]:
        p = proposals[row["proposal_id"]]
        participants = [
            dict(
                kind="company",
                id=row["company_id"],
                name=companies[row["company_id"]],
                role="subject",
            )
        ]
        if row["person_id"]:
            participants.append(
                dict(
                    kind="person",
                    id=row["person_id"],
                    name=people[row["person_id"]],
                    role="object",
                )
            )
        new["claims"].append(
            dict(
                id=row["id"],
                text=row["statement"],
                participants=participants,
                status="needs_review",
                extraction={
                    "mode": "legacy_reference",
                    "predicate": row["predicate"],
                    "review_status": row["review_status"],
                    "assertion_status": row["assertion_status"],
                    "proposal": p["payload"],
                    "proposal_id": p["id"],
                },
                run_id=p["run_id"],
                created_at=row["created_at"],
            )
        )
    passages = {p["id"]: p for p in old["passages"]}
    for row in old["evidence"]:
        passage = passages[row["passage_id"]]
        start = passage["text"].index(row["quote"])
        new["evidence"].append(
            dict(
                id=row["id"],
                claim_id=row["claim_id"],
                source_id=passage["source_id"],
                locators=[
                    {
                        "segment_id": passage["id"],
                        "char_start": start,
                        "char_end": start + len(row["quote"]),
                    }
                ],
                quote=row["quote"],
                speaker_label=row["speaker_label"],
                role="support",
            )
        )
    return new
