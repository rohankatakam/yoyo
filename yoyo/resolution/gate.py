import json
import time
from .contracts import Decision, Mention, EntityType
from .retrieve import retrieve
from .prompts import RESOLVE, TYPE
from .enrich import enrich
from .match_check import check_match


def decide(mention, candidates, research):
    payload = {
        "mention": mention.model_dump(),
        "candidates": [
            {
                "id": item["company"]["id"],
                "name": item["company"]["name"],
                "domain": item["company"].get("domain"),
                "linkedin_url": item["company"].get("linkedin_url"),
                "description": item["company"].get("description"),
                "headquarters": item["company"].get("headquarters_country_codes"),
                "identity": {
                    k: item["company"].get("identity", {}).get(k)
                    for k in ("status", "aliases", "citations")
                },
            }
            for item in candidates
        ],
    }
    from openai.lib._pydantic import to_strict_json_schema

    allowed_ids = [c["company"]["id"] for c in candidates]
    schema = to_strict_json_schema(Decision)
    schema["properties"]["company_id"] = {"enum": allowed_ids + [None]}
    schema["properties"]["entity_type"] = {"type": "string", "enum": ["company"]}
    schema["properties"]["outcome"] = {
        "type": "string",
        "enum": ["MATCH", "NEW_COMPANY", "UNRESOLVED"]
        if candidates
        else ["NEW_COMPANY", "UNRESOLVED"],
    }
    schema["properties"]["evidence"]["items"] = {
        "type": "string",
        "enum": ["mention", *allowed_ids],
    }
    decision = research.ask(RESOLVE, payload, Decision, schema=schema)
    if decision.entity_type in {"sector", "product", "brand", "division", "person"}:
        decision = decision.model_copy(
            update={"outcome": "NOT_COMPANY", "company_id": None}
        )
    allowed = {c["company"]["id"] for c in candidates}
    if decision.company_id and decision.company_id not in allowed:
        raise ValueError("Resolver selected a company outside its candidate set")
    if not set(decision.evidence) <= allowed | {"mention"}:
        raise ValueError("Resolver cited evidence outside its input")
    if decision.outcome == "MATCH":
        candidate = next(
            c for c in payload["candidates"] if c["id"] == decision.company_id
        )
        rejected = check_match(mention, candidate, research)
        if rejected:
            return rejected
    return decision


class Gate:
    def __init__(self, ledger, research, mode="lexical"):
        if mode not in {"lexical", "hybrid"}:
            raise ValueError("Unknown matching mode")
        self.ledger, self.research, self.mode = ledger, research, mode
        self.history = []

    def resolve(self, mention):
        started = time.monotonic()
        event_start = len(self.research.cache.events)
        classification = self.research.ask(TYPE, mention.model_dump(), EntityType)
        if classification.kind != "company":
            decision = Decision(
                outcome="UNRESOLVED"
                if classification.kind == "uncertain"
                else "NOT_COMPANY",
                entity_type=classification.kind,
                company_id=None,
                reason=classification.reason,
                evidence=["mention"],
            )
            entry = {
                "mention": mention.model_dump(),
                "initial": decision.model_dump(),
                "decision": decision.model_dump(),
                "company_id": None,
                "candidates": [],
                "enrichment": None,
                "seconds": time.monotonic() - started,
                "provider_events": self.research.cache.events[event_start:],
            }
            self.history.append(entry)
            return entry
        candidates = retrieve(
            mention, self.ledger.companies(), self.mode, self.research
        )
        decision = decide(mention, candidates, self.research)
        initial = decision.model_dump()
        company_id, enrichment = decision.company_id, None
        if decision.outcome == "NEW_COMPANY":
            record, pages, raw = enrich(mention, self.research)
            enrichment = {
                "parsed": record,
                "raw": raw,
                "source_urls": [p["url"] for p in pages],
            }
            if record is None:
                decision = Decision(
                    outcome="UNRESOLVED",
                    entity_type="uncertain",
                    company_id=None,
                    reason="Research did not establish an independently supported company identity.",
                    evidence=["mention"],
                )
            else:
                # Research must explain the ORIGINAL mention, not merely find a real company.
                candidate = {
                    "id": "researched-company",
                    "name": record["name"],
                    **record["profile"],
                    "identity": {
                        "status": "researched_candidate",
                        "citations": record["identity_citations"],
                    },
                }
                checked = decide(mention, [{"company": candidate}], self.research)
                if checked.outcome != "MATCH":
                    decision = Decision(
                        outcome="UNRESOLVED",
                        entity_type="uncertain",
                        company_id=None,
                        reason="Researched company does not establish the original mention's identity: "
                        + checked.reason,
                        evidence=["mention"],
                    )
                    entry = {
                        "mention": mention.model_dump(),
                        "initial": initial,
                        "decision": decision.model_dump(),
                        "company_id": None,
                        "candidates": [
                            {"id": c["company"]["id"], "name": c["company"]["name"]}
                            for c in candidates
                        ],
                        "enrichment": enrichment,
                        "seconds": time.monotonic() - started,
                        "provider_events": self.research.cache.events[event_start:],
                    }
                    self.history.append(entry)
                    return entry
                verified = Mention(
                    transcript_evidence=mention.transcript_evidence,
                    episode_context=mention.episode_context,
                    name=record["name"],
                    context=mention.context
                    + "\nVerified profile: "
                    + json.dumps(record),
                    source_id=mention.source_id,
                    domain=record["profile"].get("domain"),
                    linkedin_url=record["profile"].get("linkedin_url"),
                )
                fresh = retrieve(
                    verified, self.ledger.companies(), self.mode, self.research
                )
                if fresh:
                    decision = decide(verified, fresh, self.research)
                    company_id = decision.company_id
                if decision.outcome == "NEW_COMPANY":
                    company_id = self.ledger.create(record, pages, mention, decision)
        if decision.outcome == "MATCH":
            company_id = self.ledger.alias(company_id, mention, decision)
        entry = {
            "mention": mention.model_dump(),
            "initial": initial,
            "decision": decision.model_dump(),
            "company_id": company_id,
            "candidates": [
                {
                    "id": c["company"]["id"],
                    "name": c["company"]["name"],
                    "lexical": c["lexical"],
                    "semantic": c["semantic"],
                }
                for c in candidates
            ],
            "enrichment": enrichment,
            "seconds": time.monotonic() - started,
            "provider_events": self.research.cache.events[event_start:],
        }
        self.history.append(entry)
        return entry
