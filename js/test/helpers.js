import { readFileSync, readdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { decodeSpecial, encodeSpecial } from '../src/index.js';

export const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..', '..');

export function loadVectors() {
  const dir = join(ROOT, 'vectors');
  return readdirSync(dir)
    .filter((name) => name.endsWith('.json'))
    .sort()
    .map((name) => [name, decodeSpecial(JSON.parse(readFileSync(join(dir, name), 'utf8')))]);
}

export function readRepoSpec() {
  return JSON.parse(readFileSync(join(ROOT, 'spec', 'invariants.json'), 'utf8'));
}

/** NaN and -0 trip deepStrictEqual, so compare the JSON text of the marker form. */
export function comparable(value) {
  return JSON.parse(JSON.stringify(encodeSpecial(value)));
}

export function triples(issues) {
  return issues.map(({ code, severity, path }) => ({ code, severity, path }));
}
