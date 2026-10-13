"""Export real pilot inputs and decisions for independent human review."""

import argparse
import json
from pathlib import Path
from sqlalchemy import select
from yoyo import db
from yoyo.artifacts import read_json


def export(results_path, output):
    output.mkdir(parents=True, exist_ok=True)
    runs = json.loads(results_path.read_text())
    manifest, summary = [], []
    with db.engine.connect() as conn:
        for entry in runs:
            episode, result = entry["episode"], entry.get("result", {})
            if "run_id" not in result:
                continue
            run = (
                conn.execute(select(db.runs).where(db.runs.c.id == result["run_id"]))
                .mappings()
                .one()
            )
            source = (
                conn.execute(
                    select(db.sources).where(db.sources.c.id == result["source_id"])
                )
                .mappings()
                .one()
            )
            claims = (
                conn.execute(
                    select(db.claims).where(db.claims.c.id.in_(result["claim_ids"]))
                )
                .mappings()
                .all()
            )
            proposed = read_json(run["progress"]["accepted"])
            review = []
            for c in claims:
                evidence = (
                    conn.execute(
                        select(db.evidence).where(db.evidence.c.claim_id == c["id"])
                    )
                    .mappings()
                    .all()
                )
                review.append(
                    {
                        "kind": "committed_claim",
                        "claim": dict(c),
                        "evidence": [dict(e) for e in evidence],
                        "human_label": None,
                        "review_notes": "",
                    }
                )
            for key, decision in run["progress"].get("claim_verification", {}).items():
                review.append(
                    {
                        "kind": "verification",
                        "claim_key": key,
                        "decision": decision,
                        "human_label": None,
                        "review_notes": "",
                    }
                )
            for key, decision in run["progress"].get("resolution", {}).items():
                review.append(
                    {
                        "kind": "identity",
                        "mention_key": key,
                        "mention": decision["mention"],
                        "decision": decision["decision"],
                        "company_id": decision["company_id"],
                        "human_label": None,
                        "review_notes": "",
                    }
                )
            review.append(
                {
                    "kind": "missed_claims",
                    "source_id": source["id"],
                    "claims": [],
                    "review_notes": "Review the full transcript to measure recall.",
                }
            )
            eid = episode["episodeId"]
            (output / f"{eid}.jsonl").write_text(
                "\n".join(json.dumps(r, default=str) for r in review) + "\n"
            )
            manifest.append(
                {
                    "episode_id": eid,
                    "niche": episode["niche"],
                    "title": episode["title"],
                    "url": episode["itunesUrl"],
                    "run_id": run["id"],
                    "source_id": source["id"],
                    "source_version_hash": source["version_hash"],
                    "transcript_artifact": source["raw_artifact"],
                    "review_status": "pending_human_review",
                    "review_file": f"{eid}.jsonl",
                }
            )
            verification = run["progress"].get("claim_verification", {})
            supported = sum(
                v["verdict"]["outcome"] == "SUPPORTED" for v in verification.values()
            )
            calls = result.get("budget", {}).get("calls", {})
            summary.append(
                {
                    "episode_id": eid,
                    "niche": episode["niche"],
                    "structurally_accepted": len(proposed),
                    "entailed": supported,
                    "committed": len(claims),
                    "delta": result["delta"],
                    "external_calls": len(calls),
                    "trace_url": result.get("trace_url"),
                }
            )
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (output / "results.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("results", type=Path)
    parser.add_argument("--output", type=Path, default=Path("evaluation/episodes_v1"))
    args = parser.parse_args()
    export(args.results, args.output)
