"""Plantilla visual fija para el modo rapido de MindCrafted.

La escena se dibuja localmente con Canvas. No requiere llamadas a IA, descargas ni
archivos externos: todos los juegos rapidos comparten la misma nave orbitando un
planeta de agua.
"""

FAST_THEME = "ocean-dream"
MENTOR_NAME = "AURA"
COMPANION_NAME = "Bit"


PIXEL_ART_JS = r"""
(function(){
  function rr(g,x,y,w,h,r,c){
    g.fillStyle=c;g.beginPath();g.roundRect(x,y,w,h,r);g.fill();
  }
  function waterPlanet(g,cx,cy,r){
    g.save();
    g.shadowColor='#55dfff';g.shadowBlur=10;
    g.fillStyle='#1b8fd1';g.beginPath();g.arc(cx,cy,r,0,Math.PI*2);g.fill();
    g.shadowBlur=0;g.clip();
    g.fillStyle='#31c8e8';g.fillRect(cx-r,cy-r*.32,r*2,r*.18);
    g.fillStyle='#8bf3ff';g.fillRect(cx-r*.86,cy-r*.1,r*1.32,r*.10);
    g.fillStyle='#1470b6';g.fillRect(cx-r,cy+r*.18,r*1.2,r*.2);
    g.fillStyle='#5fe2f2';g.fillRect(cx-r*.2,cy+r*.43,r*1.12,r*.12);
    g.fillStyle='rgba(255,255,255,.38)';g.beginPath();g.arc(cx-r*.28,cy-r*.32,r*.18,0,Math.PI*2);g.fill();
    g.restore();
    g.strokeStyle='#b9fbff';g.lineWidth=1;g.beginPath();g.arc(cx,cy,r+2,3.55,5.65);g.stroke();
  }
  function star(g,x,y,c){g.fillStyle=c;g.fillRect(x,y,1,1);}
  function drawSpace(g,w,h,cover){
    var grad=g.createLinearGradient(0,0,0,h);grad.addColorStop(0,'#020817');grad.addColorStop(1,'#071b39');g.fillStyle=grad;g.fillRect(0,0,w,h);
    [[7,9],[19,21],[31,6],[46,17],[59,10],[71,27],[84,7],[97,19],[111,5],[121,30],[14,39],[39,32],[57,43],[90,37],[118,48]].forEach(function(p,i){star(g,p[0]*w/128,p[1]*h/96,i%3?'#87bfe8':'#ffffff');});
    g.fillStyle='rgba(61,112,180,.14)';g.beginPath();g.ellipse(w*.42,h*.35,w*.46,h*.13,-.18,0,Math.PI*2);g.fill();
    waterPlanet(g,w*.83,h*.54,Math.min(w,h)*(cover ? .33 : .31));
  }
  function drawCockpit(g,w,h){
    g.fillStyle='#07101d';
    g.beginPath();g.moveTo(0,0);g.lineTo(w*.13,0);g.lineTo(w*.25,h*.17);g.lineTo(w*.20,h*.66);g.lineTo(0,h*.78);g.closePath();g.fill();
    g.beginPath();g.moveTo(w,0);g.lineTo(w*.87,0);g.lineTo(w*.75,h*.17);g.lineTo(w*.80,h*.66);g.lineTo(w,h*.78);g.closePath();g.fill();
    g.fillRect(w*.13,0,w*.74,h*.035);
    g.strokeStyle='#28506d';g.lineWidth=2;g.beginPath();g.moveTo(w*.13,0);g.lineTo(w*.25,h*.17);g.lineTo(w*.75,h*.17);g.lineTo(w*.87,0);g.stroke();
    g.fillStyle='#0a2232';g.beginPath();g.moveTo(0,h*.78);g.lineTo(w*.2,h*.66);g.lineTo(w*.8,h*.66);g.lineTo(w,h*.78);g.lineTo(w,h);g.lineTo(0,h);g.closePath();g.fill();
    g.fillStyle='#123d50';g.fillRect(w*.24,h*.72,w*.52,h*.18);
    g.fillStyle='#06141f';g.fillRect(w*.28,h*.75,w*.44,h*.11);
    ['#44e5ff','#5cffb0','#ffcb66','#7f91ff'].forEach(function(c,i){g.fillStyle=c;g.fillRect(w*(.32+i*.1),h*.78,w*.055,h*.025);});
    g.strokeStyle='#3d7185';g.lineWidth=1;g.strokeRect(w*.28,h*.75,w*.44,h*.11);
  }

  window.BACKGROUNDS=[function(){drawSpace(ctx,128,96,false);drawCockpit(ctx,128,96);}];
  window.ICONS={
    star:function(g){g.fillStyle='#8bf3ff';g.fillRect(7,2,2,12);g.fillRect(2,7,12,2);g.fillStyle='#fff';g.fillRect(6,6,4,4);},
    planet:function(g){waterPlanet(g,8,8,6);}
  };
  window.CHAR_DRAW_FNS={
    mentor:function(g){
      g.fillStyle='#d7f8ff';g.fillRect(6,2,12,10);g.fillStyle='#17354c';g.fillRect(8,5,8,4);g.fillStyle='#54e7ff';g.fillRect(9,6,2,2);g.fillRect(13,6,2,2);
      g.fillStyle='#a9d7e5';g.fillRect(5,13,14,14);g.fillStyle='#23637d';g.fillRect(8,16,8,8);g.fillStyle='#69f0c1';g.fillRect(11,18,2,2);g.fillStyle='#7fb7cc';g.fillRect(2,15,3,10);g.fillRect(19,15,3,10);g.fillRect(7,27,4,8);g.fillRect(13,27,4,8);
    },
    player:function(g){
      g.fillStyle='#182d43';g.fillRect(5,1,14,12);g.fillStyle='#8bdff1';g.fillRect(7,3,10,7);g.fillStyle='#f0bf94';g.fillRect(8,7,8,6);g.fillStyle='#143a60';g.fillRect(4,14,16,14);g.fillStyle='#46d7ec';g.fillRect(8,17,8,3);g.fillStyle='#f3ca65';g.fillRect(11,18,2,2);g.fillStyle='#244f72';g.fillRect(1,16,3,10);g.fillRect(20,16,3,10);g.fillRect(6,28,5,7);g.fillRect(13,28,5,7);
    },
    pet:function(g){
      g.fillStyle='#ffd36a';g.fillRect(5,11,14,11);g.fillRect(8,7,8,5);g.fillStyle='#fff1b5';g.fillRect(8,13,8,6);g.fillStyle='#172941';g.fillRect(8,12,2,2);g.fillRect(14,12,2,2);g.fillStyle='#ff9e52';g.fillRect(11,16,2,2);g.fillStyle='#d18d42';g.fillRect(4,22,4,6);g.fillRect(16,22,4,6);
    }
  };
  window.PORTRAITS={
    mentor:function(g,w,h){g.fillStyle='#d7f8ff';g.fillRect(5,4,22,20);g.fillStyle='#17354c';g.fillRect(8,9,16,9);g.fillStyle='#54e7ff';g.fillRect(10,12,3,3);g.fillRect(19,12,3,3);g.fillStyle='#69f0c1';g.fillRect(14,20,4,3);},
    player:function(g,w,h){g.fillStyle='#182d43';g.fillRect(4,2,24,26);g.fillStyle='#8bdff1';g.fillRect(7,5,18,15);g.fillStyle='#f0bf94';g.fillRect(9,12,14,13);g.fillStyle='#17354c';g.fillRect(11,16,3,3);g.fillRect(19,16,3,3);},
    pet:function(g,w,h){g.fillStyle='#ffd36a';g.fillRect(5,8,22,18);g.fillStyle='#fff1b5';g.fillRect(9,13,14,10);g.fillStyle='#172941';g.fillRect(10,14,3,3);g.fillRect(19,14,3,3);}
  };
  window.drawTitleLogo=function(g,w,h){drawSpace(g,w,h,true);};
})();
"""


