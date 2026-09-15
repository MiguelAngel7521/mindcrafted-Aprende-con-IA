/* Directed graph decisions over validated data. No UI and no generated code. */
(function (root) {
  'use strict';
  function nodeConnectResult(m, connections, ignoredRule = null) {
    if (!Array.isArray(connections)) throw new Error('STATE_ERROR: las conexiones deben ser una lista');
    const selected = new Set(connections), edges = new Map(m.edges.map(e => [e.id, e]));
    if (selected.size !== connections.length || connections.some(id => !edges.has(id))) throw new Error('STATE_ERROR: conexiones desconocidas o duplicadas');
    const nodes = new Map(m.nodes.map(n => [n.id, n]));
    const active = m.edges.filter(e => selected.has(e.id));
    const adjacency = new Map(m.nodes.map(n => [n.id, []]));
    for (const edge of active) adjacency.get(edge.source).push(edge.target);
    function reachable(start, target) {
      const queue = [...adjacency.get(start)], seen = new Set();
      while (queue.length) {
        const next = queue.pop();
        if (next === target) return true;
        if (seen.has(next)) continue;
        seen.add(next); queue.push(...adjacency.get(next));
      }
      return false;
    }
    const rules = Object.fromEntries([...m.connectionRules, ...m.goals].map(r => [r.ruleId, true]));
    const invalidEdges = new Set(), degreeErrors = new Set(), unreachable = [], cycleNodes = [];
    for (const rule of m.connectionRules) {
      if (rule.ruleId === ignoredRule) continue;
      if (rule.kind === 'compatible') {
        for (const edge of active) {
          if (!rule.allowed.some(pair => pair.sourceKind === nodes.get(edge.source).kind && pair.targetKind === nodes.get(edge.target).kind)) {
            invalidEdges.add(edge.id); rules[rule.ruleId] = false;
          }
        }
      } else if (rule.kind === 'degree') {
        const count = active.filter(e => (rule.direction === 'in' ? e.target : e.source) === rule.node).length;
        if (count < rule.min || count > rule.max) { degreeErrors.add(rule.node); rules[rule.ruleId] = false; }
      } else if (rule.kind === 'acyclic') {
        const cycles = m.nodes.filter(node => reachable(node.id, node.id)).map(node => node.id);
        if (cycles.length) { cycleNodes.push(...cycles); rules[rule.ruleId] = false; }
      }
    }
    m.goals.forEach((goal, index) => {
      if (goal.ruleId !== ignoredRule && !reachable(goal.source, goal.target)) { unreachable.push(index); rules[goal.ruleId] = false; }
    });
    return {ok: active.length > 0 && Object.values(rules).every(Boolean), rules,
      connections: active.map(e => e.id), invalidEdges: [...invalidEdges].sort(), unreachable,
      degreeErrors: [...degreeErrors].sort(), cycleNodes: [...new Set(cycleNodes)].sort()};
  }
  Object.assign(root.MindCraftedWorld ||= {}, {nodeConnectResult});
  if (typeof module !== 'undefined') module.exports = {nodeConnectResult};
})(typeof window === 'undefined' ? globalThis : window);
