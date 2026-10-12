import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import pytest
from sqlalchemy import text, select
from fastapi.testclient import TestClient
from yoyo import db
from yoyo.config import settings
from yoyo.contracts import Bundle
from yoyo.service import import_bundle, counts
from yoyo.api import app


@pytest.fixture(autouse=True)
def isolated_database(tmp_path, monkeypatch):
    # Tests run only in a separate schema; never truncate the local research ledger.
    from sqlalchemy import create_engine
    import uuid

    schema = "test_" + uuid.uuid4().hex
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


def bundle():
    return Bundle.model_validate_json(
        Path("fixtures/felins-reference.json").read_text()
    )


def snapshot():
    with db.engine.connect() as c:
        return counts(c)


def test_import_replay_and_api_traceability():
    first = import_bundle(bundle(), tracing=False)
    second = import_bundle(bundle(), tracing=False)
    assert first["delta"]["companies"] == 1 and first["delta"]["claims"] == 2
    assert all(n == 0 for n in second["delta"].values())
    db.engine.dispose()  # Read through new connections after importer lifetime.
    client = TestClient(app)
    entity = client.get("/api/companies").json()[0]
    detail = client.get("/api/companies/" + entity["id"]).json()
    assert len(detail["claims"]) == 2 and detail["domain"] is None
    ev = detail["claims"][0]["evidence"][0]
    assert ev["run_id"] == first["run_id"] and ev["quote"]
    artifact = client.get("/api/sources/" + ev["source_id"] + "/artifact")
    assert artifact.status_code == 200
    assert detail["identity_decisions"][0]["decision"] == "unresolved"
    assert len(client.get("/api/runs").json()) == 2


def test_invalid_quote_and_speaker_rejected_without_partial_data():
    for field, value in [
        ("quote", "invented quote"),
        ("speaker_label", "invented speaker"),
    ]:
        b = bundle()
        setattr(b.findings[0], field, value)
        with pytest.raises(ValueError):
            import_bundle(b, tracing=False)
        assert all(n == 0 for n in snapshot().values())
    with db.engine.connect() as c:
        assert set(c.scalars(select(db.runs.c.status))) == {"failed"}


def test_interruption_rolls_back_and_retry_succeeds():
    with pytest.raises(RuntimeError):
        import_bundle(bundle(), tracing=False, fail_after_source=True)
    assert all(n == 0 for n in snapshot().values())
    assert import_bundle(bundle(), tracing=False)["delta"]["claims"] == 2


def test_concurrent_replay_has_one_research_addition():
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(lambda _: import_bundle(bundle(), tracing=False), range(2))
        )
    assert sum(r["delta"]["companies"] for r in results) == 1
    assert snapshot()["claims"] == 2


def test_new_source_version_keeps_separate_evidence():
    import_bundle(bundle(), tracing=False)
    b = bundle()
    b.source.provenance["revision_note"] = "Second saved source version"
    result = import_bundle(b, tracing=False)
    assert result["delta"]["companies"] == 0 and result["delta"]["claims"] == 0
    assert result["delta"]["sources"] == 1 and result["delta"]["evidence"] == 2


def test_corrupt_artifact_is_not_served_or_overwritten():
    result = import_bundle(bundle(), tracing=False)
    path = next(settings.artifact_dir.glob("*.json"))
    path.write_text("corrupt")
    assert (
        TestClient(app)
        .get("/api/sources/" + result["source_id"] + "/artifact")
        .status_code
        == 409
    )
    with pytest.raises(ValueError, match="hash mismatch"):
        import_bundle(bundle(), tracing=False)
    assert path.read_text() == "corrupt"


def test_observability_failure_does_not_block_research(monkeypatch):
    import langsmith

    monkeypatch.setattr(settings, "langsmith_api_key", "test-placeholder")
    monkeypatch.setattr(settings, "langsmith_tracing", True)

    def unavailable(**kwargs):
        raise RuntimeError("Trace service unavailable")

    monkeypatch.setattr(langsmith, "Client", unavailable)
    result = import_bundle(bundle())
    assert result["delta"]["claims"] == 2
    with db.engine.connect() as c:
        run = (
            c.execute(select(db.runs).where(db.runs.c.id == result["run_id"]))
            .mappings()
            .one()
        )
    assert run["status"] == "completed" and run["trace_status"] == "error"
