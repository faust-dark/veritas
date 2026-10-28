"""Command-line interface for Veritas."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from veritas import probes
from veritas.corgent import escalation_plan
from veritas.pipeline import adversarial_verify
from veritas.report import render_json, render_markdown

DEFAULT_QUESTION = "Is it true that humans only use 10% of their brains?"


def _cmd_verify(args: argparse.Namespace) -> int:
    case = adversarial_verify(
        args.question,
        agent_id=args.agent,
        model=args.model,
        timeout_seconds=args.timeout,
        session_id=args.session,
    )
    # When reasoning alone cannot settle the claim, attach the escalation
    # ladder (Veritas -> Bardiel -> Corgent) so the report shows it.
    if case.verdict is not None and case.verdict.status.upper() == "UNCERTAIN":
        case.escalation = escalation_plan(case)
    print(render_json(case) if args.json else render_markdown(case))
    if args.out:
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        (out / "verdict.md").write_text(render_markdown(case), encoding="utf-8")
        (out / "verdict.json").write_text(render_json(case), encoding="utf-8")
        print(f"\nWrote {out / 'verdict.md'} and {out / 'verdict.json'}")
    return 0 if case.ok else 2


def _cmd_probe(args: argparse.Namespace) -> int:
    try:
        if args.probe == "tools":
            payload = probes.tools_probe(args.agent)
        elif args.probe == "session":
            payload = probes.session_probe(args.agent)
        elif args.probe == "structured":
            payload = probes.structured_probe(args.agent)
        elif args.probe == "error":
            payload = probes.error_surface_probe()
        else:  # version
            payload = {"version": probes.version()}
    except Exception as exc:  # noqa: BLE001 - surface any provider/runtime failure
        print(f"probe failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="veritas",
        description="Adversarial verification on the OpenMinion 0.1 SDK.",
    )
    parser.add_argument("--agent", default=None, help="Configured agent id")
    parser.add_argument("--model", default=None, help="Override the model id")
    sub = parser.add_subparsers(dest="command", required=True)

    verify = sub.add_parser("verify", help="Run the full Proposer/Critic/Judge pipeline")
    verify.add_argument("question", nargs="?", default=DEFAULT_QUESTION)
    verify.add_argument("--session", default=None, help="Session id for continuity")
    verify.add_argument("--timeout", type=float, default=180.0)
    verify.add_argument("--out", default=None, help="Directory for verdict.md/.json")
    verify.add_argument("--json", action="store_true", help="Print JSON only to stdout")
    verify.set_defaults(func=_cmd_verify)

    probe = sub.add_parser("probe", help="Run one building-block probe")
    probe.add_argument(
        "probe", choices=["tools", "session", "structured", "error", "version"]
    )
    probe.set_defaults(func=_cmd_probe)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
