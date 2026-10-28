"""Corgent seam — where Veritas hands off to Cortensor's trust agent.

Corgent (Cortensor's core trust & execution agent) and Veritas answer two
*different* questions about an output:

  * Corgent: "Was this computed by enough independent miners, consistently and
    within spec?" -> network consensus + PoI/PoUW proofs.
    Verdicts: VALID / INVALID / RETRY / NEEDS_SPEC.

  * Veritas: "Does this answer survive a hostile cross-examination?"
    -> adversarial reasoning (propose / critique / rule) on a single runtime.
    Verdicts: VERIFIED / REFUTED / UNCERTAIN.

Neither replaces the other. Veritas exhausts what *reasoning* can tell you;
Corgent settles what only *the network* can tell you (redundant miners,
consensus clustering, reputation weighting). This module renders the seam
between the two: when Veritas's Judge returns UNCERTAIN, the claim is a
candidate for Corgent `validate` — re-run on the network and compared.

Corgent's public request shapes are Draft (see Cortensor docs). The payloads
below express the documented concepts (delegate / validate, reliability tiers,
verdict vocabulary) in a concrete request form, not a verified wire schema.
Treat this as an integration point, not a live client.
"""

from __future__ import annotations

from veritas.pipeline import Case

RELIABILITY_TIERS = ("fast", "safe", "oracle")
CORGENT_VERDICTS = ("VALID", "INVALID", "RETRY", "NEEDS_SPEC")
VERITAS_VERDICTS = ("VERIFIED", "REFUTED", "UNCERTAIN")


def delegate_request(question: str, reliability_tier: str = "safe") -> dict:
    """Render a Corgent ``delegate`` request: run this question on the network
    with an explicit reliability tier."""
    if reliability_tier not in RELIABILITY_TIERS:
        raise ValueError(f"reliability_tier must be one of {RELIABILITY_TIERS}")
    return {
        "operation": "delegate",
        "task": {"prompt": question},
        "policy": {"reliability_tier": reliability_tier},
    }


def validate_request(question: str, claimed_answer: str) -> dict:
    """Render a Corgent ``validate`` request: verify a claimed result on-chain
    via redundant miners + PoI/PoUW instead of trusting one run."""
    return {
        "operation": "validate",
        "task": {"prompt": question},
        "claim": {"output": claimed_answer},
    }


def handoff(case: Case) -> dict | None:
    """Return a Corgent ``validate`` request when reasoning alone is exhausted.

    VERIFIED and REFUTED are settled by argument. UNCERTAIN is exactly where
    the network's redundant-compute + PoI/PoUW consensus adds the signal that
    reasoning cannot — so that is the only case we hand to Corgent.
    """
    verdict = case.verdict
    if verdict is None or verdict.status.upper() != "UNCERTAIN":
        return None
    claimed_answer = case.claim.answer if case.claim is not None else ""
    return validate_request(case.question, claimed_answer)


def relationship() -> dict:
    """Machine-readable statement of how Veritas complements Corgent."""
    return {
        "corgent": {
            "role": "network consensus + proof (PoI/PoUW, redundant miners)",
            "question": "was this computed consistently and within spec?",
            "verdicts": list(CORGENT_VERDICTS),
        },
        "veritas": {
            "role": "adversarial reasoning (propose / critique / rule)",
            "question": "does this answer survive hostile cross-examination?",
            "verdicts": list(VERITAS_VERDICTS),
        },
        "handoff": "when verdict == UNCERTAIN, delegate to Corgent validate",
    }
