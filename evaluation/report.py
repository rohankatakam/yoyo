"""Score the fixed controls without passing expected answers to the resolver."""

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path


def summarize(result):
    rows = result["rows"]
    groups = defaultdict(set)
    owners = defaultdict(set)
    violations = []
    retrieved = eligible = 0
    decisions = Counter()
    events = {}
    for row in rows:
        decision = row["decision"]["outcome"]
        decisions[decision] += 1
        group = row.get("group")
        company_id = row["company_id"]
        if row["expected"] == "MATCH" and groups[group]:
            eligible += 1
            retrieved += bool(groups[group] & {c["id"] for c in row["candidates"]})
        if company_id:
            if row["expected"] in {"NOT_COMPANY", "UNRESOLVED"}:
                violations.append(row["case_id"])
            else:
                groups[group].add(company_id)
                owners[company_id].add(group)
        for event in row["provider_events"]:
            events.setdefault(event["key"], event)
    kinds = Counter(e["kind"] for e in events.values())
    usage = Counter()
    for event in events.values():
        for key, value in event.get("usage", {}).items():
            if isinstance(value, int):
                usage[key] += value
    return {
        "cases": len(rows),
        "exact_expected_outcomes": sum(
            r["expected"] == r["decision"]["outcome"] for r in rows
        ),
        "decisions": dict(decisions),
        "incorrect_merge_groups": sum(max(0, len(g) - 1) for g in owners.values()),
        "duplicate_entities": sum(max(0, len(ids) - 1) for ids in groups.values()),
        "false_entity_or_ambiguous_accepts": violations,
        "retrieval_hit": retrieved,
        "retrieval_eligible": eligible,
        "unique_provider_requests": dict(kinds),
        "usage": dict(usage),
        "reported_exa_dollars": sum(
            (e.get("costDollars") or {}).get("total", 0) for e in events.values()
        ),
        "cold_request_seconds_estimate": round(
            sum(e["cold_seconds"] for e in events.values()), 1
        ),
        "observed_case_seconds": round(sum(r["case_seconds"] for r in rows), 1),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("label")
    args = parser.parse_args()
    results = {
        m: json.loads(Path(f"artifacts/{args.label}-{m}.json").read_text())
        for m in ["lexical", "hybrid"]
    }
    summary = {m: summarize(r) for m, r in results.items()}
    Path(f"artifacts/{args.label}-summary.json").write_text(
        json.dumps(summary, indent=2)
    )
    print(json.dumps(summary, indent=2))
    for left, right in zip(results["lexical"]["rows"], results["hybrid"]["rows"]):
        print(
            left["case_id"],
            left["mention"]["name"],
            left["expected"],
            left["decision"]["outcome"],
            right["decision"]["outcome"],
        )
