// The JavaScript side implements exactly the invariants in spec/invariants.json.

import assert from 'node:assert/strict';
import { test } from 'node:test';
import { CHECKS, REPAIRS, SPEC } from '../src/index.js';
import { readRepoSpec } from './helpers.js';

test('embedded spec matches spec/invariants.json', () => {
  assert.deepStrictEqual(JSON.parse(JSON.stringify(SPEC)), readRepoSpec());
});

test('CHECKS covers exactly the spec codes, in spec order', () => {
  assert.deepStrictEqual(Object.keys(CHECKS), readRepoSpec().invariants.map((inv) => inv.code));
});

test('REPAIRS covers exactly the codes marked auto', () => {
  const auto = readRepoSpec().invariants.filter((inv) => inv.repair === 'auto').map((inv) => inv.code);
  assert.deepStrictEqual([...REPAIRS].sort(), auto.sort());
});
