"""Command line entry point with a one-ticket invocation and JSON completion output."""

import argparse
import json
import os
import sys
from pathlib import Path

from pydantic import ValidationError

from .datasets import DEFAULT_MANIFEST, MAX_INPUT_BYTES, describe_cases, read_input, select_case
from .models import Ticket
from .router import DEFAULT_POLICY, RoutingRunError, route_ticket


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Route one Northstar Notes support ticket")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--ticket", type=Path, help="JSON ticket file")
    source.add_argument("--stdin", action="store_true", help="Read one JSON ticket from stdin")
    source.add_argument("--case", help="Select one versioned dataset case; makes one bounded model run")
    source.add_argument("--list-cases", action="store_true", help="Validate and list inputs without calling a model")
    parser.add_argument("--manifest", type=Path, help="Dataset manifest for --case or --list-cases")
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--model", default=os.getenv("ROUTER_MODEL", "openai:gpt-6.1-sol"))
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.manifest is not None and not (args.case or args.list_cases):
        parser.error("--manifest requires --case or --list-cases")
    try:
        manifest = args.manifest or DEFAULT_MANIFEST
        if args.list_cases:
            print(json.dumps(describe_cases(manifest)))
            return 0
        dataset = None
        if args.case:
            ticket, dataset = select_case(args.case, manifest)
        else:
            raw = sys.stdin.buffer.read(MAX_INPUT_BYTES + 1) if args.stdin else read_input(args.ticket)
            if len(raw) > MAX_INPUT_BYTES:
                raise ValueError("JSON input exceeds 128 KiB")
            ticket = Ticket.model_validate_json(raw)
        if not os.getenv("OPENAI_API_KEY"):
            raise ValueError("OPENAI_API_KEY is required for a real model run")
        outcome = route_ticket(ticket, model=args.model, policy_path=args.policy)
        outcome.dataset = dataset
    except RoutingRunError as exc:
        print(json.dumps({"error": {"code": "model_failed", "message": str(exc),
                                   "type": exc.provider_error_type, "http_status": exc.http_status},
                          "observation": exc.observation.model_dump(mode="json"),
                          "input_sha256": exc.input_sha256, "policy_sha256": exc.policy_sha256,
                          "dataset": dataset.model_dump() if dataset is not None else None}), file=sys.stderr)
        return 1
    except (OSError, ValueError, ValidationError) as exc:
        print(json.dumps({"error": {"code": "invalid_configuration_or_input", "message": str(exc)}}), file=sys.stderr)
        return 2
    except Exception as exc:
        print(json.dumps({"error": {"code": "model_failed", "type": type(exc).__name__}}), file=sys.stderr)
        return 1
    print(outcome.model_dump_json())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
