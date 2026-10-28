"""Escalation seam — Veritas hands off to Bardiel and Corgent when reasoning
alone cannot settle a claim.

Veritas, Bardiel, and Corgent answer different layers of the same question:

  * Veritas — adversarial *reasoning* on one runtime (propose / critique /
    rule). Verdicts: VERIFIED / REFUTED / UNCERTAIN.

  * Bardiel — Cortensor's *product/UX* agent (Virtual-first, ERC-8004), built
    on top of Corgent. It orchestrates the higher-level workflow (GAME/ACP
    flows, ecosystem presets) that a user-facing app runs.

  * Corgent — Cortensor's *core trust & execution* agent. It delegates to
    redundant miners and validates with PoI/PoUW + consensus + reputation.
    Verdicts: VALID / INVALID / RETRY / NEEDS_SPEC.

The escalation ladder: when Veritas returns UNCERTAIN, a product app routes
the case through Bardiel (orchestration), which delegates the trust decision
to Corgent (network consensus). Reasoning, then product workflow, then
network proof — each layer adds what the one before it cannot.

Bardiel's and Corgent's public request shapes are Draft (see Cortensor docs).
The payloads here express the documented concepts in a concrete request form,
not a verified wire schema. This is an integration point, not a live client.
"""

from __future__ import annotations

from veritas.pipeline import Case

RELIABILITY_TIERS = ("fast", "safe", "oracle")
BARDIEL_WORKFLOWS = ("game", "acp", "erc8004")
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


def bardiel_request(
    question: str,
    claimed_answer: str,
    workflow: str = "game",
) -> dict:
    """Render a Bardiel-level orchestration request.

    Bardiel is the product layer: it does not re-derive the trust decision,
    it wraps the case in the app's workflow (GAME/ACP/ERC-8004) and delegates
    the actual verification to Corgent. Shape is illustrative (Draft), not a
    verified wire schema.
    """
    if workflow not in BARDIEL_WORKFLOWS:
        raise ValueError(f"workflow must be one of {BARDIEL_WORKFLOWS}")
    return {
        "operation": "resolve_uncertain",
        "workflow": workflow,
        "task": {"prompt": question},
        "claim": {"output": claimed_answer},
        "delegate_to": "corgent",
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


def escalation_plan(case: Case) -> dict | None:
    """Build the full Veritas -> Bardiel -> Corgent escalation ladder.

    Returns ``None`` unless the verdict is UNCERTAIN (the only state where
    reasoning is exhausted and escalation is warranted).
    """
    verdict = case.verdict
    if verdict is None or verdict.status.upper() != "UNCERTAIN":
        return None
    claimed_answer = case.claim.answer if case.claim is not None else ""
    return {
        "trigger": "veritas verdict == UNCERTAIN (reasoning exhausted)",
        "route": [
            {
                "layer": "bardiel",
                "role": "product/UX orchestration (GAME/ACP flow)",
                "request": bardiel_request(case.question, claimed_answer),
            },
            {
                "layer": "corgent",
                "role": "network consensus + proof (PoI/PoUW, redundant miners)",
                "request": validate_request(case.question, claimed_answer),
            },
        ],
        "expected_verdicts": list(CORGENT_VERDICTS),
    }


def relationship() -> dict:
    """Machine-readable statement of how Veritas, Bardiel, and Corgent fit."""
    return {
        "veritas": {
            "role": "adversarial reasoning (propose / critique / rule)",
            "question": "does this answer survive hostile cross-examination?",
            "verdicts": list(VERITAS_VERDICTS),
        },
        "bardiel": {
            "role": "product/UX orchestration (GAME/ACP), built on Corgent",
            "question": "how should the app surface and act on this uncertainty?",
        },
        "corgent": {
            "role": "network consensus + proof (PoI/PoUW, redundant miners)",
            "question": "was this computed consistently and within spec?",
            "verdicts": list(CORGENT_VERDICTS),
        },
        "escalation": "UNCERTAIN -> Bardiel orchestrates -> Corgent validates",
    }
