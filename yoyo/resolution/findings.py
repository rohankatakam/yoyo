"""Resolve each unique company mention before any claim can enter the ledger."""

from ..artifacts import digest, store_json
from .contracts import Mention
from .gate import Gate
from .ledger import Ledger
from .providers import Research
from .packets import episode_context, transcript_packet


def resolve_findings(source, findings, annotations, state, trace, mode):
    contexts = {}
    for claim in findings:
        for p in claim.participants:
            if p.kind == "company":
                contexts.setdefault(p.name, []).append(
                    " ".join(q.quote for q in claim.quotes)
                )
    gate = Gate(Ledger(run_id=state.id), Research(trace), mode)
    saved = state.progress.setdefault("resolution", {})
    resolved = {}
    for name, passages in contexts.items():
        mention = Mention(
            name=name,
            context="Target company mention: " + name,
            source_id=source["id"],
            transcript_evidence=transcript_packet(source, name, findings),
            episode_context=episode_context(source, name),
        )
        key = digest(mention.model_dump())
        if key not in saved:
            saved[key] = gate.resolve(mention)
            state.save()
        resolved[name.casefold()] = saved[key]
    kept, labels, withheld = [], {}, []
    for claim in findings:
        company_mentions = [p for p in claim.participants if p.kind == "company"]
        if any(
            resolved[p.name.casefold()]["decision"]["outcome"] == "UNRESOLVED"
            for p in company_mentions
        ):
            withheld.append(
                {"claim": claim.model_dump(), "reason": "Unresolved company identity"}
            )
            continue
        participants = [
            p
            for p in claim.participants
            if p.kind != "company"
            or resolved[p.name.casefold()]["decision"]["outcome"]
            in {"MATCH", "NEW_COMPANY"}
        ]
        if not any(p.kind == "company" for p in participants):
            withheld.append(
                {
                    "claim": claim.model_dump(),
                    "reason": "No resolved company participant",
                }
            )
            continue
        filtered = claim.model_copy(update={"participants": participants})
        kept.append(filtered)
        if digest(claim.model_dump()) in annotations:
            labels[digest(filtered.model_dump())] = annotations[
                digest(claim.model_dump())
            ]
    state.progress["withheld_claims"] = store_json(withheld)
    state.save()
    ids = {
        name: entry["company_id"]
        for name, entry in resolved.items()
        if entry["company_id"]
    }
    new_ids = [
        e["company_id"]
        for e in resolved.values()
        if e["decision"]["outcome"] == "NEW_COMPANY"
    ]
    return kept, labels, ids, new_ids
