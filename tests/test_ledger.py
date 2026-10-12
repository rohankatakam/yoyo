import json
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, text

from yoyo import db
from yoyo.api import app
from yoyo.artifacts import digest
from yoyo.claim_models import Annotation, Candidate
from yoyo.commit import commit_findings, counts
from yoyo.config import settings
from yoyo.source import source_record
from yoyo.transcripts.normalize import normalize


@pytest.fixture(autouse=True)
def isolated_database(tmp_path, monkeypatch):
    schema = "test_" + uuid4().hex
    admin = create_engine(settings.database_url)
    with admin.begin() as c:
        c.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_engine(
        settings.database_url, connect_args={"options": f"-csearch_path={schema}"}
    )
    monkeypatch.setattr(db, "engine", engine)
    monkeypatch.setattr(settings, "artifact_dir", tmp_path)
    db.metadata.create_all(engine)
    yield
    engine.dispose()
    with admin.begin() as c:
        c.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
    admin.dispose()


def input_data():
    # Small adversarial inputs test invariants; no recorded model outputs or runtime seed.
    raw = json.dumps(
        {
            "segments": [
                {
                    "text": "Acme may expand next year.",
                    "start": 0,
                    "end": 5,
                    "speaker": "speaker_1",
                }
            ]
        }
    ).encode()
    transcript = normalize(raw, external_id="test-episode")
    segment = transcript.segments[0]
    claim = Candidate(
        text=segment.text,
        predicate="may_expand",
        participants=[{"kind": "company", "name": "Acme", "role": "subject"}],
        anchor_segment_id=segment.id,
        speaker_label=segment.speaker,
        quotes=[{"segment_id": segment.id, "quote": segment.text}],
        rationale="Explicit future possibility",
        context="actual",
    )
    annotation = Annotation(
        time_class="FORWARD_LOOKING",
        supporting_segment_ids=[segment.id],
        rationale="May expand",
    )
    return raw, transcript, claim, annotation


def execute(*, revision=None, fail=False):
    raw, transcript, claim, annotation = input_data()
    source = source_record(transcript, raw, {"title": "Test", "revision": revision})
    run_id = str(uuid4())
    with db.engine.begin() as c:
        c.execute(
            db.runs.insert().values(
                id=run_id,
                status="running",
                input={},
                progress={},
                operation_key=run_id,
                trace_status="disabled",
            )
        )
    return commit_findings(
        source,
        transcript,
        [claim],
        {digest(claim.model_dump()): annotation},
        run_id,
        {},
        fail_after_source=fail,
    )


def snapshot():
    with db.engine.connect() as c:
        return counts(c)


def test_replay_and_restart_traceability():
    first, second = execute(), execute()
    assert first["delta"]["companies"] == 1
    assert all(n == 0 for n in second["delta"].values())
    db.engine.dispose()
    client = TestClient(app)
    company = client.get("/api/companies").json()[0]
    detail = client.get("/api/companies/" + company["id"]).json()
    assert detail["claims"][0]["annotation"]["time_class"] == "FORWARD_LOOKING"
    assert detail["claims"][0]["evidence"][0]["segments"][0]["start"] == 0
    assert (
        client.get("/api/sources/" + first["source_id"] + "/artifact").status_code
        == 200
    )
    with db.engine.connect() as c:
        assert set(c.scalars(select(db.runs.c.status))) == {"completed"}


def test_atomic_failure_and_retry():
    with pytest.raises(RuntimeError):
        execute(fail=True)
    assert all(n == 0 for n in snapshot().values())
    assert execute()["delta"]["claims"] == 1


def test_concurrent_replay_and_new_evidence():
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: execute(), range(2)))
    assert sum(r["delta"]["companies"] for r in results) == 1
    result = execute(revision="new source version")
    assert result["delta"]["claims"] == 0 and result["delta"]["evidence"] == 1


def test_artifact_corruption():
    result = execute()
    next(settings.artifact_dir.glob("*.json")).write_text("corrupt")
    client = TestClient(app)
    assert (
        client.get("/api/sources/" + result["source_id"] + "/artifact").status_code
        == 409
    )
    with pytest.raises(ValueError, match="hash mismatch"):
        execute()


def test_unknown_model_operation_is_not_retried():
    from yoyo.artifacts import digest
    from yoyo.claim_models import Candidates
    from yoyo.model import call_model
    from yoyo.run_state import State
    from yoyo.telemetry import Trace

    state = State({"source_id": "test", "max_calls": 1})
    signature = digest([settings.model, "prompt", {}, Candidates.model_json_schema()])
    state.progress["operations"]["one"] = {
        "status": "unknown_outcome",
        "signature": signature,
    }
    try:
        with pytest.raises(RuntimeError, match="inspect before resubmitting"):
            call_model(
                state,
                "one",
                "prompt",
                {},
                Candidates,
                Trace(state.id, {}, enabled=False),
            )
        with pytest.raises(RuntimeError, match="already running"):
            State(state.inputs)
    finally:
        state.close()


def test_plain_rerun_reuses_interrupted_run_and_optional_failure_stays_unknown():
    from yoyo.run_state import State
    from yoyo.pipeline import optional_repair
    from yoyo.claim_models import Candidates
    from yoyo.telemetry import Trace

    first = State({"source_id": "interrupted", "max_calls": 2})
    first.progress["operations"]["repair"] = {
        "status": "unknown_outcome",
        "signature": digest(
            [settings.model, "prompt", {}, Candidates.model_json_schema()]
        ),
    }
    first.save(status="failed")
    run_id = first.id
    first.close()
    resumed = State({"source_id": "interrupted", "max_calls": 2})
    try:
        assert resumed.id == run_id
        assert (
            optional_repair(
                resumed,
                "repair",
                "prompt",
                {},
                Candidates,
                Trace(run_id, {}, enabled=False),
            )
            is None
        )
        assert resumed.progress["operations"]["repair"]["status"] == "unknown_outcome"
    finally:
        resumed.close()
