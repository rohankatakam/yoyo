from uuid import UUID

from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from sqlalchemy import select

from . import db
from .artifacts import read_bytes

app = FastAPI(title="Yoyo evidence ledger")


def rows(conn, query):
    return [dict(r) for r in conn.execute(query).mappings()]


@app.get("/api/health")
def health():
    with db.engine.connect() as conn:
        conn.execute(select(1))
    return {"status": "ok"}


@app.get("/api/companies")
def companies():
    with db.engine.connect() as conn:
        return rows(conn, select(db.companies).order_by(db.companies.c.name))


@app.get("/api/companies/{company_id}")
def company(company_id: UUID):
    with db.engine.connect() as conn:
        entity = (
            conn.execute(
                select(db.companies).where(db.companies.c.id == str(company_id))
            )
            .mappings()
            .first()
        )
        if not entity:
            raise HTTPException(404, "Company not found")
        findings = rows(
            conn,
            select(db.claims).where(
                db.claims.c.participants.contains([{"id": str(company_id)}])
            ),
        )
        for finding in findings:
            finding["evidence"] = rows(
                conn,
                select(
                    db.evidence,
                    db.sources.c.title,
                    db.sources.c.url,
                    db.sources.c.content,
                    db.sources.c.metadata,
                    db.sources.c.raw_artifact,
                )
                .join(db.sources)
                .where(db.evidence.c.claim_id == finding["id"]),
            )
            for evidence in finding["evidence"]:
                segments = {s["id"]: s for s in evidence.pop("content")["segments"]}
                evidence["segments"] = [
                    segments[x["segment_id"]] for x in evidence["locators"]
                ]
        return {**dict(entity), "claims": findings}


@app.get("/api/runs")
def runs():
    with db.engine.connect() as conn:
        return rows(
            conn, select(db.runs).order_by(db.runs.c.created_at.desc()).limit(50)
        )


@app.get("/api/sources")
def sources():
    with db.engine.connect() as conn:
        return rows(
            conn,
            select(
                db.sources.c.id,
                db.sources.c.title,
                db.sources.c.external_id,
                db.sources.c.provider,
                db.sources.c.published_at,
                db.sources.c.url,
            ),
        )


def get_source(source_id):
    with db.engine.connect() as conn:
        source = (
            conn.execute(select(db.sources).where(db.sources.c.id == str(source_id)))
            .mappings()
            .first()
        )
    if not source:
        raise HTTPException(404, "Source not found")
    return dict(source)


@app.get("/api/sources/{source_id}")
def source(source_id: UUID):
    return get_source(source_id)


@app.get("/api/sources/{source_id}/artifact")
def artifact(source_id: UUID):
    source = get_source(source_id)
    if not source["raw_artifact"]:
        raise HTTPException(404, "Raw artifact unavailable")
    try:
        data = read_bytes(source["raw_artifact"])
    except FileNotFoundError:
        raise HTTPException(404, "Artifact missing")
    except ValueError:
        raise HTTPException(409, "Artifact integrity check failed")
    media = (
        "application/xml"
        if source["raw_artifact"]["name"].endswith(".ttml")
        else "application/json"
    )
    return Response(data, media_type=media)
