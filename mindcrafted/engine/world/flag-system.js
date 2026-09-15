/* State accessors keep systems attached when a save replaces world state. */
(function (root) {
  'use strict';
  class FlagSystem {
    constructor({state, events, emit}) {
      this.state = state; this.emit = emit;
      events.on('dialogue.effect', effect => { if (effect.type === 'setFlag') this.set(effect.target); });
    }
    has(flag) { return this.state().flags[flag] === true; }
    set(flag) {
      if (this.has(flag)) return false;
      this.state().flags[flag] = true;
      this.emit('world.flag.set', {flag, value: true});
      return true;
    }
  }
  Object.assign(root.MindCraftedWorld ||= {}, {FlagSystem});
  if (typeof module !== 'undefined') module.exports = {FlagSystem};
})(typeof window === 'undefined' ? globalThis : window);
