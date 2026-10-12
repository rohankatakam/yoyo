"""Initial evidence ledger."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "runs",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("status", sa.String, nullable=False),
        sa.Column("origin", sa.Text, nullable=False),
        sa.Column("operation_key", sa.String, nullable=False),
        sa.Column("trace_id", sa.String),
        sa.Column("trace_url", sa.Text),
        sa.Column("trace_status", sa.String, nullable=False),
        sa.Column("result", JSONB),
        sa.Column("error", sa.Text),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    for table in ("companies", "people"):
        cols = [
            sa.Column("id", sa.String, primary_key=True),
            sa.Column("name", sa.String, nullable=False),
            sa.Column("identity_status", sa.String, nullable=False),
        ]
        if table == "companies":
            cols += [
                sa.Column("domain", sa.String),
                sa.Column("linkedin_url", sa.String),
            ]
        op.create_table(
            table,
            *cols,
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
        )
    op.create_table(
        "sources",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("episode_id", sa.String, nullable=False),
        sa.Column("title", sa.String, nullable=False),
        sa.Column("url", sa.Text),
        sa.Column("sha256", sa.String, unique=True, nullable=False),
        sa.Column("parent_sha256", sa.String, nullable=False),
        sa.Column("artifact_name", sa.String, nullable=False),
        sa.Column("provenance", JSONB, nullable=False),
        sa.Column("run_id", sa.String, sa.ForeignKey("runs.id"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_table(
        "passages",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("source_id", sa.String, sa.ForeignKey("sources.id"), nullable=False),
        sa.Column("segment_index", sa.Integer, nullable=False),
        sa.Column("start", sa.Float, nullable=False),
        sa.Column("end", sa.Float, nullable=False),
        sa.Column("speaker_label", sa.String),
        sa.Column("text", sa.Text, nullable=False),
        sa.UniqueConstraint("source_id", "segment_index"),
    )
    op.create_table(
        "proposals",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("run_id", sa.String, sa.ForeignKey("runs.id"), nullable=False),
        sa.Column("payload", JSONB, nullable=False),
        sa.Column("status", sa.String, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_table(
        "claims",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column(
            "company_id", sa.String, sa.ForeignKey("companies.id"), nullable=False
        ),
        sa.Column("person_id", sa.String, sa.ForeignKey("people.id")),
        sa.Column("predicate", sa.String, nullable=False),
        sa.Column("statement", sa.Text, nullable=False),
        sa.Column("assertion_status", sa.String, nullable=False),
        sa.Column("review_status", sa.String, nullable=False),
        sa.Column(
            "proposal_id", sa.String, sa.ForeignKey("proposals.id"), nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_table(
        "evidence",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("claim_id", sa.String, sa.ForeignKey("claims.id"), nullable=False),
        sa.Column(
            "passage_id", sa.String, sa.ForeignKey("passages.id"), nullable=False
        ),
        sa.Column("quote", sa.Text, nullable=False),
        sa.Column("speaker_label", sa.String),
        sa.Column("attribution_status", sa.String, nullable=False),
        sa.UniqueConstraint("claim_id", "passage_id", "quote"),
    )
    op.create_table(
        "identity_decisions",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column(
            "company_id", sa.String, sa.ForeignKey("companies.id"), nullable=False
        ),
        sa.Column("source_id", sa.String, sa.ForeignKey("sources.id"), nullable=False),
        sa.Column("run_id", sa.String, sa.ForeignKey("runs.id"), nullable=False),
        sa.Column("decision", sa.String, nullable=False),
        sa.Column("rationale", sa.Text, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade():
    for table in (
        "identity_decisions",
        "evidence",
        "claims",
        "proposals",
        "passages",
        "sources",
        "people",
        "companies",
        "runs",
    ):
        op.drop_table(table)
