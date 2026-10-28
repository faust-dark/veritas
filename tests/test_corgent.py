"""Offline tests for the Bardiel + Corgent escalation seam."""

from veritas import (
    bardiel_request,
    delegate_request,
    escalation_plan,
    handoff,
    relationship,
    validate_request,
)
from veritas.models import Claim, Verdict
from veritas.pipeline import Case


def _case_with_verdict(status: str) -> Case:
    case = Case(question="q?")
    case.claim = Claim(answer="A", reasoning="R", confidence=0.9)
    case.verdict = Verdict(
        status=status,
        score=0.5,
        rationale="r",
        surviving_objections=[],
        evidence=["e"],
    )
    return case


def test_delegate_request_shape():
    req = delegate_request("q?", reliability_tier="safe")
    assert req["operation"] == "delegate"
    assert req["task"]["prompt"] == "q?"
    assert req["policy"]["reliability_tier"] == "safe"


def test_delegate_request_rejects_unknown_tier():
    try:
        delegate_request("q?", reliability_tier="ludicrous")
    except ValueError:
        return
    raise AssertionError("expected ValueError for unknown tier")


def test_validate_request_shape():
    req = validate_request("q?", "the answer")
    assert req["operation"] == "validate"
    assert req["claim"]["output"] == "the answer"


def test_bardiel_request_shape():
    req = bardiel_request("q?", "the answer", workflow="game")
    assert req["operation"] == "resolve_uncertain"
    assert req["workflow"] == "game"
    assert req["claim"]["output"] == "the answer"
    assert req["delegate_to"] == "corgent"


def test_bardiel_request_rejects_unknown_workflow():
    try:
        bardiel_request("q?", "a", workflow="nonsense")
    except ValueError:
        return
    raise AssertionError("expected ValueError for unknown workflow")


def test_handoff_only_on_uncertain():
    assert handoff(_case_with_verdict("VERIFIED")) is None
    assert handoff(_case_with_verdict("REFUTED")) is None
    req = handoff(_case_with_verdict("UNCERTAIN"))
    assert req is not None
    assert req["operation"] == "validate"
    assert req["claim"]["output"] == "A"


def test_handoff_none_without_verdict():
    assert handoff(Case(question="q?")) is None


def test_escalation_plan_only_on_uncertain():
    assert escalation_plan(_case_with_verdict("VERIFIED")) is None
    assert escalation_plan(_case_with_verdict("REFUTED")) is None
    plan = escalation_plan(_case_with_verdict("UNCERTAIN"))
    assert plan is not None
    layers = [step["layer"] for step in plan["route"]]
    assert layers == ["bardiel", "corgent"]
    assert plan["route"][1]["request"]["operation"] == "validate"
    assert set(plan["expected_verdicts"]) == {"VALID", "INVALID", "RETRY", "NEEDS_SPEC"}


def test_escalation_plan_none_without_verdict():
    assert escalation_plan(Case(question="q?")) is None


def test_relationship_documents_complement():
    rel = relationship()
    assert set(rel["corgent"]["verdicts"]) == {"VALID", "INVALID", "RETRY", "NEEDS_SPEC"}
    assert set(rel["veritas"]["verdicts"]) == {"VERIFIED", "REFUTED", "UNCERTAIN"}
    assert "bardiel" in rel
    assert rel["escalation"] == "UNCERTAIN -> Bardiel orchestrates -> Corgent validates"
