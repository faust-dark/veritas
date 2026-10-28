"""Focused demonstrations of individual OpenMinion building blocks.

Each probe is independent so one failing block does not hide the others. They
double as the evidence base for FINDINGS.md: run ``veritas probe <name>`` to
see a single block in isolation.
"""

from __future__ import annotations

from openminion import (
    Agent,
    AgentOutputValidationError,
    ProviderError,
    TurnTimeoutError,
    tool,
)


def version() -> str:
    import openminion

    return openminion.__version__


def tools_probe(agent_id: str | None = None) -> dict:
    """Demonstrate a decorated custom tool and forced tool selection."""

    @tool(idempotent=True)
    def lookup_order(order_id: str) -> str:
        """Return the current status for one order."""

        return f"order {order_id}: ready"

    with Agent(
        agent_id=agent_id,
        instructions="Use lookup_order and answer in one sentence.",
        tools=[lookup_order],
        forced_tools=["lookup_order"],
        session_id="veritas-probe-tools",
    ) as agent:
        # Auto-approve the tool's policy confirmation so the forced call
        # actually executes (see FINDINGS.md: user @tool functions are
        # WRITE-class by default and hit a confirmation gate).
        result = agent.run(
            "Check order A-104",
            approval_callback=lambda _tool, _args, _id: True,
        )
    return {
        "text": result.text,
        "session_id": result.session_id,
        "run_id": result.run_id,
        "run_state": result.run_state,
    }


def session_probe(agent_id: str | None = None) -> dict:
    """Demonstrate session continuity: a fact stored on one turn is recalled
    on the next turn in the same session."""

    with Agent(
        agent_id=agent_id,
        instructions=(
            "You are a conversational assistant. Do not call tools or emit "
            "tool-call syntax. Answer directly from the conversation history."
        ),
        session_id="veritas-probe-session",
        tools=[],
    ) as agent:
        first = agent.run("Remember that the project codename is 'cobalt'.")
        second = agent.run("What is the project codename?")
    return {
        "first_session": first.session_id,
        "second_session": second.session_id,
        "same_session": first.session_id == second.session_id,
        "first_text": first.text,
        "second_text": second.text,
    }


def structured_probe(agent_id: str | None = None) -> dict:
    """Demonstrate structured output decoding into a Pydantic model."""

    from pydantic import BaseModel

    class Review(BaseModel):
        decision: str
        reason: str

    with Agent(
        agent_id=agent_id,
        instructions="Return JSON with string fields named decision and reason.",
        output_type=Review,
        tools=[],
    ) as agent:
        result = agent.run("Approve a demo with passing tests.")
    return {"decision": result.output.decision, "reason": result.output.reason}


def error_surface_probe() -> dict:
    """Prove the public exception types are importable and available for the
    caller to catch. (The pipeline itself exercises them on real failures.)"""

    return {
        "exports": {
            "ProviderError": ProviderError.__name__,
            "TurnTimeoutError": TurnTimeoutError.__name__,
            "AgentOutputValidationError": AgentOutputValidationError.__name__,
            "tool": callable(tool),
        }
    }
