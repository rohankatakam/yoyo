"""One durable allowance shared by every nested provider call in a run."""

from contextlib import contextmanager
from contextvars import ContextVar
from threading import RLock
import time

active = ContextVar("research_budget", default=None)


class BudgetExhausted(RuntimeError):
    pass


class Budget:
    def __init__(self, state, max_calls=120, seconds=1800):
        self.state = state
        self.lock = RLock()
        self.record = state.progress.setdefault(
            "budget",
            {
                "max_calls": max_calls,
                "deadline": time.time() + seconds,
                "calls": {},
            },
        )
        state.save()

    def reserve(self, key, kind):
        with self.lock:
            calls = self.record["calls"]
            if key in calls:
                raise RuntimeError(
                    f"Budget operation {key} already reserved; reconcile before retry"
                )
            if time.time() >= self.record["deadline"]:
                raise BudgetExhausted("Shared elapsed-time budget exhausted")
            if len(calls) >= self.record["max_calls"]:
                raise BudgetExhausted("Shared external-call budget exhausted")
            calls[key] = {"kind": kind, "status": "reserved", "at": time.time()}
            self.state.save()

    def finish(self, key, result):
        with self.lock:
            self.record["calls"][key].update(
                status="completed",
                usage=result.get("usage", {}),
                provider_cost_dollars=result.get("costDollars"),
            )
            self.state.save()

    @contextmanager
    def bind(self):
        token = active.set(self)
        try:
            yield self
        finally:
            active.reset(token)


def reserve(key, kind):
    budget = active.get()
    if budget:
        budget.reserve(key, kind)


def finish(key, result):
    budget = active.get()
    if budget:
        budget.finish(key, result)


def timeout(default):
    budget = active.get()
    return (
        min(default, max(0.1, budget.record["deadline"] - time.time()))
        if budget
        else default
    )


def usage_summary(record):
    calls = list(record.get("calls", {}).values())
    reported = [
        c["provider_cost_dollars"] for c in calls if c.get("provider_cost_dollars")
    ]
    return {
        "external_calls": len(calls),
        "input_tokens": sum(c.get("usage", {}).get("input_tokens", 0) for c in calls),
        "output_tokens": sum(c.get("usage", {}).get("output_tokens", 0) for c in calls),
        "provider_reported_usd": sum(
            r.get("total", 0) if isinstance(r, dict) else r for r in reported
        ),
        "model_cost_usd": None,
        "unreconciled_calls": sum(c["status"] != "completed" for c in calls),
        "note": "Provider-reported dollars exclude model billing. Calls/time are capped; USD is not capped.",
    }
