"""Typed tools close over harness-owned run, budget and credentials."""

from langchain.tools import tool
from .artifacts import digest
from .budget import BudgetExhausted
from .discovery import coverage_snapshot, search_episodes
from .ingest import ingest
from .apple import episode_id


def build_tools(state, trace):
    @tool
    def coverage() -> dict:
        """Read saved company/episode coverage and dated prior searches."""
        return coverage_snapshot()

    @tool
    def discover(query: str, reason: str, limit: int = 8) -> dict:
        """Search Apple episodes. Explain the gap/refresh; avoid exhausted searches."""
        if not 1 <= limit <= 12:
            raise ValueError("limit must be 1–12")
        with trace.span(
            "discover", {"query": query, "reason": reason, "limit": limit}
        ) as output:
            result = search_episodes(state, query, reason, limit)
            output.update(result)
            return result

    @tool
    def ingest_episode(url: str) -> dict:
        """Retrieve existing transcript and sequentially verify, resolve, enrich and save."""
        key = episode_id(url)
        jobs = state.progress.setdefault("episodes", {})
        if key in jobs and jobs[key].get("result"):
            return jobs[key]["result"]
        if key not in jobs and len(jobs) >= state.inputs["max_episodes"]:
            raise BudgetExhausted("Episode budget exhausted")
        # Only ingest URLs actually returned by this run's persisted discovery.
        from .artifacts import read_json

        found = [
            e
            for s in state.progress.get("searches", {}).values()
            if s.get("artifact")
            for e in read_json(s["artifact"])["episodes"]
            if e["episodeId"] == key
        ]
        if not found:
            raise ValueError("Discover this episode before ingesting it")
        jobs[key] = {"url": url, "status": "pending", "operation_key": digest(url)}
        state.save()
        result = ingest(
            url, max_calls=state.inputs["max_calls"], seconds=state.inputs["seconds"]
        )
        jobs[key].update(status=result["status"], result=result)
        state.save()
        # Do not send large budgets or evidence back through the planner model.
        return {
            k: result.get(k)
            for k in ("status", "run_id", "ingestion_run_id", "delta", "reason")
        }

    return [coverage, discover, ingest_episode]
