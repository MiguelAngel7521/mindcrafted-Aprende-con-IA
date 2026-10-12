/* Read-only context and constrained wording. Never receives runtime mutation tools. */
(function(root) {
  'use strict';
  const contract = typeof module !== 'undefined' ? require('./npc-contract.js') : root.MindCraftedNPCContract;
  const copy = v => JSON.parse(JSON.stringify(v));
  const count = n => Number.isFinite(n) ? Math.max(0,Math.min(1000000,Math.floor(n))) : 0;
  const prefixes = {mentor:'Vamos paso a paso. ',engineer:'Revisemos el sistema. ',operator:'Comprobemos el estado. ',researcher:'Observemos la evidencia. ',rival:'Puedes superar este reto. ',guide:'Sigamos el recorrido. '};
  function hintPolicy(progress, mastery) {
    const hints=count(progress.hintsUsed), failures=Math.max(count(progress.errors),count(progress.repeatedErrors));
    const delay=mastery.length && mastery.every(x=>x.mastery>=.8) ? 1 : 0;
    if(failures>=6+delay && hints>=3 && progress.resets>=1) return 4;
    if(failures>=4+delay && hints>=2) return 3;
    if(failures>=2 && hints>=1) return 2;
    return 1;
  }
  function validateDialogue(value, context) {
    const schema=contract.dialogue;
    if(!value || typeof value!=='object' || Array.isArray(value) || JSON.stringify(value).length>8000) throw Error('DIALOGUE_SCHEMA_ERROR');
    if(Object.keys(value).some(k=>!schema.properties[k]) || schema.required.some(k=>!(k in value))) throw Error('DIALOGUE_SCHEMA_ERROR');
    for(const [key,field] of Object.entries(schema.properties)) {
      const v=value[key];
      if(field.type==='string' && (typeof v!=='string' || (field.minLength && v.length<field.minLength) || (field.maxLength && v.length>field.maxLength))) throw Error('DIALOGUE_SCHEMA_ERROR');
      if(field.type==='integer' && (!Number.isInteger(v) || v<field.minimum || v>field.maximum)) throw Error('DIALOGUE_SCHEMA_ERROR');
      if(field.type==='array' && (!Array.isArray(v) || v.length>field.maxItems || v.some(x=>typeof x!=='string'))) throw Error('DIALOGUE_SCHEMA_ERROR');
      if(field.enum && !field.enum.includes(v)) throw Error('DIALOGUE_SCHEMA_ERROR');
    }
    if(value.hintLevel!==context.maxHintLevel || value.intent!==context.intent) throw Error('HINT_LEVEL_OR_INTENT_VIOLATION');
    if(!context.allowedTexts.includes(value.text)) throw Error('UNVERIFIED_WORDING_OR_SPOILER');
    if(JSON.stringify(value.referencedConcepts)!==JSON.stringify(context.concepts) || JSON.stringify(value.sourceRefs)!==JSON.stringify(context.allowedSourceRefs) || value.kind!==(context.intent==='hint'?'academic_fact':'narrative_fiction')) throw Error('DIALOGUE_GROUNDING_ERROR');
    if(value.kind==='academic_fact' && !value.sourceRefs.length) throw Error('DIALOGUE_GROUNDING_ERROR');
    return copy(value);
  }
  function contextual(c) {
    return {text:c.allowedTexts[0],emotion:c.progress.solved?'proud':'encouraging',intent:c.intent,hintLevel:c.maxHintLevel,
      kind:c.intent==='hint'?'academic_fact':'narrative_fiction',referencedConcepts:copy(c.concepts),sourceRefs:copy(c.allowedSourceRefs)};
  }
  class NPCContextSystem {
    constructor(engine) {
      this.engine=engine;this.profiles={};this.provider=null;this.readMastery=()=>.25;this.response=null;this.sequence=0;this.diagnostics=[];
      engine.state.npcMemory={};
      engine.systemEvents.on('puzzle.failed',({puzzleId})=>{
        const p=engine.puzzles.get(puzzleId),m=this.memory(p),s=engine.state.puzzles[puzzleId];
        const signature=Object.entries(s.effect?.rules||{}).filter(([,ok])=>!ok).map(([id])=>id).sort().join('|').slice(0,512);
        m.repeatedErrors=m.errorSignature===signature?count(m.repeatedErrors+1):1;m.errorSignature=signature;
      });
      engine.systemEvents.on('puzzle.reset',()=>this.cancel());
    }
    configure({profiles={},provider=null,readMastery=()=>.25}={}) {
      this.profiles=copy(profiles);this.provider=typeof provider==='function'?provider:null;this.readMastery=readMastery;this.cancel();
    }
    profile(p) {
      const value=this.profiles[p.id]||{},schema=contract.profile.properties;
      return {role:schema.role.enum.includes(value.role)?value.role:'mentor',mode:schema.mode.enum.includes(value.mode)?value.mode:'CONTEXTUAL'};
    }
    memory(p) {
      const all=this.engine.state.npcMemory ||= {};
      return all[p.id] ||= {met:false,previousQuest:null,hintsRequested:0,lastHintLevel:0,bossCompleted:false,reactions:[],errorSignature:'',repeatedErrors:0};
    }
    cancel() { this.sequence++;this.response=null; }
    build(p, intent='reaction') {
      const e=this.engine,s=e.state.puzzles[p.id],phase=e.bossSystem.context(p.id);
      if(phase && !s.solved && !e.bossSystem.allowed(p.id)) throw Error('NPC_FUTURE_PHASE_FORBIDDEN');
      const npc=[...e.entities.values()].find(n=>n.type==='npc'&&n.puzzleId===p.id),m=e.state.npcMemory?.[p.id]||{met:false,repeatedErrors:0},profile=this.profile(p);
      const facts=p.knowledge.requiredRules.slice(0,12).map((r,i)=>({id:'fact_'+i,concept:r.skill.slice(0,128),quote:r.evidence.slice(0,600)}));
      const mastery=p.knowledge.requiredRules.slice(0,12).map(r=>({skill:r.skill.slice(0,128),mastery:Math.max(0,Math.min(1,Number(this.readMastery(r.skill))||0))}));
      const progress={attempts:count(s.attempts),errors:count(s.errors),resets:count(s.restarts),hintsUsed:count(s.hintsUsed),repeatedErrors:count(m.repeatedErrors),solved:s.solved};
      const level=intent==='hint'?hintPolicy(progress,mastery):0;
      const completed=!!phase && e.state.bosses[phase.bossId].status==='complete';
      let text;
      if(intent==='hint') text=e.hintText(p,level);
      else if(completed) text='Completaste la recuperación. El lugar vuelve a funcionar gracias a tu trabajo.';
      else if(s.solved) text='El mecanismo está restaurado. Ya puedes continuar por la ruta abierta.';
      else if(s.restarts) text='Puedes reconstruir este intento sin perder lo que ya resolviste.';
      else if(s.errors) text=`El último intento no funcionó. Llevas ${count(s.errors)} errores; podemos revisar una pista antes de probar otra vez.`;
      else text=m.met?'Seguimos aquí. Observa el mecanismo y prueba cuando estés listo.':'Bienvenido. Estoy aquí para acompañarte; observa el mecanismo antes de comenzar.';
      text=text.slice(0,1600);
      const context={version:1,npc:npc.id,role:profile.role,region:e.region.id,quest:e.quest(p.id).id,
        stage:s.solved?'completed':e.state.quests[e.quest(p.id).id]==='active'?'active':'ready',puzzle:p.id,archetype:p.archetype,
        objective:p.objective.slice(0,800),concepts:[...new Set(facts.map(f=>f.concept))],evidence:facts,progress,mastery,
        completedObjectives:[...e.puzzles.values()].filter(p=>e.state.puzzles[p.id].solved).map(p=>p.id).slice(0,12),
        flags:p.success.setFlags.filter(f=>e.state.flags[f]).slice(0,12),phase:phase?.phaseId||null,bossCompleted:completed,met:m.met,
        intent,maxHintLevel:level,allowedTexts:[text,prefixes[profile.role]+text],allowedSourceRefs:intent==='hint'?facts.map(f=>f.id):[]};
      const size=()=>new TextEncoder().encode(JSON.stringify(context)).length;
      if(size()>24000)context.evidence=context.evidence.map(f=>({...f,quote:f.quote.slice(0,120)}));
      if(size()>24000)context.allowedTexts=[text.slice(0,1000)];
      if(size()>24000) throw Error('NPC_CONTEXT_TOO_LARGE');
      return context;
    }
    present(p,intent,deliver) {
      const c=this.build(p,intent),fallback=contextual(c),m=this.memory(p);
      m.met=true;m.previousQuest=c.quest;m.hintsRequested=c.progress.hintsUsed;m.lastHintLevel=c.maxHintLevel;m.bossCompleted=c.bossCompleted;
      const reaction=c.bossCompleted?'boss_completed':c.progress.solved?'solved':c.intent==='hint'?'hint_'+c.maxHintLevel:c.progress.resets?'recovery':c.progress.errors?'failure':'intro';
      if(!m.reactions.includes(reaction))m.reactions=[...m.reactions,reaction].slice(-8);
      const token=++this.sequence;
      deliver(fallback); // Always immediate; network never blocks gameplay or persistence.
      if(this.profile(p).mode!=='AI_DYNAMIC' || !this.provider) return fallback;
      const identity=JSON.stringify(this.build(p,intent));
      let timer;
      const controller=new AbortController();
      Promise.race([Promise.resolve().then(()=>this.provider(copy(c),{signal:controller.signal})),new Promise((_,reject)=>{timer=setTimeout(()=>{controller.abort();reject(Error('NPC_PROVIDER_TIMEOUT'));},2500);})])
        .then(result=>{
          if(token!==this.sequence || JSON.stringify(this.build(p,intent))!==identity)return;
          deliver(validateDialogue(result.dialogue||result,c));
        }).catch(error=>{this.diagnostics=[...this.diagnostics,{result:'FALLBACK',category:error.message==='NPC_PROVIDER_TIMEOUT'?'NPC_PROVIDER_TIMEOUT':'NPC_RESPONSE_REJECTED'}].slice(-16);})
        .finally(()=>clearTimeout(timer));
      return fallback;
    }
    open(p) {
      if(this.profile(p).mode==='STATIC') {this.cancel();const m=this.memory(p);m.met=true;m.previousQuest=this.engine.quest(p.id).id;return;}
      this.present(p,this.memory(p).met?'reaction':'intro',answer=>{this.response={puzzle:p.id,answer};this.engine.changed();});
    }
    hint(p) {
      this.present(p,'hint',answer=>{this.response={puzzle:p.id,answer};this.engine.message(answer.text);});
    }
    restore(raw) {
      this.cancel();this.engine.state.npcMemory={};
      for(const p of this.engine.puzzles.values()) {
        const v=raw?.[p.id];if(!v || typeof v!=='object')continue;
        const m=this.memory(p),s=this.engine.state.puzzles[p.id];
        m.met=v.met===true;m.previousQuest=m.met?this.engine.quest(p.id).id:null;
        m.hintsRequested=count(s.hintsUsed);m.lastHintLevel=Math.min(4,count(v.lastHintLevel));
        m.bossCompleted=v.bossCompleted===true&&!!this.engine.bossSystem.context(p.id)&&this.engine.state.bosses[this.engine.bossSystem.context(p.id).bossId].status==='complete';
        m.reactions=Array.isArray(v.reactions)?[...new Set(v.reactions.filter(x=>['intro','failure','recovery','solved','boss_completed','hint_1','hint_2','hint_3','hint_4'].includes(x)))].slice(-8):[];
        const allowed=new Set(p.knowledge.requiredRules.map(r=>r.id));
        m.errorSignature=typeof v.errorSignature==='string'&&v.errorSignature.split('|').every(x=>allowed.has(x))?v.errorSignature:'';
        m.repeatedErrors=Math.min(count(s.errors),count(v.repeatedErrors));
      }
    }
  }
  const api={NPCContextSystem,hintPolicy,validateDialogue,contextualNPC:contextual};
  Object.assign(root.MindCraftedWorld ||= {},api);
  if(typeof module!=='undefined')module.exports=api;
})(typeof window==='undefined'?globalThis:window);
