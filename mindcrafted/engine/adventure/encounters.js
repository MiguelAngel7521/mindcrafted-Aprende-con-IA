/* Reglas educativas sin canvas, DOM ni efectos de combate. */
(function(root){
'use strict';
function create(puzzle){
  const d=puzzle.data,k=puzzle.kind;let step=0,charge=0,node=d.start,a=d.a,b=d.b,c=d.c,voltage=0,closed=true;
  const labels={add:'Sumar',subtract:'Restar',multiply:'Multiplicar por'};
  function view(){
    let prompt='',choices=[];
    if(k==='evidence_choice'){prompt='Elige una respuesta y confírmala.';choices=d.options.map((label,id)=>({id,label}));}
    if(k==='process_order'){prompt='Etapa '+(step+1)+' de '+d.steps.length+': recoge el siguiente paso.';choices=d.steps.map((label,id)=>({id,label}));}
    if(k==='concept_links'){prompt='Conecta: '+d.pairs[step].left;choices=d.pairs.map((pair,id)=>({id,label:pair.right}));}
    if(k==='packet_route'){prompt='Señal en '+d.nodes[node]+' → destino '+d.nodes[d.target]+'. Conexiones: '+d.edges.map(e=>d.nodes[e[0]]+' → '+d.nodes[e[1]]).join(' · ');choices=d.nodes.map((label,id)=>({id,label}));}
    if(k==='algorithm_trace'){const op=d.operations[step],previous=step?d.states[step-1]:d.initial,answer=d.states[step];prompt='Variable = '+previous+'. '+labels[op.op]+' '+op.value+'. ¿Nuevo valor?';choices=[answer,answer+1,answer-1,answer+2].map((n,id)=>({id:n,label:String(n)}));}
    if(k==='fraction_fill'){prompt='Carga '+d.numerator+'/'+d.denominator+' del receptor. Cada unidad vale 1/'+d.denominator+'. Tienes '+charge+'.';choices=[{id:'add',label:'Recoger 1 parte'},{id:'remove',label:'Devolver 1 parte'},{id:'submit',label:'Entregar la fracción'}];}
    if(k==='circuit_target'){prompt='Resistencia '+d.resistance+' Ω · Objetivo '+Number(d.target_current.toFixed(3))+' A · Batería '+voltage+' V · Corriente '+Number((closed?voltage/d.resistance:0).toFixed(3))+' A';choices=[{id:'up',label:'+1 V'},{id:'down',label:'−1 V'},{id:'boost',label:'+6 V'},{id:'switch',label:closed?'Abrir circuito':'Cerrar circuito'},{id:'submit',label:'Estabilizar corriente'}];}
    if(k==='balance_equation'){prompt=Number(a.toFixed(3))+'x + ('+Number(b.toFixed(3))+') = '+Number(c.toFixed(3))+'. Aísla x en ambos miembros.';choices=[{id:'cancel',label:Math.abs(b)>1e-7?(b>0?'Restar ':'Sumar ')+Number(Math.abs(b).toFixed(3))+' a ambos lados':'Sumar 1 a ambos lados'},{id:'divide',label:Math.abs(a-1)>1e-7?'Dividir ambos lados entre '+Number(a.toFixed(3)):'Multiplicar ambos lados por 2'},{id:'reset',label:'Restaurar ecuación'},{id:'submit',label:'Verificar igualdad'}];}
    return {prompt,choices,step,charge,denominator:d.denominator};
  }
  function act(id){
    let correct,done=false,assessed=true;
    if(k==='evidence_choice'){correct=id===d.answer;done=correct;}
    if(k==='process_order'){correct=id===step;if(correct)step++;done=step===d.steps.length;}
    if(k==='concept_links'){correct=id===step;if(correct)step++;done=step===d.pairs.length;}
    if(k==='algorithm_trace'){correct=id===d.states[step];if(correct)step++;done=step===d.states.length;}
    if(k==='packet_route'){correct=d.edges.some(e=>e[0]===node&&e[1]===id);if(correct)node=id;done=node===d.target;}
    if(k==='fraction_fill'){if(id==='add')charge=Math.min(d.denominator,charge+1);if(id==='remove')charge=Math.max(0,charge-1);assessed=id==='submit';correct=charge===d.numerator;done=assessed&&correct;}
    if(k==='circuit_target'){if(id==='up')voltage=Math.min(24,voltage+1);if(id==='down')voltage=Math.max(0,voltage-1);if(id==='boost')voltage=Math.min(24,voltage+6);if(id==='switch')closed=!closed;assessed=id==='submit';correct=closed&&voltage===d.target_voltage;done=assessed&&correct;}
    if(k==='balance_equation'){
      if(id==='cancel'){const delta=Math.abs(b)>1e-7?-b:1;b+=delta;c+=delta;}
      if(id==='divide'){const divisor=Math.abs(a-1)>1e-7?a:.5;a/=divisor;b/=divisor;c/=divisor;}
      if(id==='reset'){a=d.a;b=d.b;c=d.c;}
      assessed=id==='submit';correct=Math.abs(a-1)<1e-7&&Math.abs(b)<1e-7&&Math.abs(c-d.solution)<1e-6;done=assessed&&correct;
    }
    return {correct:!!correct,done,assessed,advanced:assessed&&correct&&!done};
  }
  return {view,act};
}
root.AdventureEncounters={create};if(typeof module!=='undefined')module.exports={create};
})(typeof window!=='undefined'?window:globalThis);
