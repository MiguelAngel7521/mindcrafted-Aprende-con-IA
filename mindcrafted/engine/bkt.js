// Bayesian Knowledge Tracing ligero y sin dependencias.
(function(root){
  'use strict';
  var STORAGE_KEY='mindcrafted_bkt_v1';
  var DEFAULTS={initial:0.25,learn:0.12,guess:0.20,slip:0.10,masteryThreshold:0.80};

  function clamp(value,min,max){return Math.max(min,Math.min(max,Number(value)));}
  function params(custom){
    custom=custom||{};
    return {
      initial:clamp(custom.initial==null?DEFAULTS.initial:custom.initial,0.01,0.99),
      learn:clamp(custom.learn==null?DEFAULTS.learn:custom.learn,0,0.99),
      guess:clamp(custom.guess==null?DEFAULTS.guess:custom.guess,0.01,0.49),
      slip:clamp(custom.slip==null?DEFAULTS.slip:custom.slip,0.01,0.49),
      masteryThreshold:clamp(custom.masteryThreshold==null?DEFAULTS.masteryThreshold:custom.masteryThreshold,0.5,0.99)
    };
  }

  function update(prior,correct,custom){
    var p=params(custom);prior=clamp(prior,0.001,0.999);
    var knownLikelihood=correct?(1-p.slip):p.slip;
    var unknownLikelihood=correct?p.guess:(1-p.guess);
    var denominator=prior*knownLikelihood+(1-prior)*unknownLikelihood;
    var posterior=denominator>0?(prior*knownLikelihood/denominator):prior;
    return clamp(posterior+(1-posterior)*p.learn,0.001,0.999);
  }

  function memoryStorage(){
    var value=null;
    return {getItem:function(){return value;},setItem:function(_key,next){value=String(next);}};
  }

  function createTracker(options){
    options=options||{};
    var model=params(options.params);
    var scope=String(options.scope||'curso-local').slice(0,240);
    var storage=options.storage;
    if(!storage){try{storage=root.localStorage;}catch(_err){storage=null;}}
    if(!storage)storage=memoryStorage();

    function read(){
      try{
        var parsed=JSON.parse(storage.getItem(STORAGE_KEY)||'{"version":1,"skills":{}}');
        if(!parsed||typeof parsed!=='object')throw new Error('invalid');
        if(!parsed.skills||typeof parsed.skills!=='object')parsed.skills={};
        parsed.version=1;return parsed;
      }catch(_err){return {version:1,skills:{}};}
    }
    function write(state){try{storage.setItem(STORAGE_KEY,JSON.stringify(state));return true;}catch(_err){return false;}}
    function key(skillId){return scope+'::'+String(skillId||'habilidad-general').slice(0,240);}
    function get(skillId){
      var record=read().skills[key(skillId)];
      return record||{skillId:String(skillId||'habilidad-general'),label:String(skillId||'Habilidad general'),mastery:model.initial,attempts:0,correct:0,mastered:false};
    }
    function observe(skillId,correct,metadata){
      metadata=metadata||{};var state=read();var record=get(skillId);
      record.skillId=String(skillId||'habilidad-general').slice(0,240);
      record.label=String(metadata.label||record.label||record.skillId).slice(0,240);
      record.mastery=update(record.mastery,!!correct,model);
      record.attempts=(Number(record.attempts)||0)+1;
      record.correct=(Number(record.correct)||0)+(correct?1:0);
      record.lastScore=clamp(metadata.score==null?0:metadata.score,0,100);
      record.lastObservedAt=new Date().toISOString();
      record.mastered=record.mastery>=model.masteryThreshold;
      state.skills[key(skillId)]=record;write(state);return record;
    }
    function summary(){
      var state=read(),prefix=scope+'::',records=[];
      Object.keys(state.skills).forEach(function(item){if(item.indexOf(prefix)===0)records.push(state.skills[item]);});
      var average=records.length?records.reduce(function(total,item){return total+(Number(item.mastery)||0);},0)/records.length:model.initial;
      return {mastery:average,skills:records.length,mastered:records.filter(function(item){return item.mastered;}).length,records:records};
    }
    return {get:get,observe:observe,summary:summary,params:model,storageKey:STORAGE_KEY};
  }

  var api={defaults:DEFAULTS,update:update,createTracker:createTracker};
  root.MindCraftedBKT=api;
  if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
