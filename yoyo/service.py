"""Only application functions write research data; API/CLI/agent share this boundary."""

import hashlib
import json
import os
import tempfile
from uuid import uuid4, uuid5, NAMESPACE_URL
from sqlalchemy import select, func, text
from sqlalchemy.dialects.postgresql import insert
from . import db
from .config import settings
from .contracts import Bundle

TRACKED = (
    db.companies,
    db.people,
    db.sources,
    db.passages,
    db.proposals,
    db.claims,
    db.evidence,
    db.identity_decisions,
)


def canonical(value):
    return json.dumps(
        value, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    ).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def stable(*parts):
    return str(uuid5(NAMESPACE_URL, json.dumps(parts)))


def counts(conn):
    return {t.name: conn.scalar(select(func.count()).select_from(t)) for t in TRACKED}


def save(conn, table, **values):
    return conn.execute(
        insert(table)
        .values(**values)
        .on_conflict_do_nothing(index_elements=[table.c.id])
        .returning(table.c.id)
    ).scalar_one_or_none()


def validate(bundle):
    segments = {s.index: s for s in bundle.source.segments}
    for f in bundle.findings:
        s = segments.get(f.segment_index)
        if s is None or f.quote not in s.text:
            raise ValueError("Quote must match its stored passage exactly")
        if f.speaker_label != s.speaker:
            raise ValueError("Speaker label must match stored passage")
        if f.company not in f.quote:
            raise ValueError("Reference company must appear in its quote")
        if f.predicate == "has_ceo" and (not f.person or f.person not in f.quote):
            raise ValueError("CEO reference requires a quoted person")
        if f.predicate == "reported_age" and f.person is not None:
            raise ValueError("Age reference has no person object")


def commit_findings(bundle: Bundle, run_id: str, fail_after_source=False):
    """Validate, then atomically persist. Episode-scoped identity until resolution exists."""
    validate(bundle)
    source_data = bundle.source.model_dump()
    source_hash = digest(source_data)
    settings.artifact_dir.mkdir(parents=True, exist_ok=True)
    artifact = settings.artifact_dir / (source_hash + ".json")
    # Publish complete bytes atomically; concurrent replays never observe a partial file.
    with tempfile.NamedTemporaryFile(dir=settings.artifact_dir, delete=False) as staged:
        staged.write(canonical(source_data))
        staged.flush()
        os.fsync(staged.fileno())
    try:
        try:
            os.link(staged.name, artifact)
        except FileExistsError:
            if artifact.read_bytes() != canonical(source_data):
                raise ValueError("Stored artifact hash mismatch")
    finally:
        os.unlink(staged.name)
    source_id = stable("source", source_hash)
    with db.engine.begin() as conn:
        # One writer in v0.1: also makes before/after counts meaningful under replay.
        conn.execute(text("SELECT pg_advisory_xact_lock(91827461)"))
        before = counts(conn)
        save(
            conn,
            db.sources,
            id=source_id,
            episode_id=bundle.source.episode_id,
            title=bundle.source.title,
            url=bundle.source.url,
            sha256=source_hash,
            parent_sha256=bundle.source.parent_sha256,
            artifact_name=artifact.name,
            provenance=bundle.source.provenance,
            run_id=run_id,
        )
        if fail_after_source:
            raise RuntimeError("Injected interruption before findings")
        for s in bundle.source.segments:
            save(
                conn,
                db.passages,
                id=stable(source_id, s.index),
                source_id=source_id,
                segment_index=s.index,
                start=s.start,
                end=s.end,
                speaker_label=s.speaker,
                text=s.text,
            )
        saved_claims, new_entities, reused_entities = [], set(), set()
        for f in bundle.findings:
            company_id = stable(
                "company", bundle.source.episode_id, f.company.casefold()
            )
            created = save(
                conn,
                db.companies,
                id=company_id,
                name=f.company,
                identity_status="episode_scoped_unresolved",
            )
            (new_entities if created else reused_entities).add(company_id)
            person_id = (
                stable("person", bundle.source.episode_id, f.person.casefold())
                if f.person
                else None
            )
            if person_id:
                save(
                    conn,
                    db.people,
                    id=person_id,
                    name=f.person,
                    identity_status="episode_scoped_unresolved",
                )
            proposal_id = stable("proposal", source_id, digest(f.model_dump()))
            save(
                conn,
                db.proposals,
                id=proposal_id,
                run_id=run_id,
                payload=f.model_dump(),
                status="accepted_reference",
            )
            claim_id = stable("claim", company_id, person_id, f.predicate, f.statement)
            save(
                conn,
                db.claims,
                id=claim_id,
                company_id=company_id,
                person_id=person_id,
                predicate=f.predicate,
                statement=f.statement,
                assertion_status="attributed_not_verified",
                review_status=f.review_status,
                proposal_id=proposal_id,
            )
            save(
                conn,
                db.evidence,
                id=stable("evidence", claim_id, source_id, f.segment_index, f.quote),
                claim_id=claim_id,
                passage_id=stable(source_id, f.segment_index),
                quote=f.quote,
                speaker_label=f.speaker_label,
                attribution_status="transcript_label_only",
            )
            save(
                conn,
                db.identity_decisions,
                id=stable("decision", company_id, source_id),
                company_id=company_id,
                source_id=source_id,
                run_id=run_id,
                decision="unresolved",
                rationale="Name in quoted passage; episode-scoped record. Domain, LinkedIn and cross-episode identity have not been verified.",
            )
            saved_claims.append(claim_id)
        after = counts(conn)
        result = {
            "status": "completed",
            "source_id": source_id,
            "claim_ids": sorted(set(saved_claims)),
            "added_entity_ids": sorted(new_entities),
            "reused_entity_ids": sorted(reused_entities - new_entities),
            "before": before,
            "after": after,
            "delta": {k: after[k] - before[k] for k in before},
            "research_cost_usd": 0,
            "cost_basis": "Reference import; no model or research-provider calls",
        }
        conn.execute(
            db.runs.update()
            .where(db.runs.c.id == run_id)
            .values(status="completed", result=result)
        )
        return result


