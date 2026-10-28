# Veritas

Adversarial verification on the [OpenMinion](https://openminion.com) 0.1 SDK.

Veritas answers a question the way you'd want a *trusted* system to answer it:
not with a single model's say-so, but by making three agents argue it out and
handing you the evidence.

```
Question ──► Proposer ──► Critic ──► Judge ──► Verdict + evidence bundle
             (answers)     (attacks)  (rules)
```

All three are OpenMinion **subagents** sharing one runtime. Each returns a
**typed (structured) result**, and the run is recorded end-to-end so the final
output is an auditable evidence bundle — not a bare answer.

## Veritas and Corgent

[Corgent](https://docs.cortensor.network/community-and-ecosystem/products-and-agents/corgent)
is Cortensor's core trust & execution agent — the ERC-8004-native oracle that
delegates work to redundant miners and validates results with
PoI/PoUW, consensus, and node reputation. It is already built on the network.
Veritas does **not** reimplement Corgent. The two answer different questions
and are designed to be complementary:

| | Corgent | Veritas |
|---|---|---|
| Trust mechanism | network consensus + proof (redundant miners, PoI/PoUW) | adversarial reasoning (propose / critique / rule) |
| Question it answers | "was this computed consistently and within spec?" | "does this answer survive a hostile cross-examination?" |
| Verdicts | `VALID` / `INVALID` / `RETRY` / `NEEDS_SPEC` | `VERIFIED` / `REFUTED` / `UNCERTAIN` |
| Depends on | the Cortensor network (miners, sessions, validators) | any OpenMinion provider — even one local model |
| Output | proof signals (consensus, reputation, integrity) | an interpretable reasoning trail (objections that survived, rationale) |

In one line: **Corgent proves the answer was computed consistently by enough
miners; Veritas proves the answer survives hostile cross-examination.** Corgent
is the consensus; Veritas is the argument.

Between them sits **Bardiel**, Cortensor's product/UX agent (Virtual-first,
ERC-8004), built on top of Corgent. It orchestrates the higher-level workflow
a user-facing app runs — GAME/ACP flows, ecosystem presets — and delegates the
trust decision to Corgent.

They meet at the seam where reasoning runs out. When Veritas's Judge returns
`UNCERTAIN`, the case escalates up the ladder:

```
UNCERTAIN ──► Bardiel (product orchestration) ──► Corgent (network consensus)
```

`veritas.corgent.escalation_plan(case)` renders the full route as concrete
requests; `handoff(case)` returns just the Corgent `validate` request. The CLI
attaches the escalation plan to the report automatically on `UNCERTAIN`.

## Why this is interesting

- **Complementary, not a clone.** Veritas deliberately uses a *single* runtime
  and adversarial roles, not redundant miners — it fills the gap Corgent
  explicitly leaves open ("agents still think; Corgent helps them be sure").
  Veritas is the reasoning side; Corgent is the proof side.
- **Self-contained.** No external APIs, no database, no scraping. A single
  `python run.py verify` runs the whole pipeline on whatever OpenMinion
  provider you have configured.
- **Deep SDK use.** Delegation (`subagent`), structured output
  (`output_type` + Pydantic), session identity, and the public error types
  (`ProviderError`, `TurnTimeoutError`, `AgentOutputValidationError`) are all
  exercised on the happy path and the failure path.
- **Honest.** When the model can't decide, Veritas says `UNCERTAIN` instead of
  bluffing — and hands the case to Corgent's consensus layer instead of
  guessing.

## How it uses the OpenMinion SDK

The whole workflow is ~20 lines of SDK. One `Agent` context manager owns the
runtime; three `subagent()` children do the work; each declares an
`output_type` so the reply is decoded into a typed object:

```python
from openminion import Agent, subagent

with Agent(name="veritas-coordinator", tools=[]) as coordinator:
    proposer = subagent(coordinator, name="proposer",
                        instructions=PROPOSER_INSTRUCTIONS,
                        output_type=Claim, tools=[])
    claim = proposer.run(question, timeout_seconds=60).output      # typed Claim

    critic = subagent(coordinator, name="critic", instructions=CRITIC_INSTRUCTIONS,
                      output_type=Critique, tools=[])
    critique = critic.run(f"...{claim.model_dump_json()}").output  # typed Critique

    judge = subagent(coordinator, name="judge", instructions=JUDGE_INSTRUCTIONS,
                     output_type=Verdict, tools=[])
    verdict = judge.run(f"...{critique.model_dump_json()}").output  # typed Verdict
```

The SDK blocks in play: `Agent` (session identity + context manager),
`subagent` (delegation), `output_type` (structured output), `.run()` →
`AgentRunResult` (`.output`, `.run_id`, `.run_state`, `.session_id`), and the
public error types (`ProviderError`, `TurnTimeoutError`,
`AgentOutputValidationError`) handled around each stage.

## Quickstart

```bash
# 1. install the SDK and configure a provider
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
openminion setup            # pick cortensor, ollama, openai, ... — any provider

# 2. sanity-check the runtime
openminion doctor --check-turn

# 3. run the pipeline (one bounded question)
python run.py verify "Is it true that humans only use 10% of their brains?"

# 4. write the report + evidence bundle to disk
python run.py verify "..." --out demo/out
```

With no provider configured you can still verify the wiring using the
zero-secret `echo` provider (it proves the code paths; it cannot produce a
model answer):

```bash
openminion config init --provider echo --force
python run.py verify
```

### Provider notes

- **Cortensor** (default for this hackathon): `openminion setup --provider cortensor --model gpt-oss-20b`
  and set `CORTENSOR_API_KEY`. The completion-style backend is what the SDK
  defaults to for `providers.cortensor`.
- **Ollama** (local, no key): `openminion setup --provider ollama --model qwen2.5:7b`.
- Any other provider (OpenAI, Anthropic, DeepSeek, Groq, ...) works the same —
  Veritas is provider-agnostic.

Verified end-to-end on **`deepseek-v4-flash`** (openminion 0.1.14). Avoid
`deepseek-v4-pro` for structured output — it's agentic and emits tool-call
syntax. Prefer a plain chat model (Cortensor `gpt-oss-20b` or
`deepseek-v4-flash`) for the demo. See `FINDINGS.md` for the full record.

## Running the building-block probes

Each OpenMinion building block also has a one-line probe you can run in
isolation (and which backs the findings in `FINDINGS.md`):

```bash
python run.py probe tools       # @tool decorator + forced tool selection
python run.py probe session     # session continuity across turns
python run.py probe structured  # output_type -> Pydantic decoding
python run.py probe error       # public exception-type surface
python run.py probe version     # SDK version
```

## Project layout

```
veritas/
├── run.py                 # CLI entrypoint
├── veritas/
│   ├── models.py          # Claim / Objection / Critique / Verdict (Pydantic)
│   ├── pipeline.py        # Proposer -> Critic -> Judge orchestration
│   ├── corgent.py         # Bardiel + Corgent escalation seam (escalation_plan, handoff)
│   ├── report.py          # Markdown + JSON rendering of the evidence bundle
│   ├── probes.py          # per-building-block demonstrations
│   └── cli.py             # argparse interface
├── tests/                 # offline unit tests (no model/network)
├── FINDINGS.md            # Building Blocks Tested + What We Learned
├── demo/DEMO_SCRIPT.md    # word-for-word 2-minute demo script
├── Makefile               # make setup / doctor / demo / test
├── pyproject.toml         # packaging + `veritas` console script
└── requirements.txt       # openminion==0.1.14
```

## Building blocks exercised

| Block | Where | How |
|---|---|---|
| Agent / SDK | `pipeline.py` | `Agent(...)` context manager, `agent_id`, `model` override |
| Delegation | `pipeline.py` | `subagent(parent, ...)` for proposer/critic/judge |
| Structured output | `pipeline.py`, `probes.py` | `output_type=Claim/Critique/Verdict` |
| Tools | `probes.py` | `@tool` decorator + `forced_tools` |
| Sessions | `probes.py` | shared `session_id` continuity |
| Memory | `probes.py` | cross-turn recall in one session |
| Error handling | `pipeline.py` | `ProviderError` / `TurnTimeoutError` / `AgentOutputValidationError` |
| Diagnostics | `Makefile` | `openminion doctor --check-turn`, `config init` |
| Escalation seam | `corgent.py` | `escalation_plan()`: `UNCERTAIN` → Bardiel → Corgent |

## Tests

```bash
pip install pytest
python -m pytest tests -q
```

Offline unit tests cover the typed models, the case model, the Corgent handoff
logic, and report rendering — no model or network required.

## License

MIT — see LICENSE.
