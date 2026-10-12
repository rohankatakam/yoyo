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
    resolved_companies,
    before_counts=None,
    added_company_ids=(),
    fail_after_source=False,
):
    validated = [(claim, validate_claim(claim, transcript)) for claim in findings]
    for claim, _ in validated:
        annotation = annotations.get(digest(claim.model_dump()))
        if annotation:
            validate_annotation(annotation, claim)
    with db.engine.begin() as conn:
        conn.execute(text("SELECT pg_advisory_xact_lock(91827461)"))
        before = before_counts or counts(conn)
        save(conn, db.sources, **source, run_id=run_id)
        if fail_after_source:
            raise RuntimeError("Injected interruption before findings")
        claim_ids, new_entities = [], set(added_company_ids)
        for claim, locators in validated:
            participants = []
            for p in claim.participants:
                if p.kind == "company":
                    entity_id = resolved_companies.get(p.name.casefold())
                    entity = (
                        conn.execute(
                            select(db.companies).where(db.companies.c.id == entity_id)
                        )
                        .mappings()
                        .first()
                    )
                    if (
                        not entity
                        or entity["identity"].get("status") != "source_verified"
                    ):
                        raise ValueError(
                            "Company must pass lookup/resolve/enrichment before claim commit"
                        )
                else:
                    entity_id = stable(
                        "person", transcript.external_id, p.name.casefold()
                    )
                    save(
                        conn,
                        db.people,
                        id=entity_id,
                        name=p.name,
                        identity={
                            "status": "episode_scoped_unresolved",
                            "source_id": source["id"],
                        },
                    )
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
