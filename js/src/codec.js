// Carry NaN and Infinity through plain JSON. A non-finite number is written
// as {"$num": "NaN"}, {"$num": "Infinity"} or {"$num": "-Infinity"}.
// Twin of src/dualval/codec.py.

export const MARKER = '$num';
const DECODE = { NaN: Number.NaN, Infinity: Number.POSITIVE_INFINITY, '-Infinity': Number.NEGATIVE_INFINITY };

function isPlainObject(value) {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

/** Replace marker objects with real numbers, recursively. */
export function decodeSpecial(value) {
  if (Array.isArray(value)) return value.map(decodeSpecial);
  if (isPlainObject(value)) {
    const keys = Object.keys(value);
    if (keys.length === 1 && keys[0] === MARKER && Object.hasOwn(DECODE, value[MARKER])) {
      return DECODE[value[MARKER]];
    }
    const out = {};
    for (const key of keys) {
      Object.defineProperty(out, key, { value: decodeSpecial(value[key]), enumerable: true, writable: true, configurable: true });
    }
    return out;
  }
  return value;
}

/** Replace non-finite numbers with marker objects, recursively. */
export function encodeSpecial(value) {
  if (typeof value === 'number' && !Number.isFinite(value)) {
    if (Number.isNaN(value)) return { [MARKER]: 'NaN' };
    return { [MARKER]: value > 0 ? 'Infinity' : '-Infinity' };
  }
  if (Array.isArray(value)) return value.map(encodeSpecial);
  if (isPlainObject(value)) {
    const out = {};
    for (const key of Object.keys(value)) {
      Object.defineProperty(out, key, { value: encodeSpecial(value[key]), enumerable: true, writable: true, configurable: true });
    }
    return out;
  }
  return value;
}
