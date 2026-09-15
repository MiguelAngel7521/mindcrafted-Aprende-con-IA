/* Resource arbitration is independent of the renderer and academic subject. */
(function (root) {
  'use strict';
  const {finiteState: finite} = typeof module !== 'undefined' ? require('./finite-state.js') : root.MindCraftedWorld;
  const domains = m => Object.fromEntries(m.loads.map(l => [l.id, [null, ...m.targets.map(t => t.id)]]));
  function result(m, state, ignoredRule = null) {
    finite.check(domains(m), state);
    const targets = new Map(m.targets.map(t => [t.id, t]));
    const loads = Object.fromEntries(m.targets.map(t => [t.id, 0]));
    for (const load of m.loads) if (state[load.id] !== null) loads[state[load.id]] += load.amount;
    const rules = Object.fromEntries([...m.allocationRules, ...m.goals].map(r => [r.ruleId, true]));
    const incompatible = new Set(), overloaded = new Set();
    for (const rule of m.allocationRules) {
      if (rule.ruleId === ignoredRule) continue;
      const wrong = rule.kind === 'compatible'
        ? m.loads.filter(l => state[l.id] !== null && !rule.allowed.some(p => p.sourceKind === l.kind && p.targetKind === targets.get(state[l.id]).kind)).map(l => l.id)
        : rule.limits.filter(l => loads[l.target] < l.min || loads[l.target] > l.max).map(l => l.target);
      if (wrong.length) {
        rules[rule.ruleId] = false;
        for (const id of wrong) (rule.kind === 'compatible' ? incompatible : overloaded).add(id);
      }
    }
    for (const goal of m.goals) if (goal.ruleId !== ignoredRule) rules[goal.ruleId] &&= Object.values(state).every(v => v !== null);
    return {ok: Object.values(rules).every(Boolean), rules, configuration: {...state}, loads,
      incompatible: [...incompatible].sort(), overloaded: [...overloaded].sort()};
  }
  const resourceBalance = {domains, result, initial: m => finite.initial(domains(m)),
    transition: (m, state, action) => finite.transition(domains(m), state, action)};
  Object.assign(root.MindCraftedWorld ||= {}, {resourceBalance});
  if (typeof module !== 'undefined') module.exports = {resourceBalance};
})(typeof window === 'undefined' ? globalThis : window);
