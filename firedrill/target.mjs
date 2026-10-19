import { fileURLToPath } from 'node:url';
import { resolve } from 'node:path';
import { commandMain, invokeCLI } from './adapter-runtime.mjs';

const root = fileURLToPath(new URL('../', import.meta.url));
const cases = new Set(['starter-receipt', 'ambiguous-detail']);

export async function runApplication(input, parameters, signal) {
  if (Object.keys(input).join(',') !== 'caseId' || !cases.has(input.caseId)) {
    throw new Error('Select one reviewed routing case from firedrill/scenario.json.');
  }
  const argv = ['uv', 'run', '--locked', '--no-sync', 'route-ticket', '--case', input.caseId];
  if (parameters.model) argv.push('--model', parameters.model);
  return await invokeCLI(argv, { cwd: root, signal });
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  await commandMain(runApplication);
}
