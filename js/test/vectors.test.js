// Run every shared vector in vectors/ through the JavaScript implementation.
// tests/test_vectors.py runs the same files through the Python one.

import assert from 'node:assert/strict';
import { describe, test } from 'node:test';
import { REPAIRS, repair, validate } from '../src/index.js';
import { comparable, loadVectors, triples } from './helpers.js';

const VECTORS = loadVectors();

test('there are at least 25 vectors', () => {
  assert.ok(VECTORS.length >= 25, `only ${VECTORS.length} vectors`);
});

for (const [name, vector] of VECTORS) {
  describe(name, () => {
    test('validate', () => {
      const issues = validate(vector.input, vector.options);
      assert.deepStrictEqual(triples(issues), vector.expected_issues);
      assert.ok(issues.every((issue) => issue.message.length > 0));
    });

    test('repair', () => {
      const before = comparable(vector.input);
      const { doc, changes } = repair(vector.input);
      assert.deepStrictEqual(comparable(doc), comparable(vector.expected_repaired));
      assert.deepStrictEqual(comparable(changes), comparable(vector.expected_changes));
      assert.deepStrictEqual(comparable(vector.input), before, 'repair must not modify its input');
    });

    test('repair is idempotent', () => {
      const once = repair(vector.input).doc;
      const twice = repair(once);
      assert.deepStrictEqual(twice.changes, []);
      assert.deepStrictEqual(comparable(twice.doc), comparable(once));
    });

    test('repaired doc has no repairable issues', () => {
      const { doc } = repair(vector.input);
      const left = validate(doc, vector.options).map((issue) => issue.code);
      assert.deepStrictEqual(left.filter((code) => REPAIRS.includes(code)), []);
    });
  });
}
