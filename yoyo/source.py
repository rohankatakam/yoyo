from datetime import UTC, datetime

from .artifacts import digest, stable, store_bytes


def source_record(transcript, raw: bytes, metadata: dict, format="json"):
    content = transcript.model_dump(mode="json")
    snapshot = dict(metadata)
    snapshot.setdefault(
        "review",
        "Model extraction; pending human review. Audio not independently checked.",
    )
    # Retrieval time is operational metadata, not a reason to create a new source version.
    retrieved = snapshot.pop("retrieved_at", None)
    version = digest({"content": content, "metadata": snapshot})
    published = snapshot.get("releaseDate") or snapshot.get("published_at")
    return dict(
        id=stable("source", version),
        kind="transcript",
        provider=transcript.provider,
        external_id=transcript.external_id,
        title=snapshot.get("title") or transcript.external_id,
        url=snapshot.get("itunesUrl") or snapshot.get("url"),
        published_at=datetime.fromisoformat(published.replace("Z", "+00:00"))
        if published
        else None,
        retrieved_at=datetime.fromisoformat(retrieved.replace("Z", "+00:00"))
        if retrieved
        else datetime.now(UTC),
        content=content,
        metadata=snapshot,
        content_hash=digest(content),
        version_hash=version,
        raw_artifact=store_bytes(raw, format),
    )
