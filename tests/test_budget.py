import pytest
from yoyo.budget import Budget, BudgetExhausted
from yoyo.config import settings
from yoyo.resolution.cache import Cache


class MemoryState:
    def __init__(self):
        self.progress = {}

    def save(self):
        pass


def test_nested_cache_calls_share_budget_and_replay_is_free(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "artifact_dir", tmp_path)
    state = MemoryState()
    budget = Budget(state, max_calls=1)
    with budget.bind():
        assert Cache().call("one", {}, lambda: {"value": 1}) == {"value": 1}
        assert Cache().call("one", {}, lambda: pytest.fail("repeat")) == {"value": 1}
        with pytest.raises(BudgetExhausted):
            Cache().call("two", {}, lambda: pytest.fail("over budget"))
    assert len(state.progress["budget"]["calls"]) == 1
    assert len(list((tmp_path / "provider-cache").glob("*.json"))) == 1


def test_unknown_call_stays_charged_after_restart(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "artifact_dir", tmp_path)
    state = MemoryState()

    def interrupted():
        raise ConnectionError("lost response")

    with Budget(state, max_calls=2).bind():
        with pytest.raises(ConnectionError):
            Cache().call("unknown", {}, interrupted)
    with Budget(state, max_calls=100).bind():
        with pytest.raises(RuntimeError, match="inspect before retry"):
            Cache().call("unknown", {}, lambda: pytest.fail("duplicate"))
        Cache().call("another", {}, lambda: {})
        with pytest.raises(BudgetExhausted):
            Cache().call("third", {}, lambda: {})
    assert state.progress["budget"]["max_calls"] == 2


def test_expired_budget_blocks_new_work_without_provider_submission(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(settings, "artifact_dir", tmp_path)
    with Budget(MemoryState(), seconds=-1).bind():
        with pytest.raises(BudgetExhausted):
            Cache().call("late", {}, lambda: pytest.fail("expired"))


def test_apple_reference_and_auth_destination_validation():
    from yoyo.apple import episode_id, request

    assert episode_id("https://podcasts.apple.com/us/podcast/x/id1?i=123") == "123"
    with pytest.raises(ValueError):
        episode_id("https://example.com/?i=123")
    with pytest.raises(ValueError, match="Apple credentials"):
        request("https://example.com", authorized=True)


def test_missing_apple_transcript_is_known_cached_result(tmp_path, monkeypatch):
    import httpx
    from yoyo import apple

    monkeypatch.setattr(settings, "artifact_dir", tmp_path)
    monkeypatch.setattr(apple, "TTML", tmp_path / "no-local-transcript")
    monkeypatch.setattr(apple, "local_podcasts_headers", lambda: {})
    calls = []

    def missing(url, **kwargs):
        calls.append(url)
        return httpx.Response(404, request=httpx.Request("GET", url))

    monkeypatch.setattr(apple.httpx, "get", missing)
    with Budget(MemoryState(), max_calls=1).bind():
        for _ in range(2):
            with pytest.raises(apple.TranscriptUnavailable):
                apple.transcript("123")
    assert len(calls) == 1


def test_saved_response_survives_accounting_write_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "artifact_dir", tmp_path)
    state = MemoryState()
    budget = Budget(state, max_calls=1)
    with budget.bind():
        original = state.save

        def execute():
            state.save = lambda: (_ for _ in ()).throw(RuntimeError("DB unavailable"))
            return {"value": "real first result"}

        with pytest.raises(RuntimeError, match="DB unavailable"):
            Cache().call("response-before-accounting", {}, execute)
        state.save = original
        assert (
            Cache().call(
                "response-before-accounting", {}, lambda: pytest.fail("resubmitted")
            )["value"]
            == "real first result"
        )
