# Veritas demo script (target: 2 minutes)

Run this word-for-word while recording. Adjust the question if you want a
cleaner VERIFIED/REFUTED split.

## 0. Before recording

```bash
cd veritas
source .venv/bin/activate
openminion doctor --check-turn          # prove the runtime is healthy
```

## 1. The hook (15s)

"Veritas answers a question the way you'd want a trusted system to: not with
one model's opinion, but by making three agents argue it out. A Proposer
answers, a Critic attacks, and a Judge rules with an evidence bundle — all on
the OpenMinion 0.1 SDK."

## 2. Run it (30s)

```bash
python run.py verify "Is it true that humans only use 10% of their brains?" --out demo/out
```

While it runs, narrate: "Each stage is a bounded OpenMinion subagent with a
typed output contract, so every run leaves an audit trail."

## 3. Read the verdict (30s)

Show `demo/out/verdict.md` (or the console output). Point at:
- the Proposer's answer and confidence,
- the Critic's objections (severity + target),
- the Judge's status (VERIFIED / REFUTED / UNCERTAIN), score, and evidence list.

"Notice it doesn't just say 'yes' or 'no' — it says *why*, and it keeps the
objections that survived review."

## 4. Show the evidence bundle (20s)

```bash
cat demo/out/verdict.json
```

"Structured JSON, machine-readable, with per-stage run IDs. That's the
auditable part."

## 5. Show the building blocks (25s)

```bash
python run.py probe tools
python run.py probe structured
```

"Same SDK: a custom forced tool (auto-approved through the policy gate) and
typed output, each runnable in isolation. The session probe surfaced a real
continuity gap we reported in FINDINGS.md — that's the kind of rough edge this
hackathon is for."

## 6. Close (10s)

"One question in, three agents, one auditable verdict. Source is in the repo
with setup instructions — fork it, star OpenMinion, and try your own question."
