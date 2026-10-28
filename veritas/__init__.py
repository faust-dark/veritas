"""Veritas: adversarial verification on the OpenMinion 0.1 SDK.

A question is answered by a *Proposer*, attacked by a *Critic*, and ruled on
by a *Judge*. All three are OpenMinion subagents that share one runtime and
return typed (structured) results, so every run produces an auditable
evidence bundle instead of a bare answer.

Veritas is the *reasoning* side of trust. It complements — and hands off to —
Corgent, Cortensor's core trust & execution agent, which covers the *network
consensus + proof* side. See :mod:`veritas.corgent`.
"""

from veritas.corgent import (
    BARDIEL_WORKFLOWS,
    CORGENT_VERDICTS,
    VERITAS_VERDICTS,
    bardiel_request,
    delegate_request,
    escalation_plan,
    handoff,
    relationship,
    validate_request,
)
from veritas.models import Claim, Critique, Objection, Verdict
from veritas.pipeline import Case, adversarial_verify

__all__ = [
    "BARDIEL_WORKFLOWS",
    "CORGENT_VERDICTS",
    "Case",
    "Claim",
    "Critique",
    "Objection",
    "VERITAS_VERDICTS",
    "Verdict",
    "adversarial_verify",
    "bardiel_request",
    "delegate_request",
    "escalation_plan",
    "handoff",
    "relationship",
    "validate_request",
]

__version__ = "0.1.0"
