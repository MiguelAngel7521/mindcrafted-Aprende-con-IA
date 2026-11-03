/* Pure policy: observations select future content; never write BKT or live rules. */
(function(root){
  'use strict';
  const levels=['EASY','NORMAL','HARD'];
  const defaults=Object.freeze({version:1,low:.45,high:.85,minEvidence:2,cooldown:2,minDifficulty:'EASY',maxDifficulty:'HARD',maxStepChange:1});
  const copy=x=>JSON.parse(JSON.stringify(x));
  function recommend({challengeId,objective,archetype,base='NORMAL',previous=base,records=[],history=[],sinceChange=2,policy={}}){
    const p={...defaults,...policy};
    if(Object.keys(p).some(k=>!(k in defaults)) || p.version!==1 || !Number.isFinite(p.low)||!Number.isFinite(p.high)||p.low<0||p.high>1||p.low>=p.high ||
      ![p.minEvidence,p.cooldown].every(x=>Number.isInteger(x)&&x>=2&&x<=20) || p.maxStepChange!==1 ||
      ![base,previous,p.minDifficulty,p.maxDifficulty].every(x=>levels.includes(x)) || levels.indexOf(p.minDifficulty)>levels.indexOf(p.maxDifficulty))throw Error('INVALID_DIFFICULTY_POLICY');
    if(!['node_connect','resource_balance','machine_configuration'].includes(archetype)||typeof objective!=='string'||!objective||typeof challengeId!=='string'||!challengeId)throw Error('INVALID_DIFFICULTY_OBJECTIVE');
    if(!Array.isArray(records)||records.length>24||records.some(r=>typeof r.skill!=='string'||!Number.isFinite(r.mastery)||r.mastery<0||r.mastery>1||!Number.isInteger(r.attempts)||r.attempts<0)||
      !Array.isArray(history)||history.length>24||history.some(h=>typeof h.id!=='string'||!Number.isInteger(h.errors)||h.errors<0||!Number.isInteger(h.hints)||h.hints<0||!Number.isInteger(h.resets)||h.resets<0||typeof h.success!=='boolean')||new Set(history.map(h=>h.id)).size!==history.length||!Number.isInteger(sinceChange)||sinceChange<0)throw Error('INVALID_MASTERY_EVIDENCE');
    let target=levels.indexOf(previous),band='unknown',reason='INSUFFICIENT_MASTERY_EVIDENCE';
    const recent=history.slice(-p.minEvidence),mastery=records.length?Math.min(...records.map(r=>r.mastery)):null;
    if(records.length&&records.every(r=>r.attempts>=p.minEvidence)&&recent.length>=p.minEvidence){
      band=mastery>=p.high?'high':mastery<=p.low?'low':'medium';
      const strong=recent.every(h=>h.success&&h.errors===0&&h.hints===0&&h.resets===0);
      const struggling=recent.every(h=>h.errors>=2||h.hints>=2||h.resets>=1);
      if(sinceChange<p.cooldown)reason='DIFFICULTY_COOLDOWN';
      else if(band==='high'&&strong){target++;reason='SUSTAINED_INDEPENDENT_SUCCESS';}
      else if((band==='low'||band==='medium')&&struggling){target--;reason='SUSTAINED_SUPPORT_NEED';}
      else reason='STABLE_EVIDENCE';
    }else target=levels.indexOf(base);
    target=Math.max(levels.indexOf(p.minDifficulty),Math.min(levels.indexOf(p.maxDifficulty),target));
    const prior=levels.indexOf(previous);target=Math.max(prior-1,Math.min(prior+1,target));
    if(target<levels.indexOf(p.minDifficulty)||target>levels.indexOf(p.maxDifficulty))throw Error('DIFFICULTY_OUT_OF_BOUNDS');
    return {policyVersion:p.version,challengeId,objective,archetype,previousDifficulty:previous,selectedDifficulty:levels[target],masteryBand:band,
      reasons:[reason],evidence:recent.map(h=>h.id),mastery,parameters:{initialHintLevel:1,scaffolding:levels[target]==='EASY'?'guided':'standard'}};
  }
  function verifySuggestion(input,suggestion){const expected=recommend(input);if(JSON.stringify(expected)!==JSON.stringify(suggestion))throw Error('AI_DIFFICULTY_POLICY_VIOLATION');return expected;}
  const api={recommend,verifySuggestion,defaults,levels,copy};root.MindCraftedDifficulty=api;if(typeof module!=='undefined')module.exports=api;
})(typeof window==='undefined'?globalThis:window);
