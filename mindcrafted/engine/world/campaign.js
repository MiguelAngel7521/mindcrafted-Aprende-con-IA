/* Compose validated WorldSpecs without sharing puzzle IDs or changing the canvas. */
(function (root) {
  'use strict';
  const core = root.MindCraftedWorld || (typeof require === 'function' ? require('./core.js') : null);
  if (!core?.WorldEngine || !core?.EventBus) throw new Error('WorldEngine debe cargarse antes de CampaignSession');
  const {WorldEngine, EventBus} = core;
  const difficulty = root.MindCraftedDifficulty || (typeof require === 'function' ? require('./difficulty-policy.js') : null);
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
      this.readMastery = () => null;
      this.decisions = {};
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
      this.selectNext(this._index + 1);
      this._index++;
      this._changedRegion();
      return true;
    }

    selectNext(index) {
      if(index!==this._index+1 || !this.engine.state.completed) throw Error('MID_PUZZLE_ADAPTATION_FORBIDDEN');
      const region=this._regions[index],catalog=region.adaptive;
      if(!catalog || this.decisions[index]) return;
      if(region.world.bosses?.length || catalog.policyVersion!==1)throw Error('ADAPTATION_BOUNDARY_FORBIDDEN');
      const puzzle=region.world.puzzles[0],skills=[...new Set(puzzle.knowledge.requiredRules.map(r=>r.skill))];
      const records=skills.map(skill=>this.readMastery(skill)).filter(Boolean).map(r=>({skill:r.skillId,mastery:r.mastery,attempts:r.attempts}));
      const history=[];
      for(let i=0;i<=this._index;i++)for(const p of this._engines[i].puzzles.values()) {
        if(!skills.every(skill=>p.knowledge.requiredRules.some(r=>r.skill===skill)))continue;
        const s=this._engines[i].state.puzzles[p.id];
        history.push({id:this._regions[i].id+':'+p.id,success:s.solved,errors:s.errors,hints:s.hintsUsed,resets:s.restarts});
      }
      const previousEntries=Object.entries(this.decisions).filter(([,d])=>d.input.objective===catalog.objective);
      const last=previousEntries.at(-1), previous=last?last[1].decision.selectedDifficulty:catalog.base;
      const lastChange=previousEntries.filter(([,d])=>d.decision.selectedDifficulty!==d.decision.previousDifficulty).at(-1);
      const sinceChange=lastChange?this._engines.slice(Number(lastChange[0]),index).reduce((count,engine)=>count+
        [...engine.puzzles.values()].filter(p=>engine.state.puzzles[p.id].solved && skills.every(skill=>p.knowledge.requiredRules.some(r=>r.skill===skill))).length,0):catalog.policy?.cooldown||2;
      const input={challengeId:region.id,objective:catalog.objective,archetype:puzzle.archetype,base:catalog.base,previous,policy:catalog.policy||{},
        records:records.length===skills.length?records:[],history:history.slice(-24),sinceChange};
      const decision=difficulty.recommend(input),variant=catalog.variants.find(v=>v.level===decision.selectedDifficulty);
      if(!variant)throw Error('MISSING_DIFFICULTY_VARIANT');
      const engine=new WorldEngine(variant.world,{events:this.events});
      engine.difficultyDecision={...decision,parameters:{...decision.parameters,...variant.parameters}};
      this.decisions[index]={input,decision,worldHash:variant.worldHash};this._engines[index]=engine;
      this.events.emit('difficulty.selected',copy(engine.difficultyDecision));
    }

    _changedRegion() {
      this.events.emit('campaign.region.changed', {index: this._index, regionId: this._regions[this._index].id});
      // SaveSystem listeners see the committed region, including on a transition.
      this.engine.changed();
    }

    snapshot() {
      return {version: 2, currentRegion: this._index, regions: this._regions.map((region, index) => ({
        id: region.id, worldHash: region.worldHash, state: this._engines[index].snapshot(),
        ...(this.decisions[index]?{adaptation:copy(this.decisions[index])}:{})
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
      const decisions={};
      try {
        // Stage on isolated buses: a rejected load must neither mutate live state nor emit rewards/events.
        restored = this._regions.map(region => new WorldEngine(region.world));
        for (let index = 0; index <= raw.currentRegion; index++) {
          const saved=raw.regions[index].adaptation,catalog=this._regions[index].adaptive;
          if(catalog && index>0){
            if(!saved || saved.input.challengeId!==this._regions[index].id || saved.input.objective!==catalog.objective ||
               saved.input.base!==catalog.base || saved.input.archetype!==this._regions[index].world.puzzles[0].archetype ||
               JSON.stringify(saved.input.policy)!==JSON.stringify(catalog.policy||{})) return false;
            difficulty.verifySuggestion(saved.input,saved.decision);
            const variant=catalog.variants.find(v=>v.level===saved.decision.selectedDifficulty && v.worldHash===saved.worldHash);
            if(!variant)return false;
            restored[index]=new WorldEngine(variant.world);
            restored[index].difficultyDecision={...copy(saved.decision),parameters:{...saved.decision.parameters,...variant.parameters}};
            decisions[index]=copy(saved);
          }else if(saved)return false;
          if (!restored[index].restore(raw.regions[index].state)) return false;
          if (index < raw.currentRegion && !restored[index].state.completed) return false;
        }
        // Later regions are unvisited. Discard any stored solutions or rewards for them.
      } catch (_) { return false; }
      this._engines = restored;
      this.decisions = decisions;
      this._index = raw.currentRegion;
      for (const engine of this._engines) engine.events = this.events;
      this._changedRegion();
      return true;
    }
  }

  core.CampaignSession = CampaignSession;
  if (typeof module !== 'undefined') module.exports = {CampaignSession};
})(typeof window === 'undefined' ? globalThis : window);
