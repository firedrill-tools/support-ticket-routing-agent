# Simulate this agent with Firedrill

Firedrill is a simulation platform for AI agents. Your coding agent can prepare
and operate these simulations; the application and its model run in your own
repository or CI.

Start in the repository root, not inside `firedrill/`:

```sh
npx firedrill-run init
```

Authorize Firedrill and select a project/environment. Installation choices are
optional; skip them when using the locked `firedrill/` toolchain below. This setup
does not invoke the target agent or grant it access to real business accounts.

Verified package release: **2.2.2**, October 19, 2026. The CLI and TypeScript SDK are exact-pinned with a separate npm lockfile. This optional execution toolchain requires Node 22+ and does not change the Python application's model dependencies. Python-only native integrations may instead use the official `firedrill-run` SDK; this repository uses the documented command target.

## Prepare and validate

From the repository root, install the application with `uv sync --locked --dev`. Keep `uv` on PATH. Then:

```sh
npm ci --prefix firedrill --ignore-scripts --no-audit --no-fund
firedrill_cli=firedrill/node_modules/@firedrill-run/cli/bin/firedrill.mjs
node "$firedrill_cli" validate firedrill/scenario.json --json --non-interactive
```

Validation is offline and allocates no batch. The tests exercise the real CLI's missing-key failure, adapter subprocess lifecycle, current invocation format and released recipe validator. Actual adapter-to-CLI-to-provider-SDK tests also retain completed and unfinished responses over owned loopback HTTP. Those responses and usage are synthetic; these checks do not establish authenticated persistence, paid provider usage or model quality.

## Select scope and run deliberately

Run `npx firedrill-run init` in a human terminal to sign in and select the actual project/environment. Init writes public selection to `firedrill.config.json`. Automation instead supplies `FIREDRILL_TOKEN`, `FIREDRILL_PROJECT_ID` and `FIREDRILL_ENVIRONMENT_ID` through its secret store. Conflicting scope is an error. Operator authority and the application's `OPENAI_API_KEY` are separate; the adapter removes Firedrill and CI identity variables before launching the application.

With provider access and a deliberate call budget:

```sh
node firedrill/simulate.mjs --preview
node "$firedrill_cli" simulate firedrill/scenario.json --scenario ordinary-routing --json --non-interactive
```

The selected command runs the actual Pydantic AI/OpenAI routing path once. The full recipe contains two independent ticket cases, one repetition and concurrency one; each application invocation retains its existing two-response upper bound. No synthetic Firedrill Tool is needed. Neither output limits nor deadlines guarantee a provider billing cap. Review actual usage and errors.

`node firedrill/simulate.mjs` uses the SDK to execute the same full command recipe. Optional `configuration.parameters.model` selects an enabled application model. The target receives ID-only scenario context and task input through invocation version `2026-10-17-target-invocation.1`; checks/rubrics/controller data are rejected. It returns the actual application JSON and emits failure diagnostics on stderr with nonzero status. Stateless tickets have no business database or conversation to reset. Output evidence and provider retention are separate.

## Operator MCP and recovery

Connect your coding agent to the remote OAuth endpoint **https://mcp.firedrill.run/mcp** using the [host-specific setup](https://docs.firedrill.run/guides/coding-agents). No local MCP package is needed. Host OAuth is separate from local CLI/SDK login. Preparation, queueing and report reads through MCP do not launch a local process; attach the returned batch with `node firedrill/simulate.mjs --run BATCH_ID`.

Preserve the SDK's operation ID and private journal after interruption. Use `node firedrill/simulate.mjs --resume OPERATION_ID` for that exact execution, or `--result BATCH_ID` to read retained evidence. Do not start another simulation to repair a missing acknowledgement. SDK diagnostics retain uncertainty and repair information, and runner exit codes propagate pending execution/assessment and gates. Execution completion is distinct from correctness; this recipe requests no grading or gate.

For opt-in live CI, use the released [CI generator](https://docs.firedrill.run/guides/ci) after selecting actual scope and a protected environment. Existing CI runs offline checks only. No paid campaign, real connector action, authenticated report, package publication or license decision is implied by this integration.

References: [SDK](https://docs.firedrill.run/sdk/typescript), [command adapters](https://docs.firedrill.run/guides/run-first-drill), [CLI](https://docs.firedrill.run/cli/overview), [operator MCP](https://docs.firedrill.run/guides/control-mcp).

## Offline verification

After installing the application dependencies and locked integration toolchain,
run `npm test --prefix firedrill` to exercise the adapter checks. These checks are
optional for first use and call no paid model. The Node 22+ requirement above is
for the Firedrill clients; it does not lower any application runtime requirement
in the root README.
