"""Backfill six typed tables, verify, then retire v1 in one Postgres transaction."""

from alembic import op
import sqlalchemy as sa
from migrations.schema_v2 import make_metadata
from migrations.backfill_v2 import convert

revision = "0002"
down_revision = "0001"
branch_labels = depends_on = None
OLD = (
    "runs",
    "companies",
    "people",
    "sources",
    "passages",
    "proposals",
    "claims",
    "evidence",
    "identity_decisions",
)


def upgrade():
    conn = op.get_bind()
    current = conn.scalar(sa.text("SELECT current_schema()"))
    staging = current + "_yoyo_v2"
    quote = conn.dialect.identifier_preparer.quote
    conn.execute(sa.text("SELECT pg_advisory_xact_lock(91827461)"))
    old = {
        name: [
            dict(row)
            for row in conn.execute(sa.text(f"SELECT * FROM {quote(name)}")).mappings()
        ]
        for name in OLD
    }
    data = convert(old)
    conn.execute(sa.text(f"CREATE SCHEMA {quote(staging)}"))
    metadata = make_metadata(staging)
    metadata.create_all(conn)
    for name, rows in data.items():
        table = metadata.tables[f"{staging}.{name}"]
        if rows:
            conn.execute(table.insert(), rows)
        saved = list(conn.execute(sa.select(table)).mappings())
        assert {str(x["id"]) for x in saved} == {x["id"] for x in rows}, (
            f"ID mismatch: {name}"
        )
    evidence = metadata.tables[f"{staging}.evidence"]
    assert sorted(conn.scalars(sa.select(evidence.c.quote))) == sorted(
        x["quote"] for x in old["evidence"]
    )
    sources = metadata.tables[f"{staging}.sources"]
    assert sum(
        len(x["segments"]) for x in conn.scalars(sa.select(sources.c.content))
    ) == len(old["passages"])
    # No data is retired until the complete backfill and integrity checks succeed.
    for name in (
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
        op.drop_table(name)
    for name in data:
        conn.execute(
            sa.text(
                f"ALTER TABLE {quote(staging)}.{quote(name)} SET SCHEMA {quote(current)}"
            )
        )
    conn.execute(sa.text(f"DROP SCHEMA {quote(staging)}"))


def downgrade():
    raise RuntimeError(
        "Restore the pre-migration pg_dump backup; v2 can represent data that v1 cannot."
    )
