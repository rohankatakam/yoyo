"""Small contract/retrieval tests. Live matching is evaluated separately, not mocked here."""

import pytest
from yoyo.resolution.contracts import Mention, Decision
from yoyo.resolution.retrieve import lexical_score, cosine, retrieve
from yoyo.resolution.cache import Cache
from yoyo.config import settings


def test_alias_retrieval_and_same_name_are_candidates_not_merges():
    company = {
        "id": "one",
        "name": "BranchOut Food Inc.",
        "identity": {"aliases": ["BranchOut"]},
    }
    assert (
        lexical_score(Mention(name="BranchOut", context="", source_id="test"), company)
        == 1
    )
    company["name"] = "MicroDried"
    assert (
        lexical_score(Mention(name="Microdryd", context="", source_id="test"), company)
        > 0.55
    )
    candidates = retrieve(
        Mention(name="Microdryd", context="", source_id="test"),
        [company],
        "lexical",
        None,
    )
    assert candidates[0]["company"]["id"] == "one"


def test_identity_decision_contract():
    with pytest.raises(ValueError):
        Decision(
            outcome="MATCH",
            entity_type="sector",
            company_id="one",
            reason="bad",
            evidence=["one"],
        )
    with pytest.raises(ValueError):
        Decision(
            outcome="NEW_COMPANY",
            entity_type="company",
            company_id="invented",
            reason="bad",
            evidence=["mention"],
        )
    with pytest.raises(ValueError):
        Decision(
            outcome="MATCH",
            entity_type="company",
            company_id=None,
            reason="bad",
            evidence=["mention"],
        )


def test_cosine_is_not_a_probability():
    assert cosine([1, 0], [1, 0]) == 1
    assert cosine([1, 0], [-1, 0]) == -1
    assert cosine([0, 0], [1, 0]) == 0


def test_cache_uses_real_first_result_and_never_retries_unknown(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "artifact_dir", tmp_path)
    cache = Cache()

    def first():
        return {"value": "returned once"}

    assert cache.call("test", {}, first) == cache.call(
        "test", {}, lambda: pytest.fail("duplicate submission")
    )

    def failure():
        raise RuntimeError("connection interrupted")

    with pytest.raises(RuntimeError):
        cache.call("failure", {}, failure)
    with pytest.raises(RuntimeError, match="inspect before retry"):
        cache.call("failure", {}, lambda: pytest.fail("must not retry"))
