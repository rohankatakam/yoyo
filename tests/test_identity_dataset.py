"""Frozen evaluation integrity and scoring boundaries; no provider calls."""

import hashlib
import json
from pathlib import Path
import pytest
from evaluation.identity_v1.score import score

ROOT = Path(__file__).resolve().parents[1] / "evaluation" / "identity_v1"


def test_dataset_hashes_and_case_ids():
    manifest = json.loads((ROOT / "manifest.json").read_text())
    for name, sha in manifest["sha256"].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == sha
    cases = [json.loads(s) for s in (ROOT / "cases.jsonl").read_text().splitlines()]
    assert len({c["id"] for c in cases}) == manifest["case_count"]
    assert [c["order"] for c in cases] == list(range(1, 25))


def test_scoring_uses_frozen_labels_and_requires_original_inputs():
    cases = [json.loads(s) for s in (ROOT / "cases.jsonl").read_text().splitlines()]
    rows = [
        dict(
            case_id=c["id"],
            mention=c["mention"],
            expected="TAMPERED",
            group=None,
            decision={"outcome": "UNRESOLVED"},
            company_id=None,
            candidates=[],
            provider_events=[],
            case_seconds=0,
        )
        for c in cases
    ]
    assert score({"rows": rows})["exact_expected_outcomes"] == sum(
        c["expected"] == "UNRESOLVED" for c in cases
    )
    with pytest.raises(ValueError, match="reordered"):
        score({"rows": list(reversed(rows))})
    rows[0]["mention"] = dict(rows[0]["mention"], name="altered")
    with pytest.raises(ValueError, match="Input packet differs"):
        score({"rows": rows})
