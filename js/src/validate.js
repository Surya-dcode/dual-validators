// validate(doc) for diagram documents.
//
// Every check is registered in CHECKS under the code it reports. A check
// yields [path, params] pairs and never chooses its own code. test/spec.test.js
// checks that CHECKS holds exactly the codes in spec/invariants.json.

import { SPEC } from './spec.js';
import {
  NUMBER_FIELDS,
  SIZE_FIELDS,
  asList,
  get,
  isBlank,
  isFiniteNumber,
  isNodeRef,
  isObject,
  nodeIds,
  resolveOptions,
  show,
} from './doc.js';

const INVARIANTS = new Map(SPEC.invariants.map((inv) => [inv.code, inv]));

export function buildContext(doc, options) {
  if (!isObject(doc)) throw new TypeError('doc must be a JSON object');
  const nodes = asList(get(doc, 'nodes'));
  return {
    nodes,
    edges: asList(get(doc, 'edges')),
    groups: asList(get(doc, 'groups')),
    nodeIds: nodeIds(nodes),
    options: resolveOptions(options),
  };
}

function* checkDupId(ctx) {
  const firstSeen = new Map();
  for (const [name, items] of [['nodes', ctx.nodes], ['edges', ctx.edges], ['groups', ctx.groups]]) {
    for (const [i, item] of items.entries()) {
      if (!isObject(item) || typeof get(item, 'id') !== 'string') continue;
      const path = `/${name}/${i}/id`;
      if (firstSeen.has(item.id)) {
        yield [path, { id: show(item.id), first: firstSeen.get(item.id) }];
      } else {
        firstSeen.set(item.id, path);
      }
    }
  }
}

function* checkDanglingEdge(ctx) {
  for (const [i, edge] of ctx.edges.entries()) {
    if (!isObject(edge)) continue;
    for (const end of ['from', 'to']) {
      const ref = get(edge, end);
      if (!isNodeRef(ref, ctx.nodeIds)) {
        yield [`/edges/${i}/${end}`, { edge: show(get(edge, 'id')), end, ref: show(ref) }];
      }
    }
  }
}

function* checkSelfLoop(ctx) {
  const allowed = ctx.options.selfLoopKinds;
  for (const [i, edge] of ctx.edges.entries()) {
    if (!isObject(edge)) continue;
    const start = get(edge, 'from');
    if (typeof start !== 'string' || start !== get(edge, 'to')) continue;
    const kind = get(edge, 'kind');
    if (typeof kind === 'string' && allowed.includes(kind)) continue;
    yield [`/edges/${i}`, { edge: show(get(edge, 'id')), node: show(start), kind: show(kind) }];
  }
}

function* checkGroupMemberMissing(ctx) {
  for (const [gi, group] of ctx.groups.entries()) {
    if (!isObject(group) || !Array.isArray(get(group, 'members'))) continue;
    for (const [mj, member] of group.members.entries()) {
      if (!isNodeRef(member, ctx.nodeIds)) {
        yield [`/groups/${gi}/members/${mj}`, { group: show(get(group, 'id')), ref: show(member) }];
      }
    }
  }
}

function* checkNodeInTwoGroups(ctx) {
  const owner = new Map();
  for (const [gi, group] of ctx.groups.entries()) {
    if (!isObject(group) || !Array.isArray(get(group, 'members'))) continue;
    for (const [mj, member] of group.members.entries()) {
      if (!isNodeRef(member, ctx.nodeIds)) continue;
      if (!owner.has(member)) {
        owner.set(member, gi);
      } else if (owner.get(member) !== gi) {
        const first = ctx.groups[owner.get(member)];
        yield [`/groups/${gi}/members/${mj}`, { node: show(member), first: show(get(first, 'id')) }];
      }
    }
  }
}

function* checkBadNumber(ctx) {
  for (const [i, node] of ctx.nodes.entries()) {
    if (!isObject(node)) continue;
    for (const field of NUMBER_FIELDS) {
      if (!isFiniteNumber(get(node, field))) {
        yield [`/nodes/${i}/${field}`, { node: show(get(node, 'id')), field }];
      }
    }
  }
}

