"""Plantilla espacial ligera para la generación rápida.

Todo el arte se dibuja con Canvas para que los juegos carguen sin imágenes
externas. La historia avanza por dos escenarios: órbita y vuelo sobre el océano.
"""

FAST_THEME = "ocean-dream"
MENTOR_NAME = "AURA"
COMPANION_NAME = "Bit"


PIXEL_ART_JS = r"""
(function(){
  function rect(g,x,y,w,h,c){g.fillStyle=c;g.fillRect(x,y,w,h);}
  function star(g,x,y,c,s){rect(g,x,y,s||1,s||1,c);}
  function drawStars(g,w,h){
    [[6,8],[14,22],[25,5],[34,17],[44,9],[55,28],[65,6],[76,20],[87,4],[96,31],[108,12],[118,24],[124,6],[38,37],[71,40],[102,43]].forEach(function(p,i){star(g,p[0]*w/128,p[1]*h/96,i%4?'#84bde8':'#fff',i%7===0?2:1);});
  }
  function waterPlanet(g,cx,cy,r){
    g.save();g.shadowColor='#48dcff';g.shadowBlur=9;g.fillStyle='#167fc4';g.beginPath();g.arc(cx,cy,r,0,Math.PI*2);g.fill();g.shadowBlur=0;g.clip();
    rect(g,cx-r,cy-r*.55,r*2,r*.18,'#2cbce1');rect(g,cx-r*.9,cy-r*.23,r*1.65,r*.11,'#8aefff');rect(g,cx-r,cy+r*.04,r*1.45,r*.2,'#126aae');rect(g,cx-r*.4,cy+r*.37,r*1.4,r*.14,'#55d9ec');
    g.fillStyle='rgba(255,255,255,.34)';g.beginPath();g.arc(cx-r*.3,cy-r*.38,r*.17,0,Math.PI*2);g.fill();g.restore();
    g.strokeStyle='#b9f7ff';g.lineWidth=1;g.beginPath();g.arc(cx,cy,r+2,3.55,5.7);g.stroke();
  }
  function drawShip(g,x,y,scale,thrust){
    g.save();g.translate(x,y);g.scale(scale,scale);
    if(thrust){rect(g,-14,2,7,2,'#ff9f43');rect(g,-19,3,10,2,'#ffe66d');rect(g,-23,4,11,1,'#8cf4ff');}
    g.fillStyle='#d9edf5';g.beginPath();g.moveTo(-10,-4);g.lineTo(9,-5);g.lineTo(16,1);g.lineTo(10,7);g.lineTo(-11,7);g.lineTo(-17,2);g.closePath();g.fill();
    rect(g,-9,0,22,5,'#6f9fb8');rect(g,-5,-4,11,4,'#153b60');rect(g,-3,-3,7,2,'#5ee4ff');
    g.fillStyle='#3e6c8a';g.beginPath();g.moveTo(-8,6);g.lineTo(-14,12);g.lineTo(-2,7);g.fill();g.beginPath();g.moveTo(8,6);g.lineTo(13,11);g.lineTo(12,4);g.fill();
    rect(g,12,0,4,2,'#f7d56b');g.restore();
  }
  function drawOrbit(g,w,h){
    var q=g.createLinearGradient(0,0,0,h);q.addColorStop(0,'#010510');q.addColorStop(1,'#082348');g.fillStyle=q;g.fillRect(0,0,w,h);drawStars(g,w,h);
    g.fillStyle='rgba(46,103,176,.13)';g.beginPath();g.ellipse(w*.58,h*.48,w*.62,h*.16,-.17,0,Math.PI*2);g.fill();
    waterPlanet(g,w*.84,h*.63,Math.min(w,h)*.34);
    g.strokeStyle='rgba(130,225,255,.34)';g.setLineDash([2,3]);g.beginPath();g.ellipse(w*.70,h*.55,w*.37,h*.20,-.24,0,Math.PI*2);g.stroke();g.setLineDash([]);
    drawShip(g,w*.34,h*.35,1.12,true);
    rect(g,0,h*.83,w,h*.17,'rgba(3,14,29,.72)');rect(g,0,h*.83,w,2,'#1a6684');
  }
  function drawOceanFlight(g,w,h){
    var sky=g.createLinearGradient(0,0,0,h*.58);sky.addColorStop(0,'#174f93');sky.addColorStop(1,'#79dff0');g.fillStyle=sky;g.fillRect(0,0,w,h*.58);
    rect(g,8,13,16,3,'rgba(224,250,255,.72)');rect(g,12,10,8,3,'rgba(224,250,255,.72)');rect(g,88,19,25,3,'rgba(224,250,255,.62)');rect(g,95,16,11,3,'rgba(224,250,255,.62)');
    rect(g,0,h*.55,w,h*.45,'#087db4');rect(g,0,h*.63,w,h*.37,'#056399');rect(g,0,h*.76,w,h*.24,'#074b7e');
    [[5,60,26],[39,69,31],[77,59,20],[98,80,27],[11,87,35],[58,91,26]].forEach(function(v,i){rect(g,v[0],v[1],v[2],i%2?2:1,i%2?'#5be0ea':'#a0f5f5');});
    g.fillStyle='rgba(220,255,255,.25)';g.beginPath();g.ellipse(w*.46,h*.64,w*.31,3,0,0,Math.PI*2);g.fill();
    drawShip(g,w*.56,h*.39,1.35,true);
    rect(g,w*.28,h*.64,w*.42,2,'rgba(193,252,255,.58)');rect(g,w*.36,h*.68,w*.28,1,'rgba(193,252,255,.42)');
    rect(g,0,h*.86,w,h*.14,'rgba(2,34,65,.56)');rect(g,0,h*.86,w,2,'#2fc4dc');
  }

  window.BACKGROUNDS=[function(){drawOrbit(ctx,128,96);},function(){drawOceanFlight(ctx,128,96);}];
  window.ICONS={
    star:function(g){rect(g,7,2,2,12,'#8bf3ff');rect(g,2,7,12,2,'#8bf3ff');rect(g,6,6,4,4,'#fff');},
    planet:function(g){waterPlanet(g,8,8,6);}
  };
  window.CHAR_DRAW_FNS={
    mentor:function(g){rect(g,6,2,12,10,'#d7f8ff');rect(g,8,5,8,4,'#17354c');rect(g,9,6,2,2,'#54e7ff');rect(g,13,6,2,2,'#54e7ff');rect(g,5,13,14,14,'#a9d7e5');rect(g,8,16,8,8,'#23637d');rect(g,11,18,2,2,'#69f0c1');rect(g,2,15,3,10,'#7fb7cc');rect(g,19,15,3,10,'#7fb7cc');rect(g,7,27,4,8,'#7fb7cc');rect(g,13,27,4,8,'#7fb7cc');},
    player:function(g){rect(g,5,1,14,12,'#182d43');rect(g,7,3,10,7,'#8bdff1');rect(g,8,7,8,6,'#f0bf94');rect(g,4,14,16,14,'#143a60');rect(g,8,17,8,3,'#46d7ec');rect(g,11,18,2,2,'#f3ca65');rect(g,1,16,3,10,'#244f72');rect(g,20,16,3,10,'#244f72');rect(g,6,28,5,7,'#244f72');rect(g,13,28,5,7,'#244f72');},
    pet:function(g){rect(g,5,11,14,11,'#ffd36a');rect(g,8,7,8,5,'#ffd36a');rect(g,8,13,8,6,'#fff1b5');rect(g,8,12,2,2,'#172941');rect(g,14,12,2,2,'#172941');rect(g,11,16,2,2,'#ff9e52');rect(g,4,22,4,6,'#d18d42');rect(g,16,22,4,6,'#d18d42');}
  };
  window.PORTRAITS={
    mentor:function(g){rect(g,5,4,22,20,'#d7f8ff');rect(g,8,9,16,9,'#17354c');rect(g,10,12,3,3,'#54e7ff');rect(g,19,12,3,3,'#54e7ff');rect(g,14,20,4,3,'#69f0c1');},
    player:function(g){rect(g,4,2,24,26,'#182d43');rect(g,7,5,18,15,'#8bdff1');rect(g,9,12,14,13,'#f0bf94');rect(g,11,16,3,3,'#17354c');rect(g,19,16,3,3,'#17354c');},
    pet:function(g){rect(g,5,8,22,18,'#ffd36a');rect(g,9,13,14,10,'#fff1b5');rect(g,10,14,3,3,'#172941');rect(g,19,14,3,3,'#172941');}
  };
  window.drawTitleLogo=function(g,w,h){drawOrbit(g,w,h);};
})();
"""


