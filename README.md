# Route support tickets with Pydantic AI and GPT-6.1 Sol

A standalone command-line application routes fictional Northstar Notes support tickets to billing, account, product or security. It can ask for clarification or mark an unrelated request out of scope. It uses **Pydantic AI 2.56.0**, **OpenAI Python 3.31.0** and the Responses API's native structured output. It cannot send messages, change accounts, issue refunds or connect to a help desk.

## Run one ticket

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/). From this repository:

```sh
uv sync --locked --dev
export OPENAI_API_KEY='your-key-from-a-secret-manager'
uv run --no-sync route-ticket --ticket data/tickets/ordinary-billing.json
```

The default model remains `openai:gpt-6.1-sol`; set `ROUTER_MODEL` or pass `--model openai:<model-id>` to select another Responses model supporting native JSON schema. `--policy path/to/policy.txt` selects a policy variant. This is a synchronous, one-ticket invocation. It accepts at most 128 KiB of JSON; ticket fields have smaller schema limits. `--stdin` accepts a ticket on standard input.

A command makes a real provider run and may incur cost. There are at most two model responses (the initial response and one validation correction), with 30-second request timeouts. The CLI-owned OpenAI client disables hidden HTTP retries and closes on success or failure. A Python caller injecting an `OpenAIProvider` owns that provider/client and its transport settings. No test provider, cached answer or fake model is selected by a CLI flag.

## Versioned inputs

```sh
uv run --no-sync route-ticket --list-cases
uv run --no-sync route-ticket --case starter-receipt
```

Listing checks the manifest, input schemas and SHA-256 digests **without a key or model call**. `--case` starts one real model run for the selected input. A changed digest, unknown case or invalid manifest fails before provider access. `--manifest path/to/manifest.json` selects another explicit dataset for these modes. Its JSON inputs must be inside its directory.

[Dataset 1.0.0](data/manifest.json) contains **16 distinct tickets**: 2 starter, 8 busy but ordinary, 3 ambiguous/conflicting and 3 boundary cases. The busy profile is a population of independent support requests, not eight tickets placed in one model context. No batch campaign starts automatically. Each repetition is a new run, potentially with two API responses. See [scenarios/README.md](scenarios/README.md) for case purposes and assessment limits.

Only the chosen ticket and policy reach the model. The manifest, scenario notes and assessment guidance remain outside its prompt. The wheel includes the same manifest, inputs and policy. The application is stateless: each invocation constructs a new agent and shares no conversation or business state. A rerun uses unchanged input/policy files; callers own any saved outputs.

## Completion and evidence

Exit codes are `0` for a complete validated decision, `2` for invalid input/configuration and `1` for a failed model run. Success writes one JSON object to stdout. Failure leaves stdout empty and writes JSON error evidence to stderr. A provider refusal is a model failure, distinct from a valid `out_of_scope` decision. Valid-looking JSON in an incomplete, cancelled or failed response cannot complete the task.

The result includes:

- `ticket_id`, requested `model` and structured `decision` (`action`, `queue`, `reason`, `clarifying_question`). Only `route` has a queue; only `clarify` has a nonblank question. Unexpected fields and blank reasons are rejected.
- `input_sha256` for the serialized ticket actually sent and `policy_sha256` for the policy content.
- `dataset` identity/version/profile/case/source digest when selected with `--case`; it is null for ad hoc file/stdin inputs.
- `observation.responses`: actual SDK response model, response ID, status, finish reason/state and raw reported usage for each observed response, including validation attempts.
- `usage`: aggregate reported token counts only when **every** observed response reports complete counters; otherwise null. `observation.usage_complete` states this explicitly. `observation.sdk_usage` is separate because SDK defaults can show zeros when measurements were absent. `cost_usd` stays null; no price is inferred.

A model failure retains the available parsed response observations, input/policy hashes and selected dataset identity in stderr. An HTTP failure with no parsed response has no reported usage; this is not proof of zero provider cost or a complete provider billing record. The adapter uses the pinned SDK's documented provider-details subclass hook to retain status and usage presence before normalization.

## Offline checks and CI

```sh
uv sync --locked --dev
uv run --no-sync pytest -q
uv run --no-sync route-ticket --help
uv run --no-sync route-ticket --list-cases
uv build
uv run --no-sync python scripts/check_wheel.py
```

The 44 checks exercise the actual Pydantic AI and OpenAI Responses adapters with **httpx2 2.13.1 MockTransport**, not a replacement `Agent`. They cover native JSON schema requests, correction bounds, refusals, nonfinal responses, missing/reported-zero usage, HTTP failure, client ownership, CLI stdout/stderr, input limits and dataset drift. The packaging check runs the bundled CLI outside the source checkout. CI runs these without a provider key. These are offline adapter/application proofs; they do not establish live routing quality or provider access.

## Firedrill and publication

The new Firedrill interface has not been qualified. The intended seam is the existing one-ticket CLI, immutable input/policy hashes, dataset identity, JSON completion/error output and independent invocations. Connect it only to the released interface and preserve real evidence. The older Gmail example uses a retired interface. No Firedrill report or execution is claimed here.

Live OpenAI proof, publication and license choices remain parked external gates. This repository stays private and unlicensed pending those decisions. See [AGENTS.md](AGENTS.md) for execution boundaries.

References: [Pydantic AI OpenAI adapters](https://pydantic.dev/docs/ai/models/openai/), [OpenAI structured-output completion and refusal handling](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses), and [official model documentation](https://developers.openai.com/api/docs/models/gpt-6.1-sol).

Explore related applications in the [Firedrill example catalog](https://github.com/firedrill-tools/firedrill-example-catalog). Product and setup references: [Firedrill](https://firedrill.run/) and the [official developer documentation](https://docs.firedrill.run/). Use documentation matching the qualified release.
