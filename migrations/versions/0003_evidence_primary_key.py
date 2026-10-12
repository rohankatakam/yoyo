"""Use the deterministic evidence UUID; avoid indexing unbounded quote text."""

from alembic import op
from sqlalchemy import inspect

revision = "0003"
down_revision = "0002"
branch_labels = depends_on = None


def upgrade():
    for constraint in inspect(op.get_bind()).get_unique_constraints("evidence"):
        if constraint["column_names"] == ["claim_id", "source_id", "locators", "quote"]:
            op.drop_constraint(constraint["name"], "evidence", type_="unique")


def downgrade():
    op.create_unique_constraint(
        "evidence_claim_id_source_id_locators_quote_key",
        "evidence",
        ["claim_id", "source_id", "locators", "quote"],
    )
