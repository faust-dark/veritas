# Veritas — Building Blocks Tested & What We Learned

Hackathon #5 asks for two notes: which OpenMinion building blocks were used and
what worked or broke. This is the full, evidence-backed record. Everything
below was reproduced against **openminion 0.1.14** (the current PyPI release).

Provider note: all live-model runs used **DeepSeek (`deepseek-v4-flash`)** via
OpenMinion's OpenAI-compatible adapter, because Cortensor Portal access was not
available in the build environment. The code is provider-agnostic and was also
verified end-to-end on the zero-secret `echo` provider.

---

## 1. Building Blocks Tested

| Block | Where | Result |
|---|---|---|
| Agent / context manager | `pipeline.py` `Agent(...)` | Works. `name`, `agent_id`, `model`, `session_id`, `tools` all honored. |
| Delegation (`subagent`) | `pipeline.py` | Works. Proposer/Critic/Judge run as bounded subagents on one runtime. |
| Structured output (`output_type` + Pydantic) | `pipeline.py`, `probes.py` | Works when the prompt embeds a JSON example + retries on schema mismatch. |
| Custom tools (`@tool` + `forced_tools`) | `probes.py` | Works only after `idempotent=True` + an `approval_callback` (see finding 5). |
| Sessions | `probes.py` | `session_id` wiring works (`same_session=true`), but cross-turn recall did not reproduce (finding 6). |
| Memory | `probes.py` | Exercised via session recall; see finding 6. |
| Error handling | `pipeline.py` | `ProviderError`, `TurnTimeoutError`, `AgentOutputValidationError` all import and are caught cleanly. |
| Diagnostics | `Makefile` | `openminion doctor --check-turn` and `config init --provider echo` work. |
| Corgent seam | `corgent.py` | `handoff()` unit-tested; `UNCERTAIN` -> Corgent `validate` request. |

---

## 2. What Worked

- **The whole adversarial pipeline.** Proposer -> Critic -> Judge completed
  end-to-end with a real model and produced a `VERIFIED` verdict with score,
  rationale, surviving objections, and a 5-item evidence bundle. Exit code 0.
- **`_extract_json_object` recovery.** When the reply carried the agent-name
  envelope (finding 2) but the model emitted JSON, `output_type` still decoded
  correctly thanks to the fallback in `_coerce_output`.
- **Retry-on-schema-mismatch.** The `AgentOutputValidationError` carries
  `raw_text`, which is exactly what a corrective retry needs. One or two
  retries reliably pulled the model back to valid JSON.
- **Zero-secret bring-up.** `openminion config init --provider echo --force`
  then `python run.py verify` proves the full code path with no API key.

---

## 3. What Didn't (rough edges found)

### Finding 1 — No config = opaque error
`Agent()` with no config file raises
`openminion.base.config.manager.ConfigManagerError: config file not found`.
Repro: `python run.py verify` before running `openminion setup`.
- Expected: a clear "run `openminion setup` first" message, or a default echo
  config.
- Actual: a traceback from an internal module.
- `ConfigManagerError` is **not** a top-level export, so callers cannot catch
  it by name without importing an internal path. **Feedback:** expose a public
  `ConfigError` (or `OpenMinionSetupError`) at `openminion.*`.

### Finding 2 — Reply body is wrapped in `"<agent_name>: "`
`src/openminion/services/brain/post_execution/postprocess_response.py:261`
wraps every response as `f"{agent_name}: {response_text}"`. The raw body comes
back as `openminion: {"decision": "approve", ...}`.
- This breaks `output_type`'s primary `model_validate_json`; only the
  `_extract_json_object` fallback saves it, and only if the model emitted JSON
  at all.
- **Feedback:** return the clean body (or a `raw_body` field) so structured
  output doesn't depend on a substring-recovery heuristic.

### Finding 3 — Bare `Agent()` exposes 91 default tools
A plain `Agent()` (no `tools=`) exposes the default-visible tool catalog. An
agentic model then emits tool calls, which hit policy confirmation gates and
stall the turn (first `verify` run timed out).
- **Fix we applied:** pass `tools=[]` to every pure text/JSON agent.
- **Feedback:** for `output_type`-typed runs, default to `tools=[]`; document
  this footgun in the structured-output quickstart.

