#!/usr/bin/env node
// Command line for the JavaScript validator.
//
//   node cli.js validate [FILE]   print issues as JSON, exit 1 on any error
//   node cli.js repair [FILE]     print {doc, changes} as JSON
//   node cli.js batch             read [{doc, options}, ...] on stdin and print
//                                 [{issues, repaired, changes}, ...]; used by
//                                 scripts/fuzz_parity.py
//   node cli.js codes             print the codes this side implements
//
// Input and output use the {"$num": "NaN"} markers from src/codec.js. FILE
// defaults to stdin.

import { readFileSync } from 'node:fs';
import { CHECKS, REPAIRS, decodeSpecial, encodeSpecial, hasErrors, repair, validate } from './src/index.js';

function readInput(file) {
  const text = readFileSync(file && file !== '-' ? file : 0, 'utf8');
  return decodeSpecial(JSON.parse(text));
}

function print(value) {
  process.stdout.write(`${JSON.stringify(encodeSpecial(value), null, 2)}\n`);
}

function runOne({ doc, options }) {
  try {
    const issues = validate(doc, options ?? undefined);
    const { doc: repaired, changes } = repair(doc);
    return { issues, repaired, changes };
  } catch (err) {
    return { error: String(err && err.message ? err.message : err) };
  }
}

function main(argv) {
  const [command, file] = argv;
  switch (command) {
    case 'validate': {
      const issues = validate(readInput(file));
      print(issues);
      return hasErrors(issues) ? 1 : 0;
    }
    case 'repair':
      print(repair(readInput(file)));
      return 0;
    case 'batch':
      print(readInput(file).map(runOne));
      return 0;
    case 'codes':
      print({ checks: Object.keys(CHECKS), repairs: [...REPAIRS] });
      return 0;
    default:
      process.stderr.write('usage: node cli.js validate|repair|batch|codes [FILE]\n');
      return 2;
  }
}

process.exitCode = main(process.argv.slice(2));
