"""Freeze a saved run for paired packet evaluations; never alter its ledger."""

import argparse
import json
from pathlib import Path
from sqlalchemy import select
from yoyo import db
from yoyo.artifacts import read_json
from yoyo.resolution.packets import episode_context


def prepare(run_id, cases_path):
    with db.engine.connect() as conn:
        run = (
            conn.execute(select(db.runs).where(db.runs.c.id == run_id)).mappings().one()
        )
        source = dict(
            conn.execute(
                select(db.sources).where(db.sources.c.id == run["input"]["source_id"])
            )
            .mappings()
            .one()
        )
    Path("artifacts/packet-eval-source.json").write_text(
        json.dumps(source, default=str)
    )
    Path("artifacts/packet-eval-claims.json").write_text(
        json.dumps(read_json(run["progress"]["accepted"]))
    )
    cases = [
        json.loads(line) for line in cases_path.read_text().splitlines() if line.strip()
    ]
    for case in cases:
        mention = case["mention"]
        if mention["source_id"] != source["id"]:
            continue
        selected = set()
        segments = source["content"]["segments"]
        found = [
            i
            for i, s in enumerate(segments)
            if mention["name"].casefold() in s["text"].casefold()
        ][:3]
        for i in found:
            selected.update(range(max(0, i - 1), min(len(segments), i + 2)))
        mention["transcript_evidence"] = [
            {k: s.get(k) for k in ("id", "text", "speaker", "start", "end")}
            for i, s in enumerate(segments)
            if i in selected
        ]
        if found:
            mention["context"] = "Target company mention: " + mention["name"]
    Path("artifacts/packet-no-notes-cases.json").write_text(json.dumps(cases, indent=2))
    for case in cases:
        if case["mention"]["source_id"] == source["id"]:
            case["mention"]["episode_context"] = episode_context(
                source, case["mention"]["name"]
            )
    Path("artifacts/packet-notes-cases.json").write_text(json.dumps(cases, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("run_id")
    parser.add_argument("--cases", type=Path, default=Path("evaluation/cases.jsonl"))
    args = parser.parse_args()
    prepare(args.run_id, args.cases)
