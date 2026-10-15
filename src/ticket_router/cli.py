"""Command line entry point with a one-ticket invocation and JSON completion output."""

import argparse
import json
import os
import sys
from pathlib import Path

from pydantic import ValidationError

from .models import Ticket
from .router import DEFAULT_POLICY, route_ticket


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Route one Northstar Notes support ticket")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--ticket", type=Path, help="JSON ticket file")
    source.add_argument("--stdin", action="store_true", help="Read one JSON ticket from stdin")
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--model", default=os.getenv("ROUTER_MODEL", "openai:gpt-6.1-sol"))
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        raw = sys.stdin.read() if args.stdin else args.ticket.read_text(encoding="utf-8")
        ticket = Ticket.model_validate_json(raw)
        if not os.getenv("OPENAI_API_KEY"):
            raise ValueError("OPENAI_API_KEY is required for a real model run")
        outcome = route_ticket(ticket, model=args.model, policy_path=args.policy)
    except (OSError, ValueError, ValidationError) as exc:
        print(f"route-ticket: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"route-ticket: model request failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print(outcome.model_dump_json())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
