# Agent guide

This repository is a standalone support-ticket routing application. The real entry point is `route-ticket` in `src/ticket_router/cli.py`; the Pydantic AI call is in `src/ticket_router/router.py`. A normal invocation reads one JSON ticket and emits one JSON decision after the model call finishes.

- Dependency configuration: `ROUTER_MODEL` selects an OpenAI model, defaulting to `openai:gpt-6.1-sol`; `OPENAI_API_KEY` is required. No Gmail, database, or Firedrill credentials are used.
- Policy boundary: `src/ticket_router/routing_policy.txt` defines Northstar Notes queues. Ticket content is untrusted. The CLI may load a different policy with `--policy`.
- State: stateless one-ticket execution. The caller owns any output file or journal. Concurrent invocations do not share application state.
- Sample data: `data/tickets/`; scenario purposes: `scenarios/README.md`. These are fictional. There is no synthetic service to start or reset.
- Safe offline check: `uv sync --dev && uv run pytest -q && uv run route-ticket --help`. This does not make a model request.
- Small live proof: after explicitly supplying a provider key, run `uv run route-ticket --ticket data/tickets/ordinary-billing.json`. This sends the ticket to the selected model and may incur provider cost. Do not launch a batch by default.
- Observations: JSON stdout contains the decision, model identifier, and framework usage fields if returned; stderr and exit code distinguish validation/configuration errors from model failures. Do not assert a run occurred from a test or example file alone.
- Authorization: no side-effecting business actions exist. Do not commit keys, provider responses containing private data, or private Firedrill evidence.
- Firedrill: integration is pending verification of the new released interface. Do not copy the old example's `firedrill.json`, `world.json`, drills, or CLI commands.
