from sqlalchemy import (
    create_engine,
    MetaData,
    Table,
    Column,
    String,
    Text,
    Float,
    Integer,
    ForeignKey,
    UniqueConstraint,
    DateTime,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from .config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)
metadata = MetaData()


def ident():
    return Column("id", String, primary_key=True)


def stamp():
    return Column(
        "created_at", DateTime(timezone=True), nullable=False, server_default=func.now()
    )


runs = Table(
    "runs",
    metadata,
    ident(),
    Column("status", String, nullable=False),
    Column("origin", Text, nullable=False),
    Column("operation_key", String, nullable=False),
    Column("trace_id", String),
    Column("trace_url", Text),
    Column("trace_status", String, nullable=False),
    Column("result", JSONB),
    Column("error", Text),
    stamp(),
)
companies = Table(
    "companies",
    metadata,
    ident(),
    Column("name", String, nullable=False),
    Column("identity_status", String, nullable=False),
    Column("domain", String),
    Column("linkedin_url", String),
    stamp(),
)
people = Table(
    "people",
    metadata,
    ident(),
    Column("name", String, nullable=False),
    Column("identity_status", String, nullable=False),
    stamp(),
)
sources = Table(
    "sources",
    metadata,
    ident(),
    Column("episode_id", String, nullable=False),
    Column("title", String, nullable=False),
    Column("url", Text),
    Column("sha256", String, nullable=False, unique=True),
    Column("parent_sha256", String, nullable=False),
    Column("artifact_name", String, nullable=False),
    Column("provenance", JSONB, nullable=False),
    Column("run_id", ForeignKey("runs.id"), nullable=False),
    stamp(),
)
passages = Table(
    "passages",
    metadata,
    ident(),
    Column("source_id", ForeignKey("sources.id"), nullable=False),
    Column("segment_index", Integer, nullable=False),
    Column("start", Float, nullable=False),
    Column("end", Float, nullable=False),
    Column("speaker_label", String),
    Column("text", Text, nullable=False),
    UniqueConstraint("source_id", "segment_index"),
)
proposals = Table(
    "proposals",
    metadata,
    ident(),
    Column("run_id", ForeignKey("runs.id"), nullable=False),
    Column("payload", JSONB, nullable=False),
    Column("status", String, nullable=False),
    stamp(),
)
claims = Table(
    "claims",
    metadata,
    ident(),
    Column("company_id", ForeignKey("companies.id"), nullable=False),
    Column("person_id", ForeignKey("people.id")),
    Column("predicate", String, nullable=False),
    Column("statement", Text, nullable=False),
    Column("assertion_status", String, nullable=False),
    Column("review_status", String, nullable=False),
    Column("proposal_id", ForeignKey("proposals.id"), nullable=False),
    stamp(),
)
evidence = Table(
    "evidence",
    metadata,
    ident(),
    Column("claim_id", ForeignKey("claims.id"), nullable=False),
    Column("passage_id", ForeignKey("passages.id"), nullable=False),
    Column("quote", Text, nullable=False),
    Column("speaker_label", String),
    Column("attribution_status", String, nullable=False),
    UniqueConstraint("claim_id", "passage_id", "quote"),
)
identity_decisions = Table(
    "identity_decisions",
    metadata,
    ident(),
    Column("company_id", ForeignKey("companies.id"), nullable=False),
    Column("source_id", ForeignKey("sources.id"), nullable=False),
    Column("run_id", ForeignKey("runs.id"), nullable=False),
    Column("decision", String, nullable=False),
    Column("rationale", Text, nullable=False),
    stamp(),
)
