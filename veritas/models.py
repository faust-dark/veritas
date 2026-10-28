"""Typed models for Veritas's adversarial verification pipeline.

Fields are deliberately loose (plain ``str`` / ``float``) and list fields
default to ``[]`` so a modest model such as ``gpt-oss-20b`` can still produce
a valid object — including when it omits an empty list. Case-normalisation
happens in :mod:`veritas.report`, not at the schema boundary.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class Claim(BaseModel):
    """A proposed answer to a factual question."""

    answer: str
    reasoning: str
    confidence: float
    key_facts: list[str] = Field(default_factory=list)


class Objection(BaseModel):
    """One challenge raised by the critic against the claim."""

    target: str
    severity: str
    argument: str
    requires_fact_check: bool = False


class Critique(BaseModel):
    """The critic's full assessment of a claim."""

    objections: list[Objection] = Field(default_factory=list)
    overall: str


class Verdict(BaseModel):
    """The judge's ruling after adversarial review."""

    status: str
    score: float
    rationale: str
    surviving_objections: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