function* checkNegativeSize(ctx) {
  for (const [i, node] of ctx.nodes.entries()) {
    if (!isObject(node)) continue;
    for (const field of SIZE_FIELDS) {
      const value = get(node, field);
      if (isFiniteNumber(value) && value < 0) {
        yield [`/nodes/${i}/${field}`, { node: show(get(node, 'id')), field }];
      }
    }
  }
}

function* checkEmptyLabel(ctx) {
  for (const [i, node] of ctx.nodes.entries()) {
    if (!isObject(node)) continue;
    const label = get(node, 'label');
    if (typeof label !== 'string' || isBlank(label)) {
      yield [`/nodes/${i}/label`, { node: show(get(node, 'id')) }];
    }
  }
}

function* checkTooLarge(ctx) {
  const limits = [
    ['nodes', ctx.nodes, ctx.options.maxNodes],
    ['edges', ctx.edges, ctx.options.maxEdges],
  ];
  for (const [name, items, limit] of limits) {
    if (items.length > limit) {
      yield [`/${name}`, { collection: name, count: String(items.length), limit: String(limit) }];
    }
  }
}

/** code -> check function, in spec order. */
export const CHECKS = Object.freeze({
  E_DUP_ID: checkDupId,
  E_DANGLING_EDGE: checkDanglingEdge,
  E_SELF_LOOP: checkSelfLoop,
  E_GROUP_MEMBER_MISSING: checkGroupMemberMissing,
  E_NODE_IN_TWO_GROUPS: checkNodeInTwoGroups,
  E_BAD_NUMBER: checkBadNumber,
  E_NEGATIVE_SIZE: checkNegativeSize,
  E_EMPTY_LABEL: checkEmptyLabel,
  E_TOO_LARGE: checkTooLarge,
});

export function render(template, params) {
  return template.replace(/\{([A-Za-z]+)\}/g, (whole, name) =>
    Object.hasOwn(params, name) ? params[name] : whole,
  );
}

const INDEX = /^[0-9]+$/;

/**
 * Compare two JSON Pointers: array indexes compare as numbers and sort before
 * names, and a path sorts before the paths below it. Same rule as path_key()
 * in the Python implementation.
 */
export function comparePaths(a, b) {
  const sa = a.split('/').slice(1);
  const sb = b.split('/').slice(1);
  const n = Math.min(sa.length, sb.length);
  for (let i = 0; i < n; i += 1) {
    const x = sa[i];
    const y = sb[i];
    const xi = INDEX.test(x);
    const yi = INDEX.test(y);
    if (xi && yi) {
      const d = Number(x) - Number(y);
      if (d !== 0) return d < 0 ? -1 : 1;
    } else if (xi !== yi) {
      return xi ? -1 : 1;
    } else if (x !== y) {
      return x < y ? -1 : 1;
    }
  }
  return sa.length - sb.length;
}

function compareIssues(a, b) {
  const byPath = comparePaths(a.path, b.path);
  if (byPath !== 0) return byPath;
  if (a.code === b.code) return 0;
  return a.code < b.code ? -1 : 1;
}

/**
 * Return every invariant problem in doc, sorted by path then code. Each issue
 * has code, severity, path (a JSON Pointer) and message. code, severity and
 * path are the contract shared with Python; message is for people.
 */
export function validate(doc, options) {
  const ctx = buildContext(doc, options);
  const issues = [];
  for (const [code, check] of Object.entries(CHECKS)) {
    const inv = INVARIANTS.get(code);
    for (const [path, params] of check(ctx)) {
      issues.push({ code, severity: inv.severity, path, message: render(inv.message, params) });
    }
  }
  issues.sort(compareIssues);
  return issues;
}

export function hasErrors(issues) {
  return issues.some((issue) => issue.severity === 'error');
}
