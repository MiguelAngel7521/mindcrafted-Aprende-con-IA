(function (root) {
  'use strict';
  class QuestSystem {
    constructor({quests, state, events, emit}) {
      this.quests = quests; this.state = state; this.emit = emit;
      events.on('dialogue.effect', effect => { if (effect.type === 'startQuest') this.start(effect.target); });
      events.on('puzzle.solved', ({puzzleId}) => this.complete(puzzleId));
    }
    forPuzzle(puzzleId) { return this.quests.find(q => q.puzzleId === puzzleId); }
    active(puzzleId) { return this.state().quests[this.forPuzzle(puzzleId)?.id] === 'active'; }
    start(questId) {
      const quest = this.quests.find(q => q.id === questId);
      if (!quest || this.state().quests[questId]) return false;
      this.state().quests[questId] = 'active';
      this.emit('quest.started', {questId});
      this.emit('puzzle.started', {puzzleId: quest.puzzleId});
      return true;
    }
    complete(puzzleId) {
      const quest = this.forPuzzle(puzzleId);
      if (!quest || this.state().quests[quest.id] === 'complete') return false;
      this.state().quests[quest.id] = 'complete';
      this.emit('quest.completed', {questId: quest.id, puzzleId});
      return true;
    }
  }
  Object.assign(root.MindCraftedWorld ||= {}, {QuestSystem});
  if (typeof module !== 'undefined') module.exports = {QuestSystem};
})(typeof window === 'undefined' ? globalThis : window);
