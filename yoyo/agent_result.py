"""Result IDs come from committed records, never the agent's final prose."""

from datetime import datetime
from sqlalchemy import select
from . import db
from .budget import usage_summary
from .discovery import coverage_snapshot


def run_result(state, status, summary=""):
    jobs = state.progress.get("episodes", {})
    child_ids = [j.get("result", {}).get("run_id") for j in jobs.values()]
    child_ids = [i for i in child_ids if i] + state.progress.get("child_run_ids", [])
    with db.engine.connect() as conn:
        children = (
            conn.execute(select(db.runs).where(db.runs.c.id.in_(child_ids)))
            .mappings()
            .all()
        )
        claim_ids = sorted(
            {i for r in children for i in (r["result"] or {}).get("claim_ids", [])}
        )
        started = datetime.fromisoformat(state.progress["started_at"])
        fresh = [r for r in children if r["created_at"] >= started]
        fresh_ids = [r["id"] for r in fresh]
        company_ids = {
            v["company_id"]
            for r in fresh
            for v in r["progress"].get("resolution", {}).values()
            if v.get("company_id")
        }
        # A company can commit before a claim or a run checkpoint. Keep it attributable.
        company_ids.update(
            conn.scalars(
                select(db.companies.c.id).where(
                    db.companies.c.identity["created_run_id"].astext.in_(fresh_ids)
                )
            )
        )
        new_ids = set(
            conn.scalars(
                select(db.companies.c.id).where(
                    db.companies.c.id.in_(company_ids),
                    db.companies.c.created_at >= started,
                )
            )
        )
    unresolved = [
        {"run_id": r["id"], "mention_key": k}
        for r in children
        for k, v in r["progress"].get("resolution", {}).items()
        if v.get("decision", {}).get("outcome") == "UNRESOLVED"
    ]
    after = coverage_snapshot()["counts"]
    before = state.progress["coverage_before"]["counts"]
    return {
        "status": status,
        "run_id": state.id,
        "added_entity_ids": sorted(new_ids),
        "updated_entity_ids": sorted(company_ids - new_ids),
        "claim_ids": claim_ids,
        "unresolved_ids": unresolved,
        "pending_job_ids": [k for k, j in jobs.items() if j["status"] != "completed"],
        "before": before,
        "after": after,
        "coverage_delta": {k: after[k] - before[k] for k in before},
        "budget": state.progress.get("budget"),
        "cost": usage_summary(state.progress.get("budget", {})),
        "summary": summary,
        "review_status": "pending_human_review",
    }
