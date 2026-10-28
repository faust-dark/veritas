"""Render a Case into human-readable Markdown and machine-readable JSON."""

from __future__ import annotations

import json
from dataclasses import asdict

from veritas.pipeline import Case

_STATUS_ICON = {"VERIFIED": "PASS", "REFUTED": "FAIL", "UNCERTAIN": "???"}


def render_json(case: Case) -> str:
    return json.dumps(asdict(case), indent=2, ensure_ascii=False, default=str)


def render_markdown(case: Case) -> str:
    lines = [
        "# Veritas — adversarial verification report",
        "",
        f"**Case:** `{case.case_id}`",
        "",
        f"**Question:** {case.question}",
        "",
    ]

    if case.claim is not None:
        c = case.claim
        lines += [
            "## 1. Proposal",
            "",
            f"- **Answer:** {c.answer}",
            f"- **Confidence:** {c.confidence}",
            f"- **Reasoning:** {c.reasoning}",
            "- **Key facts:**",
        ]
        lines += [f"  - {f}" for f in c.key_facts] or ["  - (none)"]
        lines.append("")

    if case.critique is not None:
        k = case.critique
        lines += [
            "## 2. Critique",
            "",
            f"- **Overall:** {k.overall}",
        ]
        for i, o in enumerate(k.objections, 1):
            lines.append(
                f"- **{i}. [{o.severity}] ({o.target})** {o.argument}"
                + ("  *(needs fact check)*" if o.requires_fact_check else "")
            )
        if not k.objections:
            lines.append("- (no objections raised)")
        lines.append("")

    if case.verdict is not None:
        v = case.verdict
        icon = _STATUS_ICON.get(v.status.upper(), "???")
        lines += [
            f"## 3. Verdict — {icon} ({v.status})",
            "",
            f"- **Score:** {v.score}",
            f"- **Rationale:** {v.rationale}",
        ]
        if v.surviving_objections:
            lines.append("- **Surviving objections:**")
            lines += [f"  - {o}" for o in v.surviving_objections]
        if v.evidence:
            lines.append("- **Evidence bundle:**")
            lines += [f"  - {e}" for e in v.evidence]
        lines.append("")

    if case.escalation:
        lines += [
            "## Escalation — Veritas → Bardiel → Corgent",
            "",
            f"- **Trigger:** {case.escalation.get('trigger', '')}",
            "- **Expected Corgent verdicts:** "
            + ", ".join(case.escalation.get("expected_verdicts", [])),
        ]
        for step in case.escalation.get("route", []):
            lines.append(
                f"- **{step.get('layer')}** — {step.get('role')}: "
                f"`{json.dumps(step.get('request'), sort_keys=True)}`"
            )
        lines.append("")

    if case.stage_runs:
        lines += ["## Run audit trail", ""]
        for stage, run in case.stage_runs.items():
            lines.append(
                f"- `{stage}`: run_id={run['run_id']} "
                f"session={run['session_id']} state={run['run_state']}"
            )
        lines.append("")

    if case.stage_errors:
        lines += ["## Stage errors", ""]
        for stage, err in case.stage_errors.items():
            lines.append(f"- `{stage}`: {err}")
        lines.append("")

    return "\n".join(lines)
