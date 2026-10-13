"""Exercise replay and a restart after acquisition using actual completed pilot inputs."""

import argparse
import json
from pathlib import Path
from sqlalchemy import select
from yoyo import db
from yoyo import ingest as ingestion
from yoyo.commit import counts


def snapshot():
    with db.engine.connect() as conn:
        return counts(conn)


def check(mode):
    rows = json.loads(Path("artifacts/pilot-v1-results.json").read_text())
    before = snapshot()
    if mode == "repeat":
        results = [
            ingestion.ingest(r["episode"]["itunesUrl"], max_calls=180, seconds=2400)
            for r in rows
        ]
        assert all(r["reused"] for r in results)
        assert before == snapshot()
        result = {
            "episodes": len(results),
            "reused": len(results),
            "before": before,
            "after": snapshot(),
        }
    else:
        url = rows[0]["episode"]["itunesUrl"]
        if mode == "interrupt":

            def stop(*args, **kwargs):
                raise RuntimeError(
                    "Injected stop after transcript acquisition, before pipeline"
                )

            ingestion.process = stop
            try:
                ingestion.ingest(url, max_calls=180, seconds=2401)
            except RuntimeError as exc:
                assert "Injected stop" in str(exc)
            else:
                raise AssertionError("Interruption did not execute")
        else:
            recovered = ingestion.ingest(url, max_calls=180, seconds=2401)
            assert recovered["run_id"] == rows[0]["result"]["run_id"]
        with db.engine.connect() as conn:
            run = (
                conn.execute(
                    select(db.runs).where(
                        db.runs.c.input["kind"].astext == "episode-url",
                        db.runs.c.input["episode_id"].astext
                        == rows[0]["episode"]["episodeId"],
                        db.runs.c.input["seconds"].as_integer() == 2401,
                    )
                )
                .mappings()
                .one()
            )
        assert "metadata" in run["progress"] and "transcript" in run["progress"]
        assert before == snapshot()
        result = {
            "run_id": run["id"],
            "status": run["status"],
            "before": before,
            "after": snapshot(),
            "external_calls": len(run["progress"]["budget"]["calls"]),
        }
        assert run["status"] == ("failed" if mode == "interrupt" else "completed")
    Path(f"artifacts/pilot-{mode}.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["repeat", "interrupt", "resume"])
    check(parser.parse_args().mode)
