import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { join } from 'node:path';
import { test } from 'node:test';
import { comparePaths, decodeSpecial, encodeSpecial, hasErrors, repair, validate } from '../src/index.js';
import { isBlank } from '../src/doc.js';
import { ROOT } from './helpers.js';

const node = (id, fields = {}) => ({ id, label: 'N', x: 0, y: 0, w: 1, h: 1, ...fields });

test('a non-object doc is rejected', () => {
  for (const bad of [null, [], 'doc', 3]) {
    assert.throws(() => validate(bad), TypeError);
    assert.throws(() => repair(bad), TypeError);
  }
});

test('an unknown option is rejected', () => {
  assert.throws(() => validate({}, { max_nodes: 3 }), /max_nodes/);
});

test('options do not leak between calls', () => {
  const doc = { nodes: [node('a'), node('b')] };
  assert.equal(validate(doc, { maxNodes: 1 }).length, 1);
  assert.deepStrictEqual(validate(doc), []);
});

test('messages are filled in', () => {
  const [issue] = validate({ nodes: [node('a')], edges: [{ id: 'e1', from: 'a', to: 'zz' }] });
  assert.equal(issue.message, 'Edge "e1" field to points to missing node "zz"');
});

test('hasErrors ignores warnings', () => {
  assert.equal(hasErrors(validate({ nodes: [node('a', { label: '' })] })), false);
  assert.equal(hasErrors(validate({ nodes: [node('a', { w: -1 })] })), true);
});

test('ids never reach Object.prototype', () => {
  const doc = { nodes: [node('a')], edges: [{ id: 'e', from: 'a', to: 'constructor' }] };
  assert.deepStrictEqual(validate(doc).map((i) => i.path), ['/edges/0/to']);
});

test('blank set differs from String.prototype.trim on purpose', () => {
  assert.equal(isBlank('\u001c'), false);
  assert.equal(isBlank('\u0085'), false);
  assert.equal(isBlank('\ufeff'), true);
  assert.equal(isBlank(''), true);
});

test('paths sort with numeric indexes', () => {
  const paths = ['/nodes/10/w', '/nodes/2/x', '/nodes/2', '/edges/0/to', '/edges/0'];
  assert.deepStrictEqual([...paths].sort(comparePaths), [
    '/edges/0',
    '/edges/0/to',
    '/nodes/2',
    '/nodes/2/x',
    '/nodes/10/w',
  ]);
});

test('codec round trip', () => {
  const value = { a: [Number.NaN, Infinity, -Infinity, 1.5, { $num: 'other' }] };
  const decoded = decodeSpecial(JSON.parse(JSON.stringify(encodeSpecial(value))));
  assert.ok(Number.isNaN(decoded.a[0]));
  assert.deepStrictEqual(decoded.a.slice(1), [Infinity, -Infinity, 1.5, { $num: 'other' }]);
});

test('cli validate exits 1 on errors and prints issues', () => {
  const cli = join(ROOT, 'js', 'cli.js');
  const input = JSON.stringify({ nodes: [node('a', { x: { $num: 'NaN' } })] });
  let status = 0;
  let out = '';
  try {
    execFileSync(process.execPath, [cli, 'validate'], { input, encoding: 'utf8' });
  } catch (err) {
    status = err.status;
    out = err.stdout;
  }
  assert.equal(status, 1);
  assert.deepStrictEqual(JSON.parse(out).map((i) => i.code), ['E_BAD_NUMBER']);
});

test('cli batch returns one result per doc', () => {
  const cli = join(ROOT, 'js', 'cli.js');
  const input = JSON.stringify([{ doc: {} }, { doc: [] }, { doc: { nodes: [node('a')] }, options: { maxNodes: 0 } }]);
  const out = JSON.parse(execFileSync(process.execPath, [cli, 'batch'], { input, encoding: 'utf8' }));
  assert.equal(out.length, 3);
  assert.deepStrictEqual(out[0].issues, []);
  assert.match(out[1].error, /JSON object/);
  assert.deepStrictEqual(out[2].issues.map((i) => i.code), ['E_TOO_LARGE']);
});
