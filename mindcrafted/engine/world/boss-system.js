/* Composition only: the existing WorldEngine/archetypes arbitrate every phase. */
(function(root) {
  'use strict';
  const copy = v => JSON.parse(JSON.stringify(v));
  function applyBindings(mechanics, phase, shared) {
    const m = copy(mechanics);
    for (const b of phase.bindings) {
      if (!Number.isInteger(shared[b.variable])) throw new Error('BOSS_SHARED_STATE_ERROR: missing input');
      const rule = (b.kind === 'resource_capacity' ? m.allocationRules : m.configurationRules).find(r => r.kind === 'capacity' && r.ruleId === b.ruleId);
      const target = b.kind === 'resource_capacity' ? rule?.limits.find(l => l.target === b.targetId) : rule;
      if (!target) throw new Error('BOSS_REFERENCE_ERROR: invalid binding');
      target.max = shared[b.variable];
    }
    return m;
  }
  function outputs(phase, puzzleState, shared) {
    const next = {...shared};
    for (const output of phase.exports) {
      const value = output.kind === 'edge_present' ? puzzleState.connections.includes(output.controlId) : puzzleState.configuration[output.controlId];
      const found = output.cases.find(c => c.when === value);
      if (!found) throw new Error('BOSS_SHARED_STATE_ERROR: output case missing');
      next[output.variable] = found.value;
    }
    return next;
  }
  class BossSystem {
    constructor(engine) {
      this.engine = engine; this.bosses = engine.spec.bosses || [];
      this.base = new Map([...engine.puzzles].map(([id,p]) => [id,copy(p.mechanics)]));
      this.reconcile();
      engine.systemEvents.on('puzzle.started', ({puzzleId}) => {
        const context = this.context(puzzleId); if (!context) return;
        this.reconcile();
        if (context.phaseIndex === 0) engine.emit('boss.started', context);
        engine.emit('boss.phase.started', context);
      });
      engine.systemEvents.on('puzzle.solved', ({puzzleId}) => {
        const context = this.context(puzzleId); if (!context) return;
        this.reconcile();
        engine.emit('boss.phase.completed', {...context,shared:copy(engine.state.bosses[context.bossId].shared)});
        if (engine.state.bosses[context.bossId].status === 'complete') engine.emit('boss.completed', context);
      });
      engine.systemEvents.on('puzzle.failed', ({puzzleId}) => {
        const context = this.context(puzzleId); if (!context) return;
        this.reconcile(); engine.emit('boss.phase.failed', context);
      });
      engine.systemEvents.on('puzzle.reset', ({puzzleId,manual}) => {
        const context = this.context(puzzleId); if (!context) return;
        this.reconcile(); engine.emit('boss.recovered', {...context,manual,shared:copy(engine.state.bosses[context.bossId].shared)});
      });
    }
    context(puzzleId) {
      for (const b of this.bosses) {
        const index = b.phases.findIndex(p => p.puzzleId === puzzleId);
        if (index >= 0) return {worldId:this.engine.spec.id,bossId:b.id,phaseId:b.phases[index].id,phaseIndex:index};
      }
      return null;
    }
    allowed(puzzleId) {
      const context = this.context(puzzleId);
      return !context || this.engine.state.bosses[context.bossId].phaseIndex === context.phaseIndex;
    }
    currentPuzzle() {
      const b = this.bosses[0], progress = b && this.engine.state.bosses[b.id];
      return b && progress.phaseIndex < b.phases.length ? this.engine.puzzles.get(b.phases[progress.phaseIndex].puzzleId) : null;
    }
    prepareRestore() {
      for (const [id,m] of this.base) this.engine.puzzles.get(id).mechanics = copy(m);
      this.reconcile();
    }
    reconcile() {
      if (!this.bosses.length) return;
      const e = this.engine;
      e.state.bosses = {};
      for (const b of this.bosses) {
        let shared = {}, index = 0, failed = 0, recoveries = 0;
        for (const phase of b.phases) {
          const p = e.puzzles.get(phase.puzzleId), state = e.state.puzzles[p.id];
          p.mechanics = applyBindings(this.base.get(p.id), phase, shared);
          failed += state.errors; recoveries += state.restarts + (b.failurePolicy === 'checkpoint' ? state.errors : 0);
          if (!state.solved) break;
          shared = outputs(phase,state,shared); index++;
        }
        e.state.bosses[b.id] = {phaseIndex:index,shared,status:index===b.phases.length?'complete':
          e.state.quests[e.quest(b.phases[index].puzzleId)?.id] === 'active' ? 'active' : 'ready',
          failures:failed,recoveries};
      }
    }
  }
  Object.assign(root.MindCraftedWorld ||= {}, {BossSystem,applyBossBindings:applyBindings,bossOutputs:outputs});
  if (typeof module !== 'undefined') module.exports = {BossSystem,applyBossBindings:applyBindings,bossOutputs:outputs};
})(typeof window === 'undefined' ? globalThis : window);
