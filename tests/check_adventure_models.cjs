const assert=require('node:assert/strict');
const C=require('../mindcrafted/engine/adventure/core.js');
const E=require('../mindcrafted/engine/adventure/encounters.js');
const bounds={left:0,right:800,top:0,bottom:600};
const a={x:50,y:50},b={...a};
for(let i=0;i<60;i++)C.move(a,1,0,1/60,[],bounds);
for(let i=0;i<120;i++)C.move(b,1,0,1/120,[],bounds);
assert.ok(Math.abs(a.x-b.x)<1e-6,'Frame rate changed movement speed');
const wall=[{x:100,y:0,width:10,height:600}],p={x:50,y:50};
for(let i=0;i<100;i++)C.move(p,1,0,.05,wall,bounds);
assert.ok(p.x<=93,'Player crossed a wall');
const diagonal={x:0,y:0};C.move(diagonal,1,1,.05,[],bounds);assert.ok(Math.hypot(diagonal.x,diagonal.y)<=155*.05+.00001);
const cases=[
 ['evidence_choice',{options:['a','b','c'],answer:1},[1]],
 ['process_order',{steps:['a','b','c']},[0,1,2]],
 ['concept_links',{pairs:[{left:'a',right:'x'},{left:'b',right:'y'},{left:'c',right:'z'}]},[0,1,2]],
 ['packet_route',{nodes:['a','b','c'],edges:[[0,1],[1,2]],start:0,target:2},[1,2]],
 ['algorithm_trace',{initial:2,operations:[{op:'add',value:3},{op:'multiply',value:2},{op:'subtract',value:1}],states:[5,10,9]},[5,10,9]],
 ['fraction_fill',{numerator:3,denominator:4},['add','add','add','submit']],
 ['circuit_target',{resistance:6,target_voltage:12,target_current:2},['boost','boost','submit']],
 ['balance_equation',{a:2,b:4,c:14,solution:5},['cancel','divide','submit']],
];
for(const [kind,data,actions] of cases){const e=E.create({kind,data});let last;for(const action of actions){assert.ok(e.view().choices.some(c=>c.id===action));last=e.act(action);}assert.equal(last.done,true,kind);}
assert.equal(E.create({kind:'packet_route',data:cases[3][1]}).act(2).correct,false);
assert.equal(E.create({kind:'evidence_choice',data:cases[0][1]}).act(0).done,false);
assert.equal(E.create({kind:'circuit_target',data:cases[6][1]}).act('boost').assessed,false,'Adjusting voltage is not an answer');
const equation=E.create({kind:'balance_equation',data:{a:2,b:-4,c:6,solution:5}});
equation.act('divide');equation.act('cancel');assert.equal(equation.act('submit').done,true,'Alternate algebra solution rejected');
console.log('OK: eight solvable mechanics, invalid answers, collision, normalized speed and independent controls.');
