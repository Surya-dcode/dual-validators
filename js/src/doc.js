// Small helpers shared by validate() and repair().
//
// Each helper has a twin with the same name in src/dualval/_doc.py. When one
// changes, the other must change the same way; the shared vectors and the
// fuzzer check that they still agree.

import { SPEC } from './spec.js';

export const NUMBER_FIELDS = ['x', 'y', 'w', 'h'];
export const SIZE_FIELDS = ['w', 'h'];

const BLANK_CHARS = new Set(
  SPEC.blankCodePoints.map((cp) => String.fromCodePoint(parseInt(cp.slice(2), 16))),
);

/** True for a JSON object (not null, not an array). */
export function isObject(value) {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

/**
 * Read an own property only. Ids such as "constructor" or "toString" must not
 * reach Object.prototype, and neither must field lookups.
 */
export function get(obj, key) {
  return Object.hasOwn(obj, key) ? obj[key] : undefined;
}

/** A collection that is not an array is treated as empty. */
export function asList(value) {
  return Array.isArray(value) ? value : [];
}

/** True for a finite number. Booleans, strings and null are not numbers. */
export function isFiniteNumber(value) {
  return typeof value === 'number' && Number.isFinite(value);
}

/**
 * True when every character is in the spec's blank set. Not String.trim():
 * trim and Python's str.strip disagree on U+001C..U+001F, U+0085 and U+FEFF,
 * so the spec lists the characters explicitly.
 */
export function isBlank(text) {
  for (const ch of text) {
    if (!BLANK_CHARS.has(ch)) return false;
  }
  return true;
}

/** String ids of every node object. Duplicated ids still count as present. */
export function nodeIds(nodes) {
  const ids = new Set();
  for (const node of nodes) {
    if (isObject(node) && typeof get(node, 'id') === 'string') ids.add(node.id);
  }
  return ids;
}

export function isNodeRef(value, ids) {
  return typeof value === 'string' && ids.has(value);
}

export function resolveOptions(options) {
  const resolved = structuredClone(SPEC.defaults);
  if (options) {
    const unknown = Object.keys(options).filter((key) => !Object.hasOwn(SPEC.defaults, key)).sort();
    if (unknown.length) throw new TypeError(`unknown option(s): ${unknown.join(', ')}`);
    Object.assign(resolved, options);
  }
  return resolved;
}

/** Render a document value for a human-readable message. */
export function show(value) {
  const text = JSON.stringify(value);
  return text === undefined ? 'undefined' : text;
}
