/* Geometría y tiempo de simulación compartidos por juego y pruebas. */
(function(root){
'use strict';
function random(seed){let x=seed|0;return ()=>{x^=x<<13;x^=x>>>17;x^=x<<5;return (x>>>0)/4294967296;};}
function distance(a,b){return Math.hypot(a.x-b.x,a.y-b.y);}
function walkable(p,boxes,bounds){
  return p.x>=bounds.left&&p.x<=bounds.right&&p.y>=bounds.top&&p.y<=bounds.bottom&&!boxes.some(b=>p.x+7>b.x&&p.x-7<b.x+b.width&&p.y+3>b.y&&p.y-7<b.y+b.height);
}
function move(player,dx,dy,seconds,boxes,bounds,speed=155){
  const dt=Math.min(.05,Math.max(0,seconds)),length=Math.hypot(dx,dy);if(!length)return false;
  dx/=length;dy/=length;const count=Math.max(1,Math.ceil(speed*dt/4));let changed=false;
  for(let i=0;i<count;i++){
    const x={x:player.x+dx*speed*dt/count,y:player.y};if(walkable(x,boxes,bounds)){player.x=x.x;changed=true;}
    const y={x:player.x,y:player.y+dy*speed*dt/count};if(walkable(y,boxes,bounds)){player.y=y.y;changed=true;}
  }
  if(changed)player.direction=Math.abs(dx)>Math.abs(dy)?dx<0?1:2:dy<0?3:0;
  return changed;
}
function storageKey(config){return 'mindcrafted_adventure_v1:'+(config.courseId||config.sourceHash)+':'+config.chunkId+':'+config.adventureHash;}
function restore(raw,config){
  const result={done:{},position:{...config.adventure.layout.spawn},bossWon:false,bossPhase:0};
  if(!raw||typeof raw!=='object')return result;
  for(const p of config.practice.puzzles){const r=raw.done?.[p.id];if(r&&r.complete===true)result.done[p.id]={complete:true,score:Math.min(100,Math.max(0,Number(r.score)||0))};}
  if(Number.isFinite(raw.position?.x)&&Number.isFinite(raw.position?.y))result.position={x:raw.position.x,y:raw.position.y};
  result.bossWon=raw.bossWon===true;result.bossPhase=0;return result;
}
const api={random,distance,walkable,move,storageKey,restore};
root.AdventureCore=api;if(typeof module!=='undefined')module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
