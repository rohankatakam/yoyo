from typing import Literal
from pydantic import Field, model_validator
from ..transcripts.models import Strict


class Mention(Strict):
    name: str
    context: str
    source_id: str
    domain: str | None = None
    linkedin_url: str | None = None


class Decision(Strict):
    outcome: Literal["MATCH", "NEW_COMPANY", "UNRESOLVED", "NOT_COMPANY"]
    entity_type: Literal[
        "company", "person", "product", "brand", "division", "sector", "uncertain"
    ]
    company_id: str | None
    reason: str
    evidence: list[str]

    @model_validator(mode="after")
    def coherent(self):
        if (self.outcome == "MATCH") != (self.company_id is not None):
            raise ValueError("Only MATCH can include a company ID")
        if self.outcome in {"MATCH", "NEW_COMPANY"} and self.entity_type != "company":
            raise ValueError("Only companies enter the ledger")
        if not self.evidence:
            raise ValueError("Decision needs evidence references")
        return self


class Citation(Strict):
    source: int
    passage: int = Field(ge=0)


class Attribute(Strict):
    field: str
    value: str | list[str]
    citations: list[Citation] = Field(min_length=1)


class Enrichment(Strict):
    entity_type: Literal[
        "company", "product", "brand", "division", "sector", "uncertain"
    ]
    canonical_name: str | None
    identity_citations: list[Citation]
    attributes: list[Attribute]
    reason: str


class EntityType(Strict):
    kind: Literal[
        "company", "person", "product", "brand", "division", "sector", "uncertain"
    ]
    reason: str
