"""A resumable URL wrapper around the verified extraction pipeline."""

import argparse
import json
from . import apple
from .artifacts import store_json
from .budget import Budget, BudgetExhausted, active, usage_summary
from .config import settings
from .pipeline import process
from .run_state import State, now


def ingest(url, *, max_calls=160, seconds=1800, tracing=True, country="us"):
    eid = apple.episode_id(url)
    state = State(
        {
            "kind": "episode-url",
            "episode_id": eid,
            "country": country,
            "version": "url-v1",
            "max_calls": max_calls,
            "seconds": seconds,
        }
    )
    if state.result:
        state.close()
        return dict(state.result, reused=True)
    budget = active.get() or Budget(state, max_calls, seconds)
    token = active.set(budget)
    try:
        state.save(status="running", error=None)
        if "metadata" not in state.progress:
            state.progress["metadata"] = store_json(apple.metadata(url, country))
            state.save()
        if "transcript" not in state.progress:
            state.progress["transcript"] = apple.transcript(eid, country)
            state.save()
        result = process(
            settings.artifact_dir / state.progress["transcript"]["name"],
            settings.artifact_dir / state.progress["metadata"]["name"],
            eid,
            max_calls=max_calls,
            tracing=tracing,
        )
        result = dict(
            result,
            ingestion_run_id=state.id,
            episode_url=url,
            budget=budget.record,
            cost=usage_summary(budget.record),
        )
        state.save(status="completed", result=result, finished_at=now())
        return result
    except apple.TranscriptUnavailable as exc:
        result = {
            "status": "waiting",
            "ingestion_run_id": state.id,
            "episode_id": eid,
            "reason": str(exc),
            "transcription_submitted": False,
        }
        state.save(status="waiting", result=result)
        return result
    except Exception as exc:
        state.save(
            status="budget_exhausted" if isinstance(exc, BudgetExhausted) else "failed",
            error=str(exc),
            finished_at=now(),
        )
        raise
    finally:
        active.reset(token)
        state.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("url")
    parser.add_argument("--max-calls", type=int, default=160)
    parser.add_argument("--seconds", type=int, default=1800)
    parser.add_argument("--no-trace", action="store_true")
    args = parser.parse_args()
    print(
        json.dumps(
            ingest(
                args.url,
                max_calls=args.max_calls,
                seconds=args.seconds,
                tracing=not args.no_trace,
            ),
            indent=2,
            default=str,
        )
    )