COVER_JS = r"""
function drawCover(g,w,h){
  var q=g.createLinearGradient(0,0,0,h);q.addColorStop(0,'#010510');q.addColorStop(1,'#082348');g.fillStyle=q;g.fillRect(0,0,w,h);
  [[7,8],[18,22],[31,5],[44,17],[57,9],[71,28],[85,6],[98,19],[112,8],[122,29],[38,38],[70,43]].forEach(function(p,i){g.fillStyle=i%3?'#84bde8':'#fff';g.fillRect(p[0],p[1],i%7===0?2:1,i%7===0?2:1);});
  g.save();g.shadowColor='#48dcff';g.shadowBlur=9;g.fillStyle='#167fc4';g.beginPath();g.arc(101,58,32,0,Math.PI*2);g.fill();g.shadowBlur=0;g.clip();g.fillStyle='#2cbce1';g.fillRect(71,42,62,6);g.fillStyle='#8aefff';g.fillRect(78,53,48,4);g.fillStyle='#126aae';g.fillRect(69,64,49,8);g.fillStyle='#55d9ec';g.fillRect(91,76,39,5);g.restore();
  g.strokeStyle='#b9f7ff';g.beginPath();g.arc(101,58,34,3.55,5.7);g.stroke();
  g.save();g.translate(40,34);g.scale(1.15,1.15);g.fillStyle='#ffe66d';g.fillRect(-20,3,10,2);g.fillStyle='#8cf4ff';g.fillRect(-24,4,12,1);g.fillStyle='#d9edf5';g.beginPath();g.moveTo(-10,-4);g.lineTo(9,-5);g.lineTo(16,1);g.lineTo(10,7);g.lineTo(-11,7);g.lineTo(-17,2);g.closePath();g.fill();g.fillStyle='#6f9fb8';g.fillRect(-9,0,22,5);g.fillStyle='#153b60';g.fillRect(-5,-4,11,4);g.fillStyle='#5ee4ff';g.fillRect(-3,-3,7,2);g.restore();
}
"""
