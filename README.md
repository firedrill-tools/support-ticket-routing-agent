# Route support tickets with Pydantic AI and GPT-6.1 Sol

This small, standalone command-line application routes Northstar Notes support tickets to billing, account, product, or security. It can ask for clarification or mark an unrelated request out of scope. The application uses **Pydantic AI 2.56.0** with an OpenAI Responses model. It does not send messages, change accounts, issue refunds, or connect to a live help desk.

## Run one ticket

Install [uv](https://docs.astral.sh/uv/) and Python 3.11 or newer. From this repository:

```sh
uv sync --dev
export OPENAI_API_KEY='your-key-from-a-secret-manager'
uv run route-ticket --ticket data/tickets/ordinary-billing.json
```

The default model is `openai:gpt-6.1-sol`; set `ROUTER_MODEL` or pass `--model openai:<model-id>` to change it. One command makes a real OpenAI API request and prints a single JSON object when complete. The model call is billed to your provider account. Do not place a real key in `.env.example` or Git. `--stdin` accepts a ticket JSON object from standard input. The CLI exits `0` after a structured decision, `2` for invalid input/configuration, and `1` for a model-request failure.

The output has `ticket_id`, `model`, `decision` (`action`, `queue`, `reason`, `clarifying_question`), and usage fields returned by Pydantic AI. Missing usage is not estimated. The queue is present only for a `route` action. No application state is retained, so each ticket invocation is independent.

## Explore scenarios

Five fictional ticket inputs and their purpose are in [scenarios/README.md](scenarios/README.md). They cover an ordinary receipt request, vague intent, an account-compromise report with a billing symptom, an unrelated request, and an instruction embedded in customer text. These files are inputs, not recorded model outcomes. The model sees the selected ticket and the routing policy in `src/ticket_router/routing_policy.txt`; it does not read the scenario brief.

Run one case at a time. A repeated call is a new provider execution and may yield different valid wording. No automatic large campaign is included.

## Offline checks and CI

```sh
uv sync --dev
uv run pytest -q
uv run route-ticket --help
```

CI runs these checks without an API key or model call. They verify input samples and the decision contract; they do not prove routing quality. A real model proof and observed outputs will be added when an authorized provider key is available.

## Firedrill connection

The new Firedrill integration has **not** been implemented or verified. The intended boundary is this one-ticket CLI: input file/stdin, JSON completion output, explicit model configuration, and no external state to reset. Connect it only against the current released Firedrill client and documentation. The older example repository in the parent workspace uses a retired interface and must not be copied. No simulated result, report, screenshot, or CI Firedrill run is claimed here.

## Limits

This is a routing assistant, not an automated help desk. It cannot confirm account facts or execute business actions. The policy is a local text file, and the example data is fictional. The package is currently local and unlicensed pending the portfolio's publication decision. See `AGENTS.md` for the execution and evidence boundaries.

Framework reference: [Pydantic AI agent documentation](https://pydantic.dev/docs/ai/core-concepts/agent/). Model identifier and Responses support: [official OpenAI GPT-6.1 Sol documentation](https://developers.openai.com/api/docs/models/gpt-6.1-sol).

Explore related applications in the [Firedrill example catalog](https://github.com/firedrill-tools/firedrill-example-catalog). Product and setup references: [Firedrill](https://firedrill.run/) and the [official developer documentation](https://docs.firedrill.run/). Use documentation matching the qualified release; this repository records its current integration limits above.
