"""The company write boundary; research is finished before acquiring the write lock."""

from datetime import datetime, UTC
from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from .. import db
from ..schema import make_metadata
from ..artifacts import stable, digest, store_json


class Ledger:
    def __init__(self, engine=None, schema=None, run_id=None):
        self.engine = engine or db.engine
        self.metadata = make_metadata(schema)
        self.tables = {t.name: t for t in self.metadata.tables.values()}
        self.run_id = run_id

    def companies(self):
        with self.engine.connect() as conn:
            return [
                dict(r)
                for r in conn.execute(
                    select(self.tables["companies"]).order_by(
                        self.tables["companies"].c.name
                    )
                ).mappings()
            ]

    def alias(self, company_id, mention, decision):
        table = self.tables["companies"]
        with self.engine.begin() as conn:
            row = (
                conn.execute(
                    select(table).where(table.c.id == company_id).with_for_update()
                )
                .mappings()
                .one()
            )
            identity = dict(row["identity"])
            identity["aliases"] = sorted(
                set(identity.get("aliases", []) + [mention.name])
            )
            identity.setdefault("decisions", []).append(
                {"mention": mention.model_dump(), **decision.model_dump()}
            )
            conn.execute(
                table.update().where(table.c.id == company_id).values(identity=identity)
            )
        return company_id

    def create(self, record, pages, mention, decision):
        company_id = stable(
            "canonical-company-v1",
            record["name"].casefold(),
            record["profile"].get("domain"),
            record["profile"].get("linkedin_url"),
        )
        ids = [stable("web-source", digest(page)) for page in pages]
        identity = {
            "status": "source_verified",
            "aliases": [mention.name],
            "citations": [
                dict(c, source_id=ids[c["source"]])
                for c in record["identity_citations"]
            ],
            "decisions": [{"mention": mention.model_dump(), **decision.model_dump()}],
        }
        field_evidence = {
            field: [dict(c, source_id=ids[c["source"]]) for c in cites]
            for field, cites in record["evidence"].items()
        }
        with self.engine.begin() as conn:
            conn.execute(text("SELECT pg_advisory_xact_lock(91827461)"))
            table = self.tables["companies"]
            existing = (
                conn.execute(select(table).where(table.c.id == company_id))
                .mappings()
                .first()
            )
            if existing:
                # Only replay the same saved mention; equal names/URLs are not a match decision.
                if any(
                    d.get("mention") == mention.model_dump()
                    for d in existing["identity"].get("decisions", [])
                ):
                    return company_id
                raise RuntimeError(
                    "Company key already exists; resolve against fresh candidates"
                )
            # A concurrent conflicting identity requires re-resolution, not an automatic merge.
            for row in conn.execute(select(table)).mappings():
                shared = any(
                    record["profile"].get(k) and record["profile"][k] == row[k]
                    for k in ("domain", "linkedin_url")
                )
                if shared and row["name"].casefold() == record["name"].casefold():
                    raise RuntimeError(
                        "Ledger identity changed during research; resolve against fresh candidates"
                    )
            for source_id, page in zip(ids, pages):
                source = dict(
                    id=source_id,
                    kind="web",
                    provider="exa",
                    external_id=page["url"],
                    title=page["title"],
                    url=page["url"],
                    retrieved_at=datetime.now(UTC),
                    content={"text": page["text"]},
                    metadata={"published_at": page["published_at"]},
                    content_hash=digest(page),
                    version_hash=digest(page),
                    raw_artifact=store_json(page),
                    run_id=self.run_id,
                )
                conn.execute(
                    insert(self.tables["sources"])
                    .values(**source)
                    .on_conflict_do_nothing()
                )
            conn.execute(
                table.insert().values(
                    id=company_id,
                    name=record["name"],
                    identity=identity,
                    field_evidence=field_evidence,
                    **record["profile"],
                )
            )
        return company_id
