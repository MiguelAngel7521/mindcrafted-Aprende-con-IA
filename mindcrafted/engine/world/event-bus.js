/* Synchronous events shared by the world systems and runtime observers. */
(function (root) {
  'use strict';
  class EventBus {
    constructor() { this.listeners = new Map(); }
    on(name, callback) {
      const group = this.listeners.get(name) || new Set();
      group.add(callback); this.listeners.set(name, group);
      return () => group.delete(callback);
    }
    emit(name, data) { for (const fn of [...(this.listeners.get(name) || [])]) fn(data); }
  }
  Object.assign(root.MindCraftedWorld ||= {}, {EventBus});
  if (typeof module !== 'undefined') module.exports = {EventBus};
})(typeof window === 'undefined' ? globalThis : window);
