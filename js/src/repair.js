// repair(doc): fix only the problems that have one obviously right answer.
//
// Fixed automatically: E_DANGLING_EDGE (remove the edge),
// E_GROUP_MEMBER_MISSING (remove the member entry) and E_NODE_IN_TWO_GROUPS
// (keep the node in the first group that lists it). Everything else is left
// for a person and validate() keeps reporting it. repair is idempotent.
// Twin of src/dualval/repair.py.

import { get, isNodeRef, isObject, nodeIds } from './doc.js';

/** Codes this function fixes. test/spec.test.js checks it against the spec. */
export const REPAIRS = Object.freeze(['E_DANGLING_EDGE', 'E_GROUP_MEMBER_MISSING', 'E_NODE_IN_TWO_GROUPS']);

/**
 * Return { doc, changes }. The input is not modified. Each change has code,
 * action, path (a JSON Pointer into the input doc) and value (the removed
 * edge's id, or the removed member entry).
 */
export function repair(doc) {
  if (!isObject(doc)) throw new TypeError('doc must be a JSON object');
  const out = structuredClone(doc);
  const changes = [];
  const nodes = get(out, 'nodes');
  const ids = nodeIds(Array.isArray(nodes) ? nodes : []);

  const edges = get(out, 'edges');
  if (Array.isArray(edges)) {
    const kept = [];
    for (const [i, edge] of edges.entries()) {
      if (isObject(edge) && !(isNodeRef(get(edge, 'from'), ids) && isNodeRef(get(edge, 'to'), ids))) {
        changes.push({ code: 'E_DANGLING_EDGE', action: 'remove_edge', path: `/edges/${i}`, value: get(edge, 'id') ?? null });
        continue;
      }
      kept.push(edge);
    }
    out.edges = kept;
  }

  const groups = get(out, 'groups');
  if (Array.isArray(groups)) {
    const owner = new Map();
    for (const [gi, group] of groups.entries()) {
      if (!isObject(group) || !Array.isArray(get(group, 'members'))) continue;
      const members = [];
      for (const [mj, member] of group.members.entries()) {
        const path = `/groups/${gi}/members/${mj}`;
        if (!isNodeRef(member, ids)) {
          changes.push(memberChange('E_GROUP_MEMBER_MISSING', path, member));
          continue;
        }
        if (!owner.has(member)) owner.set(member, gi);
        if (owner.get(member) !== gi) {
          changes.push(memberChange('E_NODE_IN_TWO_GROUPS', path, member));
          continue;
        }
        members.push(member);
      }
      group.members = members;
    }
  }

  return { doc: out, changes };
}

function memberChange(code, path, member) {
  return { code, action: 'remove_member', path, value: member ?? null };
}
