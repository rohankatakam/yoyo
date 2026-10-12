"""Candidate retrieval only: scores never constitute an identity decision."""

import math
import re
from difflib import SequenceMatcher


def normalized(name):
    return re.sub(r"[^a-z0-9]", "", name.casefold())


def lexical_score(mention, company):
    aliases = [company["name"], *company.get("identity", {}).get("aliases", [])]
    if mention.linkedin_url and mention.linkedin_url == company.get("linkedin_url"):
        return 1.0
    if mention.domain and mention.domain == company.get("domain"):
        return 1.0
    return max(
        SequenceMatcher(None, normalized(mention.name), normalized(a)).ratio()
        for a in aliases
    )


def profile_text(company):
    return " ".join(
        str(company.get(k) or "")
        for k in (
            "name",
            "description",
            "capabilities",
            "end_markets",
            "headquarters_country_codes",
        )
    )


def cosine(a, b):
    denominator = math.sqrt(sum(x * x for x in a) * sum(x * x for x in b))
    return sum(x * y for x, y in zip(a, b)) / denominator if denominator else 0.0


def retrieve(mention, companies, mode, research, limit=5):
    ranked = sorted(
        ((lexical_score(mention, c), c) for c in companies),
        key=lambda pair: (-pair[0], pair[1]["id"]),
    )
    selected = {
        c["id"]: {"company": c, "lexical": score, "semantic": None}
        for score, c in ranked[:limit]
        if score >= 0.55
    }
    if mode == "hybrid" and companies:
        query = research.embed(mention.name + " " + mention.context)
        semantic = sorted(
            ((cosine(query, research.embed(profile_text(c))), c) for c in companies),
            key=lambda pair: (-pair[0], pair[1]["id"]),
        )
        for score, c in semantic[:limit]:
            item = selected.setdefault(
                c["id"],
                {"company": c, "lexical": lexical_score(mention, c), "semantic": None},
            )
            item["semantic"] = score
    return list(selected.values())
