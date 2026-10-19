// Actual command adapter -> unchanged Python CLI -> real provider SDK -> owned
// loopback HTTP. Responses/usage here are synthetic; no paid model is called.
import test from 'node:test';
import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { spawn } from 'node:child_process';
import { once } from 'node:events';
import { fileURLToPath } from 'node:url';
import { TARGET_INVOCATION_VERSION } from '@firedrill-run/sdk';

const root = fileURLToPath(new URL('../', import.meta.url));

for (const completed of [true, false]) test(`real adapter and native SDK retain ${completed ? 'completed' : 'unfinished'} controlled response`, async () => {
  const requests = [];
  const server = createServer(async (request, response) => {
    const chunks = [];
    for await (const chunk of request) chunks.push(chunk);
    requests.push({ url: request.url, body: JSON.parse(Buffer.concat(chunks).toString()), authorization: request.headers.authorization });
    response.writeHead(200, { 'content-type': 'application/json' });
    response.end(JSON.stringify({
      id: 'resp_controlled', object: 'response', created_at: 1792070000,
      model: 'controlled-router-snapshot', status: completed ? 'completed' : 'incomplete', error: null,
      incomplete_details: completed ? null : { reason: 'max_output_tokens' }, background: false,
      output: [{ id: 'msg_controlled', type: 'message', role: 'assistant', status: 'completed', content: [{
        type: 'output_text', text: JSON.stringify({ action: 'route', queue: 'billing', reason: 'The customer needs the renewal receipt', clarifying_question: null }), annotations: [],
      }] }],
      usage: { input_tokens: 25, output_tokens: 12, total_tokens: 37, input_tokens_details: { cached_tokens: 0 }, output_tokens_details: { reasoning_tokens: 0 } },
    }));
  });
  server.listen(0, '127.0.0.1');
  await once(server, 'listening');
  const env = { ...process.env, OPENAI_API_KEY: 'synthetic-adapter-key', OPENAI_BASE_URL: `http://127.0.0.1:${server.address().port}/v1`, NO_PROXY: '127.0.0.1', no_proxy: '127.0.0.1', FIREDRILL_TOKEN: 'synthetic-operator-authority' };
  const invocation = {
    schemaVersion: TARGET_INVOCATION_VERSION, runId: 'controlled-run', attemptId: 'controlled-attempt',
    scenario: { id: 'ordinary-routing' }, configuration: { id: 'controlled', parameters: { model: 'openai:controlled-router' } },
    tools: {}, input: { caseId: 'starter-receipt' },
  };
  const child = spawn(process.execPath, ['firedrill/target.mjs'], { cwd: root, env, stdio: ['pipe', 'pipe', 'pipe'] });
  let stdout = '', stderr = '';
  child.stdout.on('data', chunk => { stdout += chunk; });
  child.stderr.on('data', chunk => { stderr += chunk; });
  const closed = once(child, 'close');
  const timeout = setTimeout(() => child.kill('SIGTERM'), 20000);
  child.stdin.end(JSON.stringify(invocation));
  try {
    const [code] = await closed;
    assert.equal(requests[0]?.url, '/v1/responses', stderr);
    assert.ok(requests.length >= 1 && requests.length <= 2);
    assert.equal(requests[0].authorization, 'Bearer synthetic-adapter-key');
    assert.match(JSON.stringify(requests[0].body.input), /NNS-1001/);
    assert.equal(JSON.stringify(requests).includes('synthetic-operator-authority'), false);
    assert.equal(JSON.stringify(requests[0].body.input).includes('starter-receipt'), false);
    if (completed) {
      assert.equal(code, 0, stderr);
      const output = JSON.parse(stdout);
      assert.equal(output.ticket_id, 'NNS-1001');
      assert.equal(output.decision.queue, 'billing');
      assert.equal(output.observation.responses[0].model, 'controlled-router-snapshot');
      assert.equal(output.observation.cost_usd, null);
      assert.equal(requests.length, 1);
    } else {
      assert.equal(code, 1, stderr);
      assert.equal(stdout, '');
      const error = JSON.parse(stderr);
      assert.equal(error.application.exitCode, 1);
      // SDK diagnostics may precede the CLI's final JSON error on stderr.
      const application = JSON.parse(error.application.stderr.split(/\r?\n/).filter(line => line.startsWith('{')).at(-1));
      assert.equal(application.error.code, 'model_failed');
      assert.equal(application.observation.cost_usd, null);
    }
  } finally {
    clearTimeout(timeout);
    if (child.exitCode === null) child.kill('SIGTERM');
    server.closeAllConnections();
    await new Promise(resolve => server.close(resolve));
  }
});
