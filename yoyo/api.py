from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select
from . import db
from .config import settings

app = FastAPI(title="Yoyo evidence ledger")


def rows(conn, query):
    return [dict(r) for r in conn.execute(query).mappings()]


@app.get("/api/health")
def health():
    with db.engine.connect() as conn:
        conn.execute(select(1))
    return {"status": "ok"}


@app.get("/api/companies")
def list_companies():
    with db.engine.connect() as conn:
        return rows(conn, select(db.companies).order_by(db.companies.c.name))


@app.get("/api/companies/{company_id}")
def company(company_id: str):
    with db.engine.connect() as conn:
        entity = (
            conn.execute(select(db.companies).where(db.companies.c.id == company_id))
            .mappings()
            .first()
        )
        if not entity:
            raise HTTPException(404, "Company not found")
        findings = rows(
            conn, select(db.claims).where(db.claims.c.company_id == company_id)
        )
        for finding in findings:
            finding["evidence"] = rows(
                conn,
                select(
                    db.evidence.c.quote,
                    db.evidence.c.attribution_status,
                    db.passages.c.start,
                    db.passages.c.end,
                    db.passages.c.speaker_label,
                    db.passages.c.segment_index,
                    db.sources.c.id.label("source_id"),
                    db.sources.c.title,
                    db.sources.c.url,
                    db.sources.c.sha256,
                    db.sources.c.parent_sha256,
                    db.sources.c.provenance,
                    db.sources.c.run_id,
                )
                .select_from(db.evidence.join(db.passages).join(db.sources))
                .where(db.evidence.c.claim_id == finding["id"]),
            )
        return {
            **dict(entity),
            "claims": findings,
            "identity_decisions": rows(
                conn,
                select(db.identity_decisions).where(
                    db.identity_decisions.c.company_id == company_id
                ),
            ),
        }


@app.get("/api/runs")
def runs():
    with db.engine.connect() as conn:
        return rows(
            conn, select(db.runs).order_by(db.runs.c.created_at.desc()).limit(50)
        )


@app.get("/api/sources/{source_id}/artifact")
def artifact(source_id: str):
    with db.engine.connect() as conn:
        source = (
            conn.execute(select(db.sources).where(db.sources.c.id == source_id))
            .mappings()
            .first()
        )
    if not source:
        raise HTTPException(404, "Source not found")
    path = settings.artifact_dir / source["artifact_name"]
    if not path.exists():
        raise HTTPException(404, "Artifact missing")
    import hashlib

    if hashlib.sha256(path.read_bytes()).hexdigest() != source["sha256"]:
        raise HTTPException(409, "Artifact integrity check failed")
    return FileResponse(path, media_type="application/json", filename=path.name)
