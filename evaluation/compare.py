"""Run real resolver calls against two isolated, initially empty PostgreSQL schemas."""

import argparse
import json
import time
from pathlib import Path
from sqlalchemy import text, select
from yoyo import db
from yoyo.artifacts import digest, stable, store_json
from yoyo.config import settings
from yoyo.resolution.contracts import Mention
from yoyo.resolution.ledger import Ledger
from yoyo.resolution.gate import Gate
from yoyo.resolution.providers import Research
from yoyo.telemetry import Trace


def experiment(cases, mode, label):
    schema = "eval_" + digest([label, mode])[:12]
    run_id = stable("resolution-eval", label, mode)
    ledger = Ledger(schema=schema, run_id=run_id)
    with db.engine.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))
        ledger.metadata.create_all(conn)
        table = ledger.tables["runs"]
        previous = (
            conn.execute(select(table).where(table.c.id == run_id)).mappings().first()
        )
        if not previous:
            assert not conn.scalar(select(ledger.tables["companies"].c.id).limit(1))
            conn.execute(
                table.insert().values(
                    id=run_id,
                    status="running",
                    input={"mode": mode, "cases_hash": digest(cases)},
                    operation_key=label,
                    progress={},
                    trace_status="pending",
                )
            )
        elif previous["input"]["cases_hash"] != digest(cases):
            raise ValueError("Experiment inputs changed; choose a fresh label")
    path = settings.artifact_dir / f"{label}-{mode}.json"
    rows = json.loads(path.read_text())["rows"] if path.exists() else []
    trace = Trace(run_id, {"experiment": label, "mode": mode, "schema": schema})
    research = Research(trace)
    gate = Gate(ledger, research, mode)
    try:
        for case in cases[len(rows) :]:
            started = time.monotonic()
            entry = gate.resolve(Mention.model_validate(case["mention"]))
            entry.update(
                case_id=case["id"],
                expected=case["expected"],
                group=case.get("group"),
                case_seconds=time.monotonic() - started,
            )
            rows.append(entry)
            path.write_text(
                json.dumps({"schema": schema, "run_id": run_id, "rows": rows}, indent=2)
            )
            with db.engine.begin() as conn:
                conn.execute(
                    table.update()
                    .where(table.c.id == run_id)
                    .values(progress={"results": store_json(rows)})
                )
            print(
                mode,
                case["id"],
                case["mention"]["name"],
                entry["decision"]["outcome"],
                flush=True,
            )
        result = {
            "schema": schema,
            "run_id": run_id,
            "rows": rows,
            "companies": ledger.companies(),
        }
        path.write_text(json.dumps(result, indent=2, default=str))
        trace.finish({"cases": len(rows), "companies": len(result["companies"])})
        with db.engine.begin() as conn:
            conn.execute(
                table.update()
                .where(table.c.id == run_id)
                .values(
                    status="completed",
                    result={"cases": len(rows), "companies": len(result["companies"])},
                    trace_id=trace.id,
                    trace_url=trace.url,
                    trace_status=trace.status,
                )
            )
        return result
    except Exception as exc:
        trace.finish(error=str(exc))
        with db.engine.begin() as conn:
            conn.execute(
                table.update()
                .where(table.c.id == run_id)
                .values(status="failed", error=str(exc))
            )
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("cases", type=Path)
    parser.add_argument("--label", required=True)
    parser.add_argument("--mode", choices=["lexical", "hybrid", "both"], default="both")
    args = parser.parse_args()
    raw = args.cases.read_text()
    cases = (
        [json.loads(line) for line in raw.splitlines() if line.strip()]
        if args.cases.suffix == ".jsonl"
        else json.loads(raw)
    )
    for mode in ["lexical", "hybrid"] if args.mode == "both" else [args.mode]:
        experiment(cases, mode, args.label)
