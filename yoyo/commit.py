"""A single transaction commits validated claims, evidence and database-derived results."""

from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert

from . import db
from .artifacts import digest, stable
from .validate import validate_annotation, validate_claim

TRACKED = (db.companies, db.people, db.sources, db.claims, db.evidence)


def counts(conn):
    return {t.name: conn.scalar(select(func.count()).select_from(t)) for t in TRACKED}


def save(conn, table, **values):
    return conn.execute(
        insert(table)
        .values(**values)
        .on_conflict_do_nothing(index_elements=[table.c.id])
        .returning(table.c.id)
    ).scalar_one_or_none()


def commit_findings(
    source,
    transcript,
    findings,
    annotations,
    run_id,
    provenance,
    *,
    fail_after_source=False,
):
    validated = [(claim, validate_claim(claim, transcript)) for claim in findings]
    for claim, _ in validated:
        annotation = annotations.get(digest(claim.model_dump()))
        if annotation:
            validate_annotation(annotation, claim)
    with db.engine.begin() as conn:
        conn.execute(text("SELECT pg_advisory_xact_lock(91827461)"))
        before = counts(conn)
        save(conn, db.sources, **source, run_id=run_id)
        if fail_after_source:
            raise RuntimeError("Injected interruption before findings")
        claim_ids, new_entities = [], set()
        for claim, locators in validated:
            participants = []
            for p in claim.participants:
                table = db.companies if p.kind == "company" else db.people
                entity_id = stable(p.kind, transcript.external_id, p.name.casefold())
                values = dict(
                    id=entity_id,
                    name=p.name,
                    identity={
                        "status": "episode_scoped_unresolved",
                        "rationale": "Quoted mention only; global identity and external identifiers unverified.",
                        "source_id": source["id"],
                        "run_id": run_id,
                    },
                )
                if p.kind == "company":
                    values["field_evidence"] = {}
                created = save(conn, table, **values)
                if created and p.kind == "company":
                    new_entities.add(entity_id)
                participants.append(dict(p.model_dump(), id=entity_id))
            # Include every participant and the claimant label. No semantic auto-merging.
            claim_id = stable(
                "claim-v2",
                claim.text,
                participants,
                transcript.external_id,
                claim.speaker_label,
            )
            key = digest(claim.model_dump())
            annotation = annotations.get(key)
            extraction = dict(
                provenance,
                predicate=claim.predicate,
                context=claim.context,
                rationale=claim.rationale,
                speaker_label=claim.speaker_label,
                anchor_segment_id=claim.anchor_segment_id,
                assertion_status="attributed_not_verified",
            )
            annotation_data = (
                dict(annotation.model_dump(), **provenance) if annotation else None
            )
            created = save(
                conn,
                db.claims,
                id=claim_id,
                text=claim.text,
                participants=participants,
                status="needs_review",
                extraction=extraction,
                annotation=annotation_data,
                run_id=run_id,
            )
            # A previously unclassified claim can gain classification; don't overwrite existing decisions.
            if not created and annotation_data:
                conn.execute(
                    db.claims.update()
                    .where(db.claims.c.id == claim_id, db.claims.c.annotation.is_(None))
                    .values(annotation=annotation_data)
                )
            for q, locator in zip(claim.quotes, locators):
                segment = next(s for s in transcript.segments if s.id == q.segment_id)
                save(
                    conn,
                    db.evidence,
                    id=stable("evidence-v2", claim_id, source["id"], locator, q.role),
                    claim_id=claim_id,
                    source_id=source["id"],
                    locators=[locator],
                    quote=q.quote,
                    speaker_label=segment.speaker,
                    role=q.role,
                )
            claim_ids.append(claim_id)
        after = counts(conn)
        result = {
            "status": "completed",
            "source_id": source["id"],
            "claim_ids": sorted(set(claim_ids)),
            "added_entity_ids": sorted(new_entities),
            "before": before,
            "after": after,
            "delta": {k: after[k] - before[k] for k in before},
        }
        from .run_state import now

        conn.execute(
            db.runs.update()
            .where(db.runs.c.id == run_id)
            .values(status="completed", result=result, finished_at=now(), error=None)
        )
        return result
