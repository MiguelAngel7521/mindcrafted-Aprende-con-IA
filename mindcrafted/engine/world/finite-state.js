/* Finite selectors: pure state transitions, with strict saved-state validation. */
(function (root) {
  'use strict';
  function check(domains, state) {
    if (!state || typeof state !== 'object' || Array.isArray(state) ||
        Object.keys(state).length !== Object.keys(domains).length ||
        Object.entries(domains).some(([key, values]) => !Object.hasOwn(state, key) || !values.includes(state[key])))
      throw new Error('STATE_ERROR: configuración fuera del dominio');
  }
  const initial = domains => Object.fromEntries(Object.entries(domains).map(([key, values]) => [key, values[0]]));
  function transition(domains, state, action) {
    check(domains, state);
    if (action && Object.keys(action).length === 1 && action.type === 'reset') return initial(domains);
    if (action && Object.keys(action).length === 1 && action.type === 'submit') return {...state};
    if (!action || Object.keys(action).length !== 2 || action.type !== 'control' || typeof action.controlId !== 'string' || !Object.hasOwn(domains, action.controlId))
      throw new Error('ACTION_ERROR: acción no declarada');
    const values = domains[action.controlId];
    return {...state, [action.controlId]: values[(values.indexOf(state[action.controlId]) + 1) % values.length]};
  }
  const finiteState = {check, initial, transition};
  Object.assign(root.MindCraftedWorld ||= {}, {finiteState});
  if (typeof module !== 'undefined') module.exports = {finiteState};
})(typeof window === 'undefined' ? globalThis : window);
