from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Segment(StrictModel):
    index: int = Field(ge=0)
    start: float = Field(ge=0, allow_inf_nan=False)
    end: float = Field(ge=0, allow_inf_nan=False)
    speaker: str | None
    text: str = Field(min_length=1)

    @model_validator(mode="after")
    def valid_range(self):
        if self.end <= self.start:
            raise ValueError("End must follow start")
        return self


class Source(StrictModel):
    episode_id: str
    title: str
    url: str | None = None
    parent_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    provenance: dict
    segments: list[Segment] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_indices(self):
        if len({s.index for s in self.segments}) != len(self.segments):
            raise ValueError("Duplicate segment indices")
        return self


class Finding(StrictModel):
    company: str = Field(min_length=1)
    person: str | None = None
    predicate: Literal["has_ceo", "reported_age"]
    statement: str = Field(min_length=1)
    segment_index: int
    quote: str = Field(min_length=1)
    speaker_label: str | None
    review_status: Literal["reference_pending_human_review"] = (
        "reference_pending_human_review"
    )


class Bundle(StrictModel):
    source: Source
    origin: str
    findings: list[Finding] = Field(min_length=1)
