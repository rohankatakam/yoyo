"""Replay saved extraction through the new gates in an isolated PostgreSQL schema."""

import argparse
import json
from datetime import datetime
from pathlib import Path
from sqlalchemy import create_engine, select, text
from yoyo import db
from yoyo.artifacts import digest, read_json
from yoyo.claim_models import Candidate, Annotation
from yoyo.commit import commit_findings, counts
from yoyo.config import settings
from yoyo.resolution.findings import resolve_findings
from yoyo.run_state import State
from yoyo.telemetry import Trace
from yoyo.transcripts.models import Transcript
from yoyo.verify_claims import verify_findings


def replay(source_path, claims_path, run_id, label):
    source = json.loads(source_path.read_text())
    claims = [Candidate.model_validate(c) for c in json.loads(claims_path.read_text())]
    annotations = {}
    with db.engine.connect() as conn:
        original = (
            conn.execute(select(db.runs).where(db.runs.c.id == run_id)).mappings().one()
        )
    for name, operation in original["progress"]["operations"].items():
        if name.startswith("annotate-") and operation.get("parsed"):
            for item in read_json(operation["parsed"])["claims"]:
                annotations[item["claim_key"]] = Annotation.model_validate(
                    item["annotation"]
                )
    schema = "eval_" + digest(["replay", label])[:12]
    with db.engine.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))
    db.engine = create_engine(
        settings.database_url, connect_args={"options": f"-csearch_path={schema}"}
    )
    db.metadata.create_all(db.engine)
    source.pop("run_id", None)
    for field in ("published_at", "retrieved_at"):
        if source.get(field):
            source[field] = datetime.fromisoformat(source[field])
    state = State(
        {
            "pipeline": "saved-extraction-packets-v1",
            "source_id": source["id"],
            "claims_hash": digest([c.model_dump() for c in claims]),
            "label": label,
        }
    )
    trace = Trace(state.id, {"evaluation": label, "schema": schema})
    try:
        if state.result:
            print(json.dumps(state.result, indent=2))
            return
        if "ledger_before" not in state.progress:
            with db.engine.connect() as conn:
                state.progress["ledger_before"] = counts(conn)
            state.save()
        verified = verify_findings(claims, source, state, trace)
        kept, labels, ids, added = resolve_findings(
            source, verified, annotations, state, trace, "lexical"
        )
        result = commit_findings(
            source,
            Transcript.model_validate(source["content"]),
            kept,
            labels,
            state.id,
            {
                "model": settings.model,
                "run_id": state.id,
                "validation": "model_entailment_and_identity",
            },
            resolved_companies=ids,
            before_counts=state.progress["ledger_before"],
            added_company_ids=added,
        )
        trace.finish(result)
        state.save(trace_id=trace.id, trace_url=trace.url, trace_status=trace.status)
        output = {
            "schema": schema,
            "run_id": state.id,
            "trace_url": trace.url,
            "extracted": len(claims),
            "entailed": len(verified),
            "result": result,
        }
        Path(f"artifacts/{label}.json").write_text(json.dumps(output, indent=2))
        print(json.dumps(output, indent=2))
    except Exception as exc:
        trace.finish(error=str(exc))
        state.save(status="failed", error=str(exc))
        raise
    finally:
        state.close()
        db.engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("claims", type=Path)
    parser.add_argument("--original-run", required=True)
    parser.add_argument("--label", required=True)
    args = parser.parse_args()
    replay(args.source, args.claims, args.original_run, args.label)