### Finding 4 — Tool-hungry models emit DSML even with `tools=[]`
`deepseek-v4-flash` (and `-pro`) emit `DSML` tool-call syntax (`<｜｜DSML｜｜ invoke
name="search">...`) even when no tools are exposed. The runtime passes this
syntax through as reply text instead of rejecting it.
- The Judge stage and the session probe both hit this.
- **Fix we applied:** an explicit "do not call tools or emit tool-call syntax"
  clause in every stage prompt.
- **Feedback:** detect/strip or reject tool-call syntax when the tool list is
  empty.

### Finding 5 — `@tool` functions gate on confirmation by default
A user `@tool` is WRITE-class (`ENFORCE_SAFE_CONFIRM`) even when the function
has no side effects. `forced_tools` then surfaces "Policy confirmation
required" instead of executing.
- `idempotent=True` alone is not enough (still confirmed, now
  `ENFORCE_SAFE_CONFIRM`). A successful forced call needs an
  `approval_callback` that approves.
- **Feedback:** add a first-class read-only marker to `@tool` so side-effect
  free functions don't gate, and document the `approval_callback` pattern in
  the tool quickstart (the minimal example would otherwise appear broken).

### Finding 6 — Cross-turn session recall did not reproduce
`Agent(session_id=...)` + two `.run()` calls report the same `session_id`, but
the second turn did not recall a fact stored on the first turn ("project
codename is cobalt" -> "I don't have a confirmed project codename"). This is
the docs' own `sessions.py` pattern.
- **Feedback:** worth investigating whether session context/history is
  actually injected into subsequent SDK turns (memory_v2 / contextctl), or
  whether a `resume`/continuation call is required.

### Finding 7 — Freshness verifier hijacks recall questions
Asking "What is the launch color?" (a recall question) tripped the freshness
guard: the turn refused with "Missing live-data evidence for a
freshness-sensitive answer" instead of answering from the session.
- **Feedback:** the freshness verifier should not fire for questions that are
  answerable from session context.

### Finding 8 — Schema tolerance for weak models
Pydantic list fields without defaults fail when a model omits an empty list.
Giving every list field `Field(default_factory=list)` (and keeping `status` /
`severity` / `overall` as plain strings, normalized in the report layer) made
the pipeline resilient. Small change, large reliability gain.

---

## 4. What We Learned

1. **The JSON-example-in-prompt trick is decisive.** Embedding one concrete
   JSON instance per schema made structured output reliable with a modest
   model, where prose field lists alone were not.
2. **Restrict tools aggressively.** For any turn that must return clean text
   or JSON, pass `tools=[]` AND add a "do not call tools" clause — agentic
   models will otherwise wander into tool-call syntax.
3. **Provider matters.** `deepseek-v4-pro` (agentic) was unreliable for
   structured JSON; `deepseek-v4-flash` (chat) was reliable. For the demo we
   recommend a plain chat model (Cortensor `gpt-oss-20b`, or `deepseek-v4-flash`).
4. **The public SDK surface is good but has sharp edges** around config
   bring-up (finding 1), structured-output envelope (finding 2), and tool
   confirmation (finding 5). These are one-line docs fixes and one-field API
   additions, not architectural problems.
5. **Corgent and Veritas are cleanly complementary.** Corgent answers "was it
   computed consistently by the network"; Veritas answers "does it survive
   hostile cross-examination". The `UNCERTAIN -> Corgent validate` handoff is a
   natural seam, not a conflict.

---

## 5. Reproduction

```bash
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
openminion setup --provider deepseek --model deepseek-v4-flash --no-chat   # or your provider
export DEEPSEEK_API_KEY=...                                                 # or provider key
python -m pytest tests -q                                                   # 11 offline tests
python run.py verify --out demo/out                                         # live pipeline
python run.py probe tools && python run.py probe session && python run.py probe structured
```

Findings 1–8 were each reproduced by the steps in their respective entries.
