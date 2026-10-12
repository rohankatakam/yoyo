from typing import Literal

from pydantic import Field

from .transcripts.models import Strict


class Participant(Strict):
    kind: Literal["company", "person"]
    name: str = Field(min_length=1)
    role: Literal["subject", "object", "mentioned"]
    # IDs are assigned/looked up by application code, never supplied by the model.


class Quote(Strict):
    segment_id: str
    quote: str = Field(min_length=1)
    role: Literal["support", "context", "attribution"] = "support"


class Candidate(Strict):
    text: str = Field(min_length=1)
    predicate: str = Field(min_length=1)
    participants: list[Participant] = Field(min_length=1)
    anchor_segment_id: str
    speaker_label: str | None
    quotes: list[Quote] = Field(min_length=1)
    rationale: str = Field(min_length=1, max_length=1200)
    context: Literal["actual", "sponsor", "hypothetical", "unclear"]


class Candidates(Strict):
    claims: list[Candidate]


class Annotation(Strict):
    time_class: Literal["FORWARD_LOOKING", "NOT_FORWARD_LOOKING", "UNCLEAR"]
    supporting_segment_ids: list[str] = Field(min_length=1)
    rationale: str = Field(min_length=1, max_length=1200)


class Classified(Strict):
    claim_key: str
    annotation: Annotation


class Classifications(Strict):
    claims: list[Classified]