COVER_JS = r"""
function drawCover(g,w,h){
  var q=g.createLinearGradient(0,0,0,h);q.addColorStop(0,'#020817');q.addColorStop(1,'#071b39');g.fillStyle=q;g.fillRect(0,0,w,h);
  [[8,9],[18,23],[31,6],[43,18],[58,10],[71,29],[86,8],[99,20],[113,6],[122,35],[37,39],[61,43]].forEach(function(p,i){g.fillStyle=i%3?'#7caad2':'#fff';g.fillRect(p[0],p[1],1,1);});
  g.save();g.shadowColor='#55dfff';g.shadowBlur=10;g.fillStyle='#198eca';g.beginPath();g.arc(101,50,31,0,Math.PI*2);g.fill();g.shadowBlur=0;g.clip();
  g.fillStyle='#3bd1e5';g.fillRect(72,37,53,6);g.fillStyle='#8bf3ff';g.fillRect(80,48,44,4);g.fillStyle='#136cab';g.fillRect(70,60,38,8);g.fillStyle='#5fe2f2';g.fillRect(94,71,31,5);g.fillStyle='rgba(255,255,255,.35)';g.beginPath();g.arc(92,37,7,0,Math.PI*2);g.fill();g.restore();
  g.strokeStyle='#b9fbff';g.lineWidth=1;g.beginPath();g.arc(101,50,33,3.5,5.7);g.stroke();
  g.fillStyle='#07101d';g.beginPath();g.moveTo(0,0);g.lineTo(17,0);g.lineTo(29,17);g.lineTo(26,64);g.lineTo(0,78);g.closePath();g.fill();
  g.beginPath();g.moveTo(w,0);g.lineTo(108,0);g.lineTo(88,17);g.lineTo(102,66);g.lineTo(w,78);g.closePath();g.fill();g.fillRect(17,0,91,4);
  g.strokeStyle='#28506d';g.lineWidth=2;g.beginPath();g.moveTo(17,0);g.lineTo(29,17);g.lineTo(88,17);g.lineTo(108,0);g.stroke();
  g.fillStyle='#0a2232';g.beginPath();g.moveTo(0,78);g.lineTo(26,66);g.lineTo(102,66);g.lineTo(128,78);g.lineTo(128,96);g.lineTo(0,96);g.closePath();g.fill();
  g.fillStyle='#123d50';g.fillRect(35,73,58,16);g.fillStyle='#06141f';g.fillRect(39,76,50,9);g.fillStyle='#44e5ff';g.fillRect(44,79,10,2);g.fillStyle='#5cffb0';g.fillRect(59,79,10,2);g.fillStyle='#ffcb66';g.fillRect(74,79,10,2);
}
"""
