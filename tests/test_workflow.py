from test_ledger import isolated_database as isolated_database
from yoyo.agent_result import run_result
from yoyo.discovery import coverage_snapshot, validate_window
from yoyo.run_state import State, now
import pytest


def test_empty_agent_result_is_database_derived_and_lock_has_no_open_transaction():
    state = State({"kind": "discovery-agent", "test": "result"})
    try:
        state.progress.update(
            started_at=now().isoformat(), coverage_before=coverage_snapshot()
        )
        # AUTOCOMMIT avoids blocking the checkpointer's concurrent index migrations.
        assert state.lock.get_execution_options()["isolation_level"] == "AUTOCOMMIT"
        result = run_result(state, "completed", "The model claimed 100 companies")
        assert result["added_entity_ids"] == []
        assert result["claim_ids"] == []
        assert all(v == 0 for v in result["coverage_delta"].values())
    finally:
        state.close()


def test_window_rejects_invalid_or_reversed_dates():
    with pytest.raises(ValueError):
        validate_window("2026-13-12", None)
    with pytest.raises(ValueError):
        validate_window("2026-10-12", "2025-01-01")
