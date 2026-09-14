/* Compose validated WorldSpecs without sharing puzzle IDs or changing the canvas. */
(function (root) {
  'use strict';
  const core = root.MindCraftedWorld || (typeof require === 'function' ? require('./core.js') : null);
  if (!core?.WorldEngine || !core?.EventBus) throw new Error('WorldEngine debe cargarse antes de CampaignSession');
  const {WorldEngine, EventBus} = core;
  const record = value => value !== null && typeof value === 'object' && !Array.isArray(value);
  const copy = value => JSON.parse(JSON.stringify(value));
  const validId = value => typeof value === 'string' && /^[a-zA-Z0-9_.-]{1,128}$/.test(value) && value !== '.' && !value.includes('..');
  const digest = value => typeof value === 'string' && /^[a-f0-9]{64}$/.test(value);

  class CampaignSession {
    constructor(campaign, {events = new EventBus()} = {}) {
      if (!record(campaign) || campaign.format !== 'mindcrafted-campaign' || campaign.version !== 2 ||
          !validId(campaign.id) || typeof campaign.title !== 'string' || !campaign.title.length || campaign.title.length > 2000 ||
          !Array.isArray(campaign.regions) || campaign.regions.length < 1 || campaign.regions.length > 24) {
        throw new Error('CampaignPackage incompatible');
      }
      const ids = new Set();
      for (const region of campaign.regions) {
        if (!record(region) || !validId(region.id) || ids.has(region.id) || !digest(region.worldHash) ||
            !digest(region.sourceHash) || !record(region.world)) throw new Error('Región de campaña incompatible');
        ids.add(region.id);
      }
      if (!events || typeof events.on !== 'function' || typeof events.emit !== 'function') throw new Error('EventBus incompatible');
      this.events = events;
      this._regions = copy(campaign.regions);
      this._index = 0;
      // Each lesson keeps its own flags, entities, dialogues and puzzle state.
      this._engines = this._regions.map(region => new WorldEngine(region.world, {events: this.events}));
    }

    get engine() { return this._engines[this._index]; }
    get index() { return this._index; }
    get completed() { return this._engines.every(engine => engine.state.completed); }
    get xp() { return this._engines.slice(0, this._index + 1).reduce((total, engine) => total + engine.state.xp, 0); }
    get inventory() { return this._engines.slice(0, this._index + 1).flatMap(engine => engine.state.inventory); }

    advance() {
      if (!this.engine.state.completed || this._index + 1 >= this._engines.length) return false;
      this._index++;
      this._changedRegion();
      return true;
    }

    _changedRegion() {
      this.events.emit('campaign.region.changed', {index: this._index, regionId: this._regions[this._index].id});
      // SaveSystem listeners see the committed region, including on a transition.
      this.engine.changed();
    }

    snapshot() {
      return {version: 2, currentRegion: this._index, regions: this._regions.map((region, index) => ({
        id: region.id, worldHash: region.worldHash, state: this._engines[index].snapshot()
      }))};
    }

    restore(raw) {
      if (!record(raw) || raw.version !== 2 || !Number.isInteger(raw.currentRegion) || raw.currentRegion < 0 ||
          raw.currentRegion >= this._regions.length || !Array.isArray(raw.regions) || raw.regions.length !== this._regions.length) return false;
      for (let index = 0; index < this._regions.length; index++) {
        const saved = raw.regions[index], region = this._regions[index];
        if (!record(saved) || saved.id !== region.id || saved.worldHash !== region.worldHash || !record(saved.state)) return false;
      }
      let restored;
      try {
        // Stage on isolated buses: a rejected load must neither mutate live state nor emit rewards/events.
        restored = this._regions.map(region => new WorldEngine(region.world));
        for (let index = 0; index <= raw.currentRegion; index++) {
          if (!restored[index].restore(raw.regions[index].state)) return false;
          if (index < raw.currentRegion && !restored[index].state.completed) return false;
        }
        // Later regions are unvisited. Discard any stored solutions or rewards for them.
      } catch (_) { return false; }
      this._engines = restored;
      this._index = raw.currentRegion;
      for (const engine of this._engines) engine.events = this.events;
      this._changedRegion();
      return true;
    }
  }

  core.CampaignSession = CampaignSession;
  if (typeof module !== 'undefined') module.exports = {CampaignSession};
})(typeof window === 'undefined' ? globalThis : window);
