"""Normalize -> extract -> validate -> annotate -> atomic commit."""

import json
from pathlib import Path

from .artifacts import digest, store_json
from .claim_models import Candidates, Classifications
from .commit import commit_findings, counts
from . import db
from .resolution.findings import resolve_findings
from .config import settings
from .model import call_model
from .grounding import ground
from .prompts import ANNOTATE, EXTRACT
from .run_state import State, now
from .source import source_record
from .telemetry import Trace
from .transcripts.normalize import normalize
from .validate import validate_annotation, validate_claim
from .verify_claims import verify_findings, PROMPT as VERIFY_PROMPT


def chunks(segments, limit=14000):
    batch, size = [], 0
    for segment in segments:
        if batch and size + len(segment.text) > limit:
            yield batch
            batch, size = [], 0
        batch.append(segment)
        size += len(segment.text)
    if batch:
        yield batch


def process(
    path,
    metadata_path,
    episode_id,
    *,
    resume=None,
    max_calls=30,
    tracing=True,
    matching="lexical",
):
    if not settings.model or not settings.openai_api_key:
        raise ValueError("Set MODEL and OPENAI_API_KEY in .env")
    raw = Path(path).read_bytes()
    metadata = json.loads(Path(metadata_path).read_text())
    if str(metadata.get("episodeId", episode_id)) != episode_id:
        raise ValueError("Metadata episode ID does not match requested episode")
    format = "ttml" if Path(path).suffix == ".ttml" else "json"
    transcript = normalize(
        raw,
        external_id=episode_id,
        format=format,
        duration_seconds=metadata.get("durationSeconds"),
    )
    source = source_record(transcript, raw, metadata, format=format)
    inputs = {
        "source_id": source["id"],
        "model": settings.model,
        "max_calls": max_calls,
        "pipeline": "claims-v5-evidence-packets",
        "matching": matching,
        "prompt_hash": digest([EXTRACT, ANNOTATE, VERIFY_PROMPT]),
    }
    state = State(inputs, resume)
    if state.result:
        state.close()
        return dict(state.result, run_id=state.id, reused=True)
    state.progress["source_snapshot"] = store_json(
        {
            "metadata": metadata,
            "transcript": transcript.model_dump(),
            "raw_artifact": source["raw_artifact"],
        }
    )
    state.save(status="running", error=None, finished_at=None)
    trace = Trace(state.id, inputs, enabled=tracing)
    state.progress.setdefault("trace_attempt_ids", []).append(trace.id)
    state.save()
    accepted, rejected, annotations = {}, [], {}
    try:
        for index, batch in enumerate(chunks(transcript.segments)):
            owned = {s.id for s in batch}
            context = {s.id: s for s in transcript.segments[:20]}
            first = transcript.segments.index(batch[0])
            for segment in transcript.segments[
                max(0, first - 2) : first + len(batch) + 2
            ]:
                context[segment.id] = segment
            payload = {
                "owned_segment_ids": sorted(owned),
                "segments": [s.model_dump(exclude={"words"}) for s in context.values()],
            }
            candidates = call_model(
                state, f"extract-{index}", EXTRACT, payload, Candidates, trace
            )
            valid, errors = screen(
                candidates, transcript, owned, list(context.values())
            )
            if errors:
                repaired = optional_repair(
                    state,
                    f"repair-{index}",
                    EXTRACT,
                    dict(
                        payload,
                        repair_only=errors,
                        instruction="Correct rejected candidates using exact original segments. Omit anything unsupported.",
                    ),
                    Candidates,
                    trace,
                )
                fixed, remaining = screen(
                    repaired or Candidates(claims=[]),
                    transcript,
                    owned,
                    list(context.values()),
                )
                valid.extend(fixed)
                rejected.extend(remaining if repaired is not None else errors)
                state.progress.setdefault("initial_rejections", {})[str(index)] = (
                    store_json(errors)
                )
            if not valid:
                continue
            keyed = {digest(c.model_dump()): c for c in valid}
            classified = call_model(
                state,
                f"annotate-{index}",
                ANNOTATE,
                {
                    "claims": [
                        {"claim_key": k, **c.model_dump()} for k, c in keyed.items()
                    ]
                },
                Classifications,
                trace,
            )
            if len(classified.claims) != len(keyed) or {
                c.claim_key for c in classified.claims
            } != set(keyed):
                raise ValueError("Annotation did not cover each claim exactly once")
            for c in classified.claims:
                validate_annotation(c.annotation, keyed[c.claim_key])
                annotations[c.claim_key] = c.annotation
            accepted.update(keyed)
        state.progress["rejected"] = store_json(rejected)
        state.progress["accepted"] = store_json(
            [c.model_dump() for c in accepted.values()]
        )
        state.save()
        if "ledger_before" not in state.progress:
            with db.engine.connect() as conn:
                state.progress["ledger_before"] = counts(conn)
            state.save()
        verified = verify_findings(list(accepted.values()), source, state, trace)
        findings, annotations, resolved_ids, added_ids = resolve_findings(
            source, verified, annotations, state, trace, matching
        )
        provenance = {
            "model": settings.model,
            "prompt_hash": inputs["prompt_hash"],
            "run_id": state.id,
            "validation": "structural_quote_and_model_entailment_checks",
        }
        with trace.span(
            "commit", {"accepted": len(accepted), "rejected": len(rejected)}
        ) as output:
            result = commit_findings(
                source,
                transcript,
                findings,
                annotations,
                state.id,
                provenance,
                resolved_companies=resolved_ids,
                before_counts=state.progress["ledger_before"],
                added_company_ids=added_ids,
            )
            output.update(result)
        trace.finish(result)
        state.save(trace_id=trace.id, trace_url=trace.url, trace_status=trace.status)
        return dict(
            result, run_id=state.id, rejected=len(rejected), trace_url=trace.url
        )
    except Exception as exc:
        trace.finish(error=str(exc))
        state.save(
            status="failed",
            error=str(exc),
            finished_at=now(),
            trace_id=trace.id,
            trace_url=trace.url,
            trace_status=trace.status,
        )
        raise
    finally:
        state.close()


def screen(candidates, transcript, owned, context):
    valid, errors = [], []
    for candidate in candidates.claims:
        candidate = ground(candidate, context)
        try:
            if candidate.anchor_segment_id not in owned:
                raise ValueError("Anchor not owned by this chunk")
            validate_claim(candidate, transcript)
            valid.append(candidate)
        except ValueError as exc:
            errors.append({"candidate": candidate.model_dump(), "reason": str(exc)})
    return valid, errors


def optional_repair(state, key, *args):
    try:
        return call_model(state, key, *args)
    except Exception:
        operation = state.progress["operations"].get(key, {})
        if operation.get("status") != "unknown_outcome":
            raise
        state.progress.setdefault("warnings", {})[key] = (
            "Optional repair outcome unknown; not resubmitted. Unrepaired candidates rejected."
        )
        state.save()
        return None
