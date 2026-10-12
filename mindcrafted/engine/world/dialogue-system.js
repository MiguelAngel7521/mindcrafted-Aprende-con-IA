/* Dialogue remains part of the map; declarative effects flow through events. */
(function (root) {
  'use strict';
  class DialogueSystem {
    constructor({dialogues, entities, puzzles, state, events, emit, changed, npc}) {
      Object.assign(this, {dialogues, entities, puzzles, state, emit, changed, npc});
      events.on('entity.interacted', ({entityId}) => {
        const entity = entities.get(entityId), puzzle = puzzles.get(entity?.puzzleId);
        if (entity?.type === 'npc' && puzzle) this.open(state().puzzles[puzzle.id].solved ? puzzle.success.dialogue : entity.dialogueId);
      });
      events.on('puzzle.solved', ({puzzleId}) => this.open(puzzles.get(puzzleId).success.dialogue));
    }
    open(id) {
      if (!this.dialogues.has(id)) throw new Error('Diálogo inexistente');
      this.state().dialogue = {id, line: 0};
      const d=this.dialogues.get(id), entity=this.entities.get(d.speaker);
      if(entity?.puzzleId)this.npc?.open(this.puzzles.get(entity.puzzleId));
      this.changed();
    }
    line() {
      const active = this.state().dialogue;
      if(!active)return null;
      const dialogue=this.dialogues.get(active.id), p=this.puzzles.get(this.entities.get(dialogue.speaker)?.puzzleId);
      if(active.line===0 && p && this.npc && this.npc.profile(p).mode!=='STATIC') {
        const answer=this.npc.response?.puzzle===p.id?this.npc.response.answer:null;
        const text=answer?.text || this.npc.build(p,'reaction').allowedTexts[0];
        return {...dialogue.lines[active.line],text};
      }
      return dialogue.lines[active.line];
    }
    advance() {
      const state = this.state(), active = state.dialogue;
      if (!active) return;
      this.npc?.cancel();
      const dialogue = this.dialogues.get(active.id);
      if (++active.line >= dialogue.lines.length) {
        state.dialogue = null;
        if (!state.completedDialogues.includes(dialogue.id)) state.completedDialogues.push(dialogue.id);
        for (const effect of dialogue.onComplete) this.emit('dialogue.effect', {...effect});
        this.emit('npc.dialogue.completed', {npcId: dialogue.speaker, dialogueId: dialogue.id});
      }
      this.changed();
    }
  }
  Object.assign(root.MindCraftedWorld ||= {}, {DialogueSystem});
  if (typeof module !== 'undefined') module.exports = {DialogueSystem};
})(typeof window === 'undefined' ? globalThis : window);
