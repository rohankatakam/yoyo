import re
from urllib.parse import urlparse
from ..company_models import CompanyProfile
from .contracts import Enrichment
from .prompts import ENRICH
from .websites import verify_website


def enrich(mention, research):
    # Both retrieval options issue identical research for the same NEW_COMPANY mention.
    target_segments = [
        s["text"]
        for s in mention.transcript_evidence
        if mention.name.casefold() in s["text"].casefold()
    ]
    search_context = " ".join(target_segments)[:600] or mention.context[:300]
    queries = [
        f"{mention.name} official company {search_context}",
        f"{mention.name} company LinkedIn ownership funding headquarters products markets",
    ]
    sources = {}
    for query in queries:
        for row in research.search(query).get("results", []):
            if row.get("text"):
                sources[row["url"]] = {
                    "url": row["url"],
                    "title": row.get("title", ""),
                    "text": "URL: " + row["url"] + "\n" + row["text"],
                    "published_at": row.get("publishedDate"),
                }
    pages = list(sources.values())
    for page in pages:
        page["passages"] = [
            part.strip()
            for part in re.split(r"\n+|(?<=[.!?])\s+", page["text"])
            if part.strip()
        ]
    result = research.ask(
        ENRICH,
        {
            "mention": mention.model_dump(),
            "sources": [
                {
                    "index": i,
                    "url": p["url"],
                    "passages": [
                        {"index": j, "text": v} for j, v in enumerate(p["passages"])
                    ],
                }
                for i, p in enumerate(pages)
            ],
        },
        Enrichment,
    )

    def citations_valid(citations):
        return bool(citations) and all(
            0 <= c.source < len(pages)
            and 0 <= c.passage < len(pages[c.source]["passages"])
            for c in citations
        )

    if (
        result.entity_type != "company"
        or not result.canonical_name
        or not citations_valid(result.identity_citations)
    ):
        return None, pages, result.model_dump()
    from .retrieve import normalized

    def citation(c):
        return {"source": c.source, "quote": pages[c.source]["passages"][c.passage]}

    names = " ".join(citation(c)["quote"] for c in result.identity_citations)
    if normalized(result.canonical_name) not in normalized(names):
        return None, pages, result.model_dump()
    values, evidence, rejected = {}, {}, []
    for attribute in result.attributes:
        field = attribute.field
        if (
            field not in CompanyProfile.model_fields
            or field == "field_evidence"
            or not citations_valid(attribute.citations)
        ):
            rejected.append(attribute.model_dump())
            continue
        value = attribute.value
        if field == "domain":
            value = str(value).lower().removeprefix("www.").rstrip("/")
            if "/" in value or "." not in value:
                rejected.append(attribute.model_dump())
                continue
            if not any(
                urlparse(pages[c.source]["url"]).hostname in {value, "www." + value}
                for c in attribute.citations
            ):
                rejected.append(attribute.model_dump())
                continue
        if field == "linkedin_url":
            parsed = urlparse(str(value))
            cited_urls = [urlparse(pages[c.source]["url"]) for c in attribute.citations]
            if not any(
                u.hostname in {"linkedin.com", "www.linkedin.com"}
                and u.path.rstrip("/") == parsed.path.rstrip("/")
                for u in cited_urls
            ):
                rejected.append(attribute.model_dump())
                continue
            if parsed.hostname not in {
                "linkedin.com",
                "www.linkedin.com",
            } or not parsed.path.startswith("/company/"):
                rejected.append(attribute.model_dump())
                continue
        try:
            CompanyProfile(
                **{field: value}, field_evidence={field: ["pending-source-id"]}
            )
        except ValueError:
            rejected.append(attribute.model_dump())
            continue
        values[field] = value
        evidence[field] = [citation(c) for c in attribute.citations]
    observed_domains = []
    if values.get("domain"):
        accepted, observation = verify_website(
            result.canonical_name, values["domain"], pages, research
        )
        observed_domains.append(observation)
        if not accepted:
            values.pop("domain")
            evidence.pop("domain", None)
    return (
        {
            "observed_domains": observed_domains,
            "name": result.canonical_name,
            "profile": values,
            "evidence": evidence,
            "identity_citations": [citation(c) for c in result.identity_citations],
            "reason": result.reason,
            "rejected_attributes": rejected,
        },
        pages,
        result.model_dump(),
    )
