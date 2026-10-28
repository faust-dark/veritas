"""Offline unit tests: no model, network, or config required."""

import json

from veritas.models import Claim, Critique, Objection, Verdict
from veritas.pipeline import Case
from veritas.report import render_json, render_markdown


def test_claim_roundtrip():
    c = Claim(answer="Yes", reasoning="Because", confidence=0.9, key_facts=["f1"])
    data = json.loads(c.model_dump_json())
    assert data["answer"] == "Yes"
    assert data["confidence"] == 0.9
    assert data["key_facts"] == ["f1"]


def test_critique_roundtrip():
    c = Critique(
        objections=[
            Objection(target="answer", severity="critical", argument="unsupported")
        ],
        overall="flawed",
    )
    assert c.overall == "flawed"
    assert c.objections[0].severity == "critical"


def test_verdict_roundtrip():
    v = Verdict(
        status="REFUTED",
        score=0.2,
        rationale="r",
        surviving_objections=["o"],
        evidence=["e"],
    )
    assert v.status == "REFUTED"
    assert v.score == 0.2


def test_case_ok_flag():
    case = Case(question="q")
    assert not case.ok
    case.verdict = Verdict(status="VERIFIED", score=0.9, rationale="r")
    assert case.ok


def test_render_json_and_markdown():
    case = Case(question="q?", case_id="abc123")
    case.claim = Claim(answer="A", reasoning="R", confidence=0.8, key_facts=["k"])
    case.critique = Critique(
        objections=[Objection(target="answer", severity="major", argument="x")],
        overall="flawed",
    )
    case.verdict = Verdict(
        status="UNCERTAIN",
        score=0.5,
        rationale="r",
        surviving_objections=["x"],
        evidence=["e"],
    )
    js = render_json(case)
    assert "abc123" in js
    data = json.loads(js)
    assert data["verdict"]["status"] == "UNCERTAIN"
    assert data["claim"]["answer"] == "A"
    assert data["critique"]["objections"][0]["severity"] == "major"
    md = render_markdown(case)
    assert "q?" in md
    assert "UNCERTAIN" in md
    assert "Evidence bundle" in md
