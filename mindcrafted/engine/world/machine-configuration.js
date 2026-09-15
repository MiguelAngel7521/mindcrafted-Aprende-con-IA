/* Declarative component/parameter rules; no renderer or generated executable code. */
(function (root) {
  'use strict';
  const {finiteState: finite} = typeof module !== 'undefined' ? require('./finite-state.js') : root.MindCraftedWorld;
  function domains(m) {
    const result = Object.fromEntries(m.slots.map(s => [s.id, [null, ...s.components]]));
    for (const p of m.parameters) {
      const values = p.values.map(v => v.id), start = values.indexOf(p.initial);
      result[p.id] = [...values.slice(start), ...values.slice(0, start)];
    }
    return result;
  }
  function result(m, state, ignoredRule = null) {
    finite.check(domains(m), state);
    const rules = Object.fromEntries([...m.configurationRules, ...m.goals].map(r => [r.ruleId, true]));
    const failures = [], affected = new Set(), capacities = [];
    const holds = c => c.values.includes(state[c.control]);
    for (const rule of [...m.configurationRules, ...m.goals]) {
      if (rule.ruleId === ignoredRule) continue;
      let ok, controls;
      if (rule.kind === 'required') {
        ok = holds(rule.condition); controls = [rule.condition.control];
      } else if (rule.kind === 'dependency') {
        ok = !holds(rule.when) || holds(rule.then); controls = [rule.when.control, rule.then.control];
      } else if (rule.kind === 'exclusion') {
        ok = !(holds(rule.left) && holds(rule.right)); controls = [rule.left.control, rule.right.control];
      } else if (rule.kind === 'range') {
        const parameter = m.parameters.find(p => p.id === rule.control);
        const quantity = parameter.values.find(v => v.id === state[parameter.id]).quantity;
        ok = quantity >= rule.min && quantity <= rule.max; controls = [parameter.id];
      } else {
        const load = rule.terms.reduce((sum, t) => sum + (t.costs.find(c => c.value === state[t.control])?.amount || 0), 0);
        ok = load <= rule.max; controls = rule.terms.map(t => t.control);
        capacities.push({ruleId: rule.ruleId, load, max: rule.max, unit: rule.unit});
      }
      rules[rule.ruleId] &&= ok;
      if (!ok) {
        controls.forEach(id => affected.add(id));
        failures.push({kind: rule.kind, ruleId: rule.ruleId, controls});
      }
    }
    return {ok: Object.values(rules).every(Boolean), rules, configuration: {...state}, failures,
      affectedControls: [...affected].sort(), capacities};
  }
  const machineConfiguration = {domains, result, initial: m => finite.initial(domains(m)),
    transition: (m, state, action) => finite.transition(domains(m), state, action)};
  Object.assign(root.MindCraftedWorld ||= {}, {machineConfiguration});
  if (typeof module !== 'undefined') module.exports = {machineConfiguration};
})(typeof window === 'undefined' ? globalThis : window);
