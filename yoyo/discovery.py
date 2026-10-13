"""Coverage is a database snapshot; search history is persisted in existing run JSON."""

from collections import Counter
from datetime import date
from sqlalchemy import select
from . import apple, db
from .artifacts import digest, read_json, store_json
from .commit import counts
from .run_state import now


def coverage_snapshot():
    with db.engine.connect() as conn:
        sectors = Counter(conn.scalars(select(db.companies.c.sector_id)))
        episodes = list(
            conn.scalars(
                select(db.sources.c.external_id).where(
                    db.sources.c.kind == "transcript"
                )
            )
        )
        history = (
            conn.execute(
                select(
                    db.runs.c.id, db.runs.c.input, db.runs.c.progress, db.runs.c.status
                )
                .where(db.runs.c.input["kind"].astext == "discovery-agent")
                .order_by(db.runs.c.created_at.desc())
                .limit(30)
            )
            .mappings()
            .all()
        )
        return {
            "counts": counts(conn),
            "sector_counts": {k or "unknown": v for k, v in sectors.items()},
            "processed_episode_ids": sorted(set(episodes)),
            "search_history": [
                {
                    "run_id": r["id"],
                    "status": r["status"],
                    "searches": r["progress"].get("searches", {}),
                }
                for r in history
            ],
        }


def current_availability(result):
    known = set(coverage_snapshot()["processed_episode_ids"])
    return dict(
        result,
        episodes=[
            dict(e, already_processed=e["episodeId"] in known)
            for e in result["episodes"]
        ],
        exhausted=not any(e["episodeId"] not in known for e in result["episodes"]),
    )


def search_episodes(state, query, reason, limit=8):
    if not reason.strip():
        raise ValueError("Explain the coverage gap or refresh")
    key = digest(
        [
            query.strip().casefold(),
            limit,
            state.inputs.get("after"),
            state.inputs.get("before"),
        ]
    )
    searches = state.progress.setdefault("searches", {})
    if key in searches and searches[key].get("artifact"):
        return dict(
            current_availability(read_json(searches[key]["artifact"])), reused=True
        )
    refresh = state.inputs["search_date"]
    for run in coverage_snapshot()["search_history"]:
        old = run["searches"].get(key)
        if old and old.get("search_date") == refresh and old.get("artifact"):
            searches[key] = dict(old, reused_from_run=run["run_id"])
            state.save()
            return dict(current_availability(read_json(old["artifact"])), reused=True)
    searches[key] = {
        "query": query,
        "reason": reason,
        "search_date": refresh,
        "status": "submitted",
    }
    state.save()
    episodes = apple.search(query, limit, refresh=refresh)
    after, before = state.inputs.get("after"), state.inputs.get("before")
    episodes = [
        e
        for e in episodes
        if (not after or (e.get("releaseDate") or "")[:10] >= after)
        and (not before or (e.get("releaseDate") or "9999")[:10] <= before)
    ]
    known = set(coverage_snapshot()["processed_episode_ids"])
    result = {
        "episodes": [
            dict(e, already_processed=e["episodeId"] in known) for e in episodes
        ],
        "query": query,
        "retrieved_at": now().isoformat(),
        "exhausted": not any(e["episodeId"] not in known for e in episodes),
    }
    searches[key].update(
        status="completed",
        artifact=store_json(result),
        count=len(episodes),
        exhausted=result["exhausted"],
    )
    state.save()
    return result


def validate_window(after, before):
    for value in (after, before):
        if value:
            date.fromisoformat(value)
    if after and before and after > before:
        raise ValueError("after must precede before")
