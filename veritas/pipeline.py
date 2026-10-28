"""Adversarial verification pipeline: Proposer -> Critic -> Judge.

Three OpenMinion subagents share one runtime. Each returns a typed result
(structured output). The coordinator feeds JSON between stages and records
every stage's run identity so the whole run is auditable.

Trust model: adversarial *reasoning*, not redundant compute. This is
deliberately different from (and complementary to) Corgent, which re-runs work
on independent miners and compares via PoI/PoUW. Veritas asks whether an
answer survives hostile cross-examination; Corgent asks whether it was
computed consistently by the network. See :mod:`veritas.corgent` for the seam.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from openminion import (
    Agent,
    AgentOutputValidationError,
    ProviderError,
    TurnTimeoutError,
    subagent,
)

from veritas.models import Claim, Critique, Verdict

# Concrete JSON shapes are embedded in every prompt: the single most reliable
# way to get a modest model to emit valid structured output (far stronger than
# prose field lists alone).
CLAIM_EXAMPLE = (
    '{"answer": "no, it is a myth", "reasoning": "because ...", '
    '"confidence": 0.9, "key_facts": ["fact one", "fact two"]}'
)
CRITIQUE_EXAMPLE = (
    '{"objections": [{"target": "answer", "severity": "major", '
    '"argument": "unsupported by evidence", "requires_fact_check": true}], '
    '"overall": "flawed"}'
)
VERDICT_EXAMPLE = (
    '{"status": "VERIFIED", "score": 0.9, "rationale": "the objection was '
    'dismissed because ...", "surviving_objections": [], "evidence": ["..."]}'
)

# Some models (notably DeepSeek's agentic variants) emit tool-call syntax such
# as DSML even when no tools are exposed. This clause suppresses that so the
# reply is a bare JSON object.
NO_TOOLS = (
    "Do not call any tools or emit tool-call syntax (such as DSML). Reply with "
    "the JSON object only."
)

PROPOSER_INSTRUCTIONS = (
    "You are a careful analyst. Answer the question directly and honestly.\n"
    "Return ONLY a single JSON object (no prose, no markdown fences) matching "
    "this exact shape:\n"
    f"{CLAIM_EXAMPLE}\n"
    'Fields: "answer" (string), "reasoning" (string), "confidence" (number '
    '0 to 1), "key_facts" (list of strings).\n'
    f"{NO_TOOLS}"
)

CRITIC_INSTRUCTIONS = (
    "You are a ruthless, skeptical critic. Given a question and a proposed "
    "claim (JSON), attack the claim: find unsupported assertions, factual "
    "errors, missing caveats, and overconfidence.\n"
    "Return ONLY a single JSON object (no prose, no markdown fences) matching "
    "this exact shape:\n"
    f"{CRITIQUE_EXAMPLE}\n"
    'Fields: "objections" (list of objects, each with "target" (string), '
    '"severity" (critical|major|minor), "argument" (string), '
    '"requires_fact_check" (boolean)), and "overall" (sound|flawed|unverifiable). '
    'If the claim is solid, return {"objections": [], "overall": "sound"}.\n'
    f"{NO_TOOLS}"
)

JUDGE_INSTRUCTIONS = (
    "You are an impartial judge. Given a question, a proposed claim (JSON) and "
    "a critique (JSON), rule whether the claim survives adversarial review.\n"
    "Return ONLY a single JSON object (no prose, no markdown fences) matching "
    "this exact shape:\n"
    f"{VERDICT_EXAMPLE}\n"
    'Fields: "status" (VERIFIED|REFUTED|UNCERTAIN), "score" (number 0 to 1), '
    '"rationale" (string), "surviving_objections" (list of strings), '
    '"evidence" (list of strings).\n'
    f"{NO_TOOLS}"
)


@dataclass
class Case:
    """One completed (or partially completed) verification run."""

    question: str
    case_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    claim: Claim | None = None
    critique: Critique | None = None
    verdict: Verdict | None = None
    stage_errors: dict[str, str] = field(default_factory=dict)
    stage_runs: dict[str, dict] = field(default_factory=dict)
    escalation: dict | None = None

    @property
    def ok(self) -> bool:
        return self.verdict is not None


def _run_typed(
    agent,
    message: str,
    stage: str,
    case: Case,
    timeout_seconds: float,
    schema_example: str,
):
    """Run one stage and coerce the reply to the agent's output type.

    Retries up to three times with a corrective hint (re-stating the exact
    JSON shape) when the model's reply is not valid JSON for the target
    schema. Provider and turn-timeout failures are recorded on the case
    instead of aborting the whole pipeline.
    """
    for attempt in range(1, 4):
        try:
            result = agent.run(message, timeout_seconds=timeout_seconds)
        except AgentOutputValidationError as exc:
            if attempt < 3:
                print(
                    f"[veritas] {stage}: reply was not valid JSON on attempt "
                    f"{attempt}, retrying ...",
                    flush=True,
                )
                message = (
                    f"{message}\n\nYour previous reply was not valid JSON for "
                    f"the required schema. Do not call tools or emit tool-call "
                    f"syntax. Reply with ONLY a JSON object in this exact "
                    f"shape:\n{schema_example}"
                )
                continue
            case.stage_errors[stage] = (
                f"AgentOutputValidationError (raw={exc.raw_text[:120]!r})"
            )
            return None
        except ProviderError as exc:
            code = getattr(exc, "code", "")
            message_ = getattr(exc, "message", exc)
            case.stage_errors[stage] = f"ProviderError {code}: {message_}"
            return None
        except TurnTimeoutError as exc:
            case.stage_errors[stage] = f"TurnTimeoutError: {exc}"
            return None

        case.stage_runs[stage] = {
            "run_id": result.run_id,
            "run_state": result.run_state,
            "session_id": result.session_id,
        }
        return result.output

    case.stage_errors[stage] = "AgentOutputValidationError after retries"
    return None


def adversarial_verify(
    question: str,
    *,
    agent_id: str | None = None,
    model: str | None = None,
    timeout_seconds: float = 180.0,
    session_id: str | None = None,
) -> Case:
    """Run the full Proposer -> Critic -> Judge pipeline on one question."""

    case = Case(question=question)
    child_timeout = int(timeout_seconds) if timeout_seconds else None
    print(f"[veritas] case {case.case_id} — verifying question", flush=True)

    try:
        with Agent(
            name="veritas-coordinator",
            agent_id=agent_id,
            model=model,
            session_id=session_id,
            tools=[],
        ) as coordinator:
            proposer = subagent(
                coordinator,
                name="proposer",
                instructions=PROPOSER_INSTRUCTIONS,
                output_type=Claim,
                model=model,
                tools=[],
                timeout_seconds=child_timeout,
            )
            print("[veritas] 1/3 proposer — answering ...", flush=True)
            claim = _run_typed(
                proposer, question, "proposer", case, timeout_seconds, CLAIM_EXAMPLE
            )
            case.claim = claim
            if claim is None:
                print(
                    f"[veritas] proposer failed: {case.stage_errors.get('proposer')}",
                    flush=True,
                )
                return case
            print(f"[veritas] proposer done — confidence {claim.confidence}", flush=True)

            critic = subagent(
                coordinator,
                name="critic",
                instructions=CRITIC_INSTRUCTIONS,
                output_type=Critique,
                model=model,
                tools=[],
                timeout_seconds=child_timeout,
            )
            critic_msg = (
                f"Question: {question}\n\n"
                f"Proposed claim (JSON):\n{claim.model_dump_json(indent=2)}"
            )
            print("[veritas] 2/3 critic — attacking ...", flush=True)
            critique = _run_typed(
                critic, critic_msg, "critic", case, timeout_seconds, CRITIQUE_EXAMPLE
            )
            case.critique = critique
            if critique is None:
                print(
                    f"[veritas] critic failed: {case.stage_errors.get('critic')}",
                    flush=True,
                )
                return case
            print(
                f"[veritas] critic done — {len(critique.objections)} objection(s), "
                f"overall {critique.overall}",
                flush=True,
            )

            judge = subagent(
                coordinator,
                name="judge",
                instructions=JUDGE_INSTRUCTIONS,
                output_type=Verdict,
                model=model,
                tools=[],
                timeout_seconds=child_timeout,
            )
            judge_msg = (
                f"Question: {question}\n\n"
                f"Proposed claim (JSON):\n{claim.model_dump_json(indent=2)}\n\n"
                f"Critique (JSON):\n{critique.model_dump_json(indent=2)}"
            )
            print("[veritas] 3/3 judge — ruling ...", flush=True)
            verdict = _run_typed(
                judge, judge_msg, "judge", case, timeout_seconds, VERDICT_EXAMPLE
            )
            case.verdict = verdict
            if verdict is None:
                print(
                    f"[veritas] judge failed: {case.stage_errors.get('judge')}",
                    flush=True,
                )
            else:
                print(
                    f"[veritas] judge done — {verdict.status} (score {verdict.score})",
                    flush=True,
                )
    except ProviderError as exc:
        code = getattr(exc, "code", "")
        message_ = getattr(exc, "message", exc)
        case.stage_errors["pipeline"] = f"ProviderError {code}: {message_}"
    except TurnTimeoutError as exc:
        case.stage_errors["pipeline"] = f"TurnTimeoutError: {exc}"

    return case
