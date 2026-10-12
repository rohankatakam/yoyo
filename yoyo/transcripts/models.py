from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Word(Strict):
    text: str
    start: float | None = Field(default=None, ge=0)
    end: float | None = Field(default=None, ge=0)


class Segment(Strict):
    id: str
    index: int = Field(ge=0)
    start: float | None = Field(default=None, ge=0)
    end: float | None = Field(default=None, ge=0)
    text: str = Field(min_length=1)
    speaker: str | None = None
    words: list[Word] = Field(default_factory=list)


class Transcript(Strict):
    normalization_version: str = "segments-v2"
    provider: str
    external_id: str
    language: str | None = None
    duration_seconds: float | None = Field(default=None, gt=0)
    coverage: Literal["full", "partial"]
    timing_status: Literal["available", "missing", "partial"]
    segments: list[Segment] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_segments(self):
        previous = -1.0
        ids, indices = set(), set()
        for segment in self.segments:
            if segment.id in ids or segment.index in indices:
                raise ValueError("Duplicate segment ID/index")
            ids.add(segment.id)
            indices.add(segment.index)
            if (segment.start is None) != (segment.end is None):
                raise ValueError("Incomplete timestamp pair")
            if segment.start is not None:
                if segment.start < previous or segment.end <= segment.start:
                    raise ValueError("Invalid or unordered timestamps")
                previous = segment.start
                if self.duration_seconds and segment.end > self.duration_seconds + 1:
                    raise ValueError("Segment exceeds metadata duration")
            previous_word = -1.0
            for word in segment.words:
                if (word.start is None) != (word.end is None):
                    raise ValueError("Incomplete word timing")
                if word.start is None:
                    continue
                if segment.start is None:
                    raise ValueError("Word timing without segment timing")
                if word.start < previous_word or word.end < word.start:
                    raise ValueError("Invalid word timing")
                if word.start < segment.start - 0.1 or word.end > segment.end + 0.1:
                    raise ValueError("Word outside segment")
                previous_word = word.start
        timed = sum(s.start is not None for s in self.segments)
        expected = (
            "available"
            if timed == len(self.segments)
            else "missing"
            if timed == 0
            else "partial"
        )
        if expected != self.timing_status:
            raise ValueError("Incorrect timing status")
        if (
            self.coverage == "full"
            and self.duration_seconds
            and timed == len(self.segments)
        ):
            if self.segments[0].start > max(30, 0.1 * self.duration_seconds):
                raise ValueError("Transcript beginning appears truncated; mark partial")
            last = max(s.end for s in self.segments)
            if abs(last - self.duration_seconds) > max(30, 0.1 * self.duration_seconds):
                raise ValueError("Transcript appears truncated; mark partial")
        return self
