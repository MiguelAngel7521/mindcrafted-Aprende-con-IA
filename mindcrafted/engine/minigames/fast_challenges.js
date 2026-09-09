// Cuatro retos reutilizables del modo rápido. Todo el contenido visible está en español.
(function(){
  function esc(value){
    return String(value == null ? '' : value).replace(/[&<>"']/g,function(ch){
      return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch];
    });
  }
  function shell(title,instruction,body){
    return '<div style="width:100%;max-width:680px;margin:auto;padding:18px;color:'+(GAME.theme.text||'#e0f0ff')+'">'+
      '<div class="mg-title" style="text-align:center;margin-bottom:8px">'+esc(title)+'</div>'+
      '<div class="mg-instruction">'+esc(instruction)+'</div>'+body+'</div>';
  }
  function shuffle(items){
    var out=items.slice();
    for(var i=out.length-1;i>0;i--){var j=Math.floor(Math.random()*(i+1)),tmp=out[i];out[i]=out[j];out[j]=tmp;}
    return out;
  }
  function actionStyle(){return 'pointer-events:auto;width:100%;text-align:left;padding:11px 14px;margin:5px 0';}

  registerMinigame('orbital_quiz',function(ct,data){
    var questions=Array.isArray(data.questions)?data.questions:[],index=0,correct=0,answered=false;
    function render(){
      if(!questions.length){closeMiniGame(0);return;}
      var q=questions[index],opts=Array.isArray(q.options)?q.options:[];
      var body='<div style="padding:16px;border:1px solid '+GAME.theme.border+';border-radius:14px;background:rgba(255,255,255,.035)">'+
        '<div style="font-size:11px;color:'+GAME.theme.muted+';margin-bottom:8px">PREGUNTA '+(index+1)+' / '+questions.length+'</div>'+
        '<div style="font-size:15px;line-height:1.55;margin-bottom:12px">'+esc(q.question)+'</div><div>';
      opts.forEach(function(opt,i){body+='<button class="mg-btn quiz-opt" data-index="'+i+'" style="'+actionStyle()+'">'+esc(opt)+'</button>';});
      body+='</div><div id="quiz-feedback" style="min-height:42px;margin-top:8px;font-size:12px;line-height:1.5"></div></div>';
      ct.innerHTML=shell(data.title||'Reto orbital',data.instruction||'Elige la respuesta correcta.',body);
      ct.querySelectorAll('.quiz-opt').forEach(function(btn){btn.onclick=function(){
        if(answered)return;answered=true;
        var picked=Number(btn.dataset.index),ok=picked===Number(q.answer||0);if(ok)correct++;
        btn.style.borderColor=ok?GAME.theme.success:'#ff6060';Audio.playSFX(ok?'correct':'wrong');
        var fb=ct.querySelector('#quiz-feedback');fb.style.color=ok?GAME.theme.success:'#ff8a8a';fb.textContent=(ok?'✓ Correcto. ':'✗ Revisa la idea. ')+(q.explanation||'');
        var next=document.createElement('button');next.className='mg-btn';next.style.pointerEvents='auto';next.textContent=index<questions.length-1?'Siguiente →':'Ver resultado →';
        next.onclick=function(){index++;answered=false;if(index<questions.length)render();else closeMiniGame(Math.round(correct/questions.length*100));};
        fb.appendChild(document.createElement('br'));fb.appendChild(next);
      };});
    }
    render();
  });

  registerMinigame('sequence_puzzle',function(ct,data){
    var steps=Array.isArray(data.steps)?data.steps.slice(0,6):[],pool=shuffle(steps.map(function(text,index){return {text:text,index:index};})),chosen=[],attempts=0;
    function render(){
      var slots=chosen.map(function(item,i){return '<button class="mg-btn seq-chosen" data-pos="'+i+'" style="pointer-events:auto;padding:10px 12px">'+(i+1)+'. '+esc(item.text)+'</button>';}).join('');
      var available=pool.filter(function(item){return chosen.indexOf(item)<0;}).map(function(item){return '<button class="mg-btn seq-item" data-index="'+item.index+'" style="'+actionStyle()+'">'+esc(item.text)+'</button>';}).join('');
      var body='<div style="display:grid;grid-template-columns:1fr 1fr;gap:14px"><div><div style="color:'+GAME.theme.muted+';font-size:11px;margin-bottom:6px">PIEZAS</div>'+available+'</div>'+
        '<div><div style="color:'+GAME.theme.muted+';font-size:11px;margin-bottom:6px">TU SECUENCIA</div><div style="min-height:150px;border:1px dashed '+GAME.theme.border+';border-radius:12px;padding:8px">'+slots+'</div></div></div>'+
        '<div id="seq-feedback" style="min-height:28px;text-align:center;margin-top:8px"></div><div style="text-align:center"><button id="seq-check" class="mg-btn" style="pointer-events:auto" '+(chosen.length!==steps.length?'disabled':'')+'>Comprobar puzle</button></div>';
      ct.innerHTML=shell(data.title||'Puzle de secuencia',data.instruction||'Ordena las piezas correctamente.',body);
      ct.querySelectorAll('.seq-item').forEach(function(btn){btn.onclick=function(){var idx=Number(btn.dataset.index),item=pool.find(function(x){return x.index===idx;});if(item){chosen.push(item);Audio.playSFX('select');render();}};});
      ct.querySelectorAll('.seq-chosen').forEach(function(btn){btn.onclick=function(){chosen.splice(Number(btn.dataset.pos),1);render();};});
      var check=ct.querySelector('#seq-check');if(check)check.onclick=function(){attempts++;var ok=chosen.every(function(item,i){return item.index===i;});
        if(ok){Audio.playSFX('complete');spawnParticles(384,250,'confetti',30);closeMiniGame(attempts===1?100:75);}
        else{Audio.playSFX('wrong');chosen=[];var fb=ct.querySelector('#seq-feedback');fb.style.color='#ff8a8a';fb.textContent='El orden aún no es correcto. Inténtalo otra vez.';setTimeout(render,900);}
      };
    }
    render();
  });

  registerMinigame('memory_match',function(ct,data){
    var pairs=Array.isArray(data.pairs)?data.pairs.slice(0,5):[],cards=[];
    pairs.forEach(function(pair,id){cards.push({id:id,text:pair.term});cards.push({id:id,text:pair.definition});});cards=shuffle(cards);
    var open=[],matched={},mistakes=0,locked=false;
    function render(){
      if(!pairs.length){closeMiniGame(0);return;}
      var body='<div style="display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:9px">';
      cards.forEach(function(card,i){var visible=open.indexOf(i)>=0||matched[card.id];body+='<button class="mg-btn memory-card" data-index="'+i+'" style="pointer-events:auto;min-height:62px;padding:10px;border-color:'+(matched[card.id]?GAME.theme.success:GAME.theme.border)+'">'+(visible?esc(card.text):'✦ SEÑAL OCULTA ✦')+'</button>';});
      body+='</div><div style="text-align:center;color:'+GAME.theme.muted+';font-size:11px;margin-top:10px">Parejas: '+Object.keys(matched).length+' / '+pairs.length+'</div>';
      ct.innerHTML=shell(data.title||'Memoria de señales',data.instruction||'Encuentra cada concepto y su explicación.',body);
      ct.querySelectorAll('.memory-card').forEach(function(btn){btn.onclick=function(){
        var idx=Number(btn.dataset.index),card=cards[idx];if(locked||matched[card.id]||open.indexOf(idx)>=0)return;open.push(idx);Audio.playSFX('select');render();
        if(open.length===2){locked=true;var a=cards[open[0]],b=cards[open[1]];setTimeout(function(){if(a.id===b.id){matched[a.id]=true;Audio.playSFX('correct');spawnParticles(384,250,'sparkle',10);}else{mistakes++;Audio.playSFX('wrong');}open=[];locked=false;if(Object.keys(matched).length===pairs.length)closeMiniGame(Math.max(55,100-mistakes*10));else render();},650);}
      };});
    }
    render();
  });

  registerMinigame('signal_sort',function(ct,data){
    var categories=Array.isArray(data.categories)?data.categories.slice(0,3):[],items=[];
    categories.forEach(function(cat,catIndex){(cat.items||[]).slice(0,4).forEach(function(item){items.push({text:item,category:catIndex});});});items=shuffle(items);
    var index=0,correct=0;
    function render(){
      if(index>=items.length){closeMiniGame(items.length?Math.round(correct/items.length*100):0);return;}
      var item=items[index],body='<div style="text-align:center;padding:18px;border:1px solid '+GAME.theme.border+';border-radius:14px;background:rgba(255,255,255,.035)"><div style="font-size:18px;color:'+GAME.theme.highlight+';margin-bottom:16px">'+esc(item.text)+'</div>';
      categories.forEach(function(cat,i){body+='<button class="mg-btn sort-choice" data-index="'+i+'" style="pointer-events:auto;padding:12px 18px">'+esc(cat.name)+'</button>';});body+='<div id="sort-feedback" style="min-height:30px;margin-top:10px"></div></div>';
      ct.innerHTML=shell(data.title||'Clasificador de señales',data.instruction||'Envía cada señal a la categoría correcta.',body);
      ct.querySelectorAll('.sort-choice').forEach(function(btn){btn.onclick=function(){var ok=Number(btn.dataset.index)===item.category;if(ok)correct++;Audio.playSFX(ok?'correct':'wrong');var fb=ct.querySelector('#sort-feedback');fb.style.color=ok?GAME.theme.success:'#ff8a8a';fb.textContent=ok?'✓ Clasificación correcta.':'✗ Correspondía a '+categories[item.category].name+'.';ct.querySelectorAll('.sort-choice').forEach(function(b){b.disabled=true;});setTimeout(function(){index++;render();},700);};});
    }
    render();
  });
})();
