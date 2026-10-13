"""Score a live run against frozen labels; never use labels during inference."""

import argparse
import json
from pathlib import Path
from evaluation.report import summarize


def score(result):
    root = Path(__file__).parent
    cases = [
        json.loads(line) for line in (root / "cases.jsonl").read_text().splitlines()
    ]
    baseline = [
        json.loads(line) for line in (root / "baseline.jsonl").read_text().splitlines()
    ]
    if [r["case_id"] for r in result["rows"]] != [c["id"] for c in cases]:
        raise ValueError("Incomplete, reordered or different evaluation cases")
    rows = []
    for row, case in zip(result["rows"], cases):
        if row["mention"] != case["mention"]:
            raise ValueError("Input packet differs from frozen evaluation case")
        rows.append(dict(row, expected=case["expected"], group=case["group"]))
    metrics = summarize(dict(result, rows=rows))
    metrics["baseline_expected_agreement"] = sum(
        b["expected"] == b["new_with_metadata"] for b in baseline
    )
    metrics["changed_decisions"] = [
        {
            "id": row["case_id"],
            "expected": case["expected"],
            "baseline": saved["new_with_metadata"],
            "current": row["decision"]["outcome"],
        }
        for row, case, saved in zip(rows, cases, baseline)
        if row["decision"]["outcome"] != saved["new_with_metadata"]
    ]
    return metrics


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("result", type=Path)
    args = parser.parse_args()
    print(json.dumps(score(json.loads(args.result.read_text())), indent=2))
