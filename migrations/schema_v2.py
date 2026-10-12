"""Frozen schema snapshot for migration 0002. Do not edit after release."""

from sqlalchemy import (
    MetaData,
    Table,
    Column as C,
    Text,
    DateTime,
    Numeric,
    ForeignKey,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID, ARRAY


def make_metadata(schema=None):
    m = MetaData(schema=schema)

    def uid(name="id", target=None, nullable=False):
        args = [name, UUID(as_uuid=False)]
        if target:
            args.append(ForeignKey(f"{schema + '.' if schema else ''}{target}.id"))
        return C(*args, primary_key=name == "id", nullable=nullable)

    def created():
        return C(
            "created_at",
            DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
        )

    def doc(name, nullable=False):
        return C(name, JSONB, nullable=nullable)

    Table(
        "runs",
        m,
        uid(),
        C("status", Text, nullable=False),
        doc("input"),
        C("operation_key", Text, nullable=False),
        doc("progress"),
        doc("result", True),
        C("cost", Numeric(14, 6)),
        uid("trace_id", nullable=True),
        C("trace_url", Text),
        C("trace_status", Text, nullable=False),
        C("error", Text),
        created(),
        C("finished_at", DateTime(timezone=True)),
    )
    profile_text = [
        "domain",
        "linkedin_url",
        "sector_id",
        "subsector_id",
        "description",
        "ownership_status",
        "funding_stage",
    ]
    profile_lists = [
        "capabilities",
        "end_markets",
        "headquarters_country_codes",
        "operating_country_codes",
        "operating_region_codes",
    ]
    Table(
        "companies",
        m,
        uid(),
        C("name", Text, nullable=False),
        *[C(n, Text) for n in profile_text],
        *[C(n, ARRAY(Text)) for n in profile_lists],
        doc("industry_codes", True),
        doc("financial_observations", True),
        doc("identity"),
        doc("field_evidence"),
        created(),
    )
    Table(
        "people",
        m,
        uid(),
        C("name", Text, nullable=False),
        C("linkedin_url", Text),
        doc("identity"),
        created(),
    )
    Table(
        "sources",
        m,
        uid(),
        C("kind", Text, nullable=False),
        C("provider", Text, nullable=False),
        C("external_id", Text, nullable=False),
        C("title", Text, nullable=False),
        C("url", Text),
        C("published_at", DateTime(timezone=True)),
        C("retrieved_at", DateTime(timezone=True), nullable=False),
        doc("content"),
        doc("metadata"),
        C("content_hash", Text, nullable=False),
        C("version_hash", Text, nullable=False, unique=True),
        doc("raw_artifact", True),
        uid("run_id", "runs"),
        created(),
    )
    Table(
        "claims",
        m,
        uid(),
        C("text", Text, nullable=False),
        doc("participants"),
        uid("speaker_person_id", "people", True),
        C("status", Text, nullable=False),
        doc("extraction"),
        doc("annotation", True),
        uid("run_id", "runs"),
        created(),
    )
    Table(
        "evidence",
        m,
        uid(),
        uid("claim_id", "claims"),
        uid("source_id", "sources"),
        doc("locators"),
        C("quote", Text, nullable=False),
        C("speaker_label", Text),
        C("role", Text, nullable=False),
        UniqueConstraint("claim_id", "source_id", "locators", "quote"),
    )
    return m