def import_bundle(bundle: Bundle, *, tracing=True, fail_after_source=False):
    run_id = str(uuid4())
    enabled = (
        tracing and settings.langsmith_tracing and bool(settings.langsmith_api_key)
    )
    with db.engine.begin() as conn:
        conn.execute(
            db.runs.insert().values(
                id=run_id,
                status="running",
                origin=bundle.origin,
                operation_key=digest(bundle.model_dump()),
                trace_status="pending" if enabled else "disabled",
            )
        )
    # Trace initialization/upload cannot change the outcome of a committed research write.
    trace = None
    if enabled:
        try:
            from langsmith import Client, RunTree

            client = Client(api_key=settings.langsmith_api_key)
            trace = RunTree(
                name="import_reference_episode",
                run_type="chain",
                id=run_id,
                client=client,
                project_name=settings.langsmith_project,
                inputs={
                    "episode_id": bundle.source.episode_id,
                    "finding_count": len(bundle.findings),
                },
                extra={
                    "metadata": {
                        "run_id": run_id,
                        "operation_key": digest(bundle.model_dump()),
                        "mode": "reference_import",
                    }
                },
            )
            trace.post()
        except Exception:
            trace = None
            with db.engine.begin() as conn:
                conn.execute(
                    db.runs.update()
                    .where(db.runs.c.id == run_id)
                    .values(trace_status="error")
                )
    child = None
    if trace:
        try:
            child = trace.create_child(
                name="validate_and_commit_findings",
                run_type="tool",
                inputs={"episode_id": bundle.source.episode_id},
            )
            child.post()
        except Exception:
            child = None
    try:
        result = commit_findings(bundle, run_id, fail_after_source=fail_after_source)
    except Exception as exc:
        with db.engine.begin() as conn:
            conn.execute(
                db.runs.update()
                .where(db.runs.c.id == run_id)
                .values(status="failed", error=str(exc))
            )
        if trace:
            try:
                if child:
                    child.end(error=str(exc))
                    child.patch()
                trace.end(error=str(exc))
                trace.patch()
                with db.engine.begin() as conn:
                    conn.execute(
                        db.runs.update()
                        .where(db.runs.c.id == run_id)
                        .values(
                            trace_id=run_id,
                            trace_url=trace.get_url(),
                            trace_status="submitted",
                        )
                    )
            except Exception:
                with db.engine.begin() as conn:
                    conn.execute(
                        db.runs.update()
                        .where(db.runs.c.id == run_id)
                        .values(trace_status="error")
                    )
        raise
    if trace:
        try:
            if child:
                child.end(outputs=result)
                child.patch()
            trace.end(outputs=result)
            trace.patch()
            url = trace.get_url()
            with db.engine.begin() as conn:
                conn.execute(
                    db.runs.update()
                    .where(db.runs.c.id == run_id)
                    .values(trace_id=run_id, trace_url=url, trace_status="submitted")
                )
        except Exception:
            with db.engine.begin() as conn:
                conn.execute(
                    db.runs.update()
                    .where(db.runs.c.id == run_id)
                    .values(trace_status="error")
                )
    return {"run_id": run_id, **result}
