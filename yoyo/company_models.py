"""Optional enrichment contracts. Values need evidence; unknown stays null."""

from datetime import date as Date
from decimal import Decimal
from typing import Literal

from pydantic import Field, model_validator

from .transcripts.models import Strict


class IndustryCode(Strict):
    system: str
    version: str
    code: str


class FinancialObservation(Strict):
    type: Literal["valuation", "funding_raised", "acquisition_price"]
    amount: Decimal = Field(ge=0, allow_inf_nan=False)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    date: Date | None = None
    basis: str
    source_id: str
    quote: str


class CompanyProfile(Strict):
    domain: str | None = None
    linkedin_url: str | None = None
    sector_id: str | None = None
    subsector_id: str | None = None
    description: str | None = None
    capabilities: list[str] | None = None
    end_markets: list[str] | None = None
    headquarters_country_codes: list[str] | None = None
    operating_country_codes: list[str] | None = None
    operating_region_codes: list[str] | None = None
    industry_codes: list[IndustryCode] | None = None
    ownership_status: str | None = None
    funding_stage: str | None = None
    financial_observations: list[FinancialObservation] | None = None
    field_evidence: dict[str, list[str]] = Field(default_factory=dict)

    @model_validator(mode="after")
    def require_evidence(self):
        for name in type(self).model_fields:
            if name != "field_evidence" and getattr(self, name) is not None:
                if not self.field_evidence.get(name):
                    raise ValueError(f"Evidence required for {name}")
        return self
