-- MindCrafted: arte original y reproducible mediante la API nativa de Aseprite.
-- Ejecutar desde build.py. No necesita MCP, red ni un servicio de imágenes.
local root = assert(app.params.output, 'Falta --script-param output=...')
local PC = app.pixelColor
local ink, cream = '#111e2b', '#f5edcf'
local img, ox, oy, layerImages, activeName
local catalog = {}
local colors = {}
local function color(hex)
  if not colors[hex] then
    local s=hex:gsub('#','')
    colors[hex]=PC.rgba(tonumber(s:sub(1,2),16),tonumber(s:sub(3,4),16),tonumber(s:sub(5,6),16),255)
  end
  return colors[hex]
end
local function pixel(x,y,c)
  x,y=math.floor(x+ox),math.floor(y+oy)
  if x>=0 and y>=0 and x<img.width and y<img.height then img:drawPixel(x,y,color(c)) end
end
local function rect(x,y,w,h,c)
  for yy=math.floor(y),math.floor(y+h-1) do for xx=math.floor(x),math.floor(x+w-1) do pixel(xx,yy,c) end end
end
local function line(x0,y0,x1,y1,c)
  local n=math.max(math.abs(x1-x0),math.abs(y1-y0),1)
  for i=0,n do pixel(x0+(x1-x0)*i/n,y0+(y1-y0)*i/n,c) end
end
local function ellipse(cx,cy,rx,ry,c)
  for y=-ry,ry do
    local span=math.floor(rx*math.sqrt(math.max(0,1-y*y/(ry*ry))))
    rect(cx-span,cy+y,span*2+1,1,c)
  end
end
local function box(x,y,w,h,fill,light,dark)
  rect(x,y,w,h,dark or ink);rect(x+1,y+1,w-2,h-2,fill)
  line(x+1,y+1,x+w-2,y+1,light or cream);line(x+1,y+1,x+1,y+h-2,light or cream)
end
local function bolts(x,y,w,h)
  for _,p in ipairs({{x+3,y+3},{x+w-5,y+3},{x+3,y+h-5},{x+w-5,y+h-5}}) do
    rect(p[1],p[2],3,3,ink);pixel(p[1],p[2],'#9ab8bf')
  end
end
local function scatter(x,y,w,h,n,palette,seed)
  local s=seed or 17
  for i=1,n do
    s=(s*48271)%2147483647;local px=x+s%w
    s=(s*48271)%2147483647;local py=y+s%h
    pixel(px,py,palette[i%#palette+1])
  end
end
local function layer(name)
  activeName=name
  img=layerImages[name]
end
local function sprite(name,w,h,frames,draw,tags)
  colors={}
  local spr=Sprite(w,h,ColorMode.RGB)
  spr.gridBounds=Rectangle(0,0,32,32)
  spr.layers[1].name='Silueta y volumen'
  local nativeLayers={spr.layers[1],spr:newLayer(),spr:newLayer()}
  nativeLayers[2].name='Detalles y materiales';nativeLayers[3].name='Luz y animación'
  local sheet=Image(w*frames,h,ColorMode.RGB)
  for f=1,frames do
    if f>1 then spr:newEmptyFrame() end
    spr.frames[f].duration=0.16
    layerImages={}
    for _,l in ipairs(nativeLayers) do layerImages[l.name]=Image(w,h,ColorMode.RGB) end
    ox,oy=0,0;layer('Silueta y volumen');draw(f)
    local flat=Image(w,h,ColorMode.RGB)
    for _,l in ipairs(nativeLayers) do
      spr:newCel(l,f,layerImages[l.name],Point(0,0))
      flat:drawImage(layerImages[l.name],Point(0,0))
    end
    sheet:drawImage(flat,Point((f-1)*w,0))
    if f==1 then flat:saveAs(root..'/exports/'..name..'.png') end
  end
  for _,t in ipairs(tags or {{'idle',1,frames}}) do
    local tag=spr:newTag(t[2],t[3]);tag.name=t[1]
  end
  local swatches={};for hex,_ in pairs(colors) do swatches[#swatches+1]=hex end;table.sort(swatches)
  local palette=Palette(#swatches)
  for i,hex in ipairs(swatches) do local s=hex:sub(2);palette:setColor(i-1,Color{r=tonumber(s:sub(1,2),16),g=tonumber(s:sub(3,4),16),b=tonumber(s:sub(5,6),16)}) end
  spr:setPalette(palette)
  palette:saveAs(root..'/palettes/'..name..'.gpl')
  spr:saveAs(root..'/source/'..name..'.aseprite')
  if frames>1 then sheet:saveAs(root..'/exports/'..name..'-sheet.png') end
  catalog[#catalog+1]={id=name,width=w,height=h,frames=frames,frameDuration=160,
    image='art/exports/'..name..'.png',source='art/source/'..name..'.aseprite',
    sheet=frames>1 and ('art/exports/'..name..'-sheet.png') or nil,tags=tags or {{'idle',1,frames}}}
  spr:close()
end

-- Cada atlas tiene ocho variaciones de suelo, cuatro de pared y cuatro piezas especiales.
local palettes={
  laboratory={'#263746','#304553','#3a5360','#486571','#60838b','#7ba3a5','#59d9d0','#c2f1dc'},
  mathematics={'#473c43','#594950','#6b5557','#7e665f','#9c8070','#c5a17b','#e3ba79','#f5dfab'},
  biology={'#1c3e38','#244b3e','#2c5944','#3b6c4b','#4e8056','#77a35d','#a4c676','#dcdb8a'},
}
for _,world in ipairs({'laboratory','mathematics','biology'}) do
  local p=palettes[world]
  sprite('terrain-'..world,256,64,1,function()
    for t=0,15 do
      ox=(t%8)*32;oy=math.floor(t/8)*32
      rect(0,0,32,32,p[2+(t%2)])
      if world=='biology' then
        if t<8 then
          scatter(0,0,32,32,65,{p[2],p[3],p[4]},101+t)
          for n=1,5 do local x=(t*7+n*11)%29+1;local y=(t*13+n*7)%29+1
            line(x,y,x-1,y-2,p[5]);line(x,y,x+2,y-1,p[4]) end
        elseif t<12 then
          rect(0,0,32,32,'#295e72');scatter(0,0,32,32,20,{'#347487','#438999'},80+t)
          for n=1,4 do local x=(n*9+t*3)%24;local y=(n*7+t)%30;line(x,y,x+5,y,'#68a9ae') end
        else
          rect(0,0,32,32,'#8b805b');scatter(0,0,32,32,90,{'#746c51','#a39468','#b5a475'},40+t)
        end
      elseif t<8 then
        box(0,0,32,32,p[2+t%2],p[4],p[1]);line(2,30,30,30,p[1])
        if world=='mathematics' then
          for y=8,24,8 do line(2,y,30,y,p[1]);line(3,y+1,29,y+1,p[4]) end
          scatter(3,3,26,26,13,{p[4],p[2]},33+t)
        else
          for _,a in ipairs({{3,3},{28,3},{3,28},{28,28}}) do pixel(a[1],a[2],p[5]) end
          if t%3==0 then line(8,14,22,14,p[4]);line(8,16,15,16,p[4]) end
        end
      elseif t<12 then
        rect(0,0,32,32,p[1]);box(0,2,32,28,p[3],p[5],ink)
        rect(3,6,26,13,p[2]);line(2,26,30,26,p[6]);line(0,30,31,30,p[7])
        if world=='laboratory' then rect(7,9,18,2,p[5]);rect(7,13,18,2,p[1])
        else line(16,4,16,25,p[1]);rect(5,8,3,10,p[4]) end
      else
        rect(0,0,32,32,p[1]);box(1,1,30,30,p[2],p[5],p[1])
        if t==12 then for x=5,26,4 do line(x,4,x,27,p[1]) end
        elseif t==13 then for x=-20,40,12 do for j=0,4 do line(x+j,0,x+j+32,31,p[7]) end end
        elseif t==14 then box(7,7,18,18,p[3],p[5],p[1]);ellipse(16,16,4,4,p[7])
        else rect(3,12,26,8,p[7]);line(3,13,28,13,p[8]) end
      end
    end
    ox,oy=0,0
  end)
end

sprite('lab-reactor',80,112,6,function(f)
  ellipse(40,102,33,7,'#142630');box(13,87,54,15,'#3b6271','#93b5b6');bolts(13,87,54,15)
  box(19,19,42,72,'#1e4254','#638fa0');ellipse(40,20,22,8,'#345867');ellipse(40,17,22,7,'#80a9ad')
  box(24,27,32,57,'#163144','#456b80');rect(27,30,26,49,'#225a70')
  for y=33,75,6 do line(27,y,52,y,'#2e7788') end
  rect(8,33,9,46,'#233b4a');rect(10,34,3,43,'#5e8790');rect(63,33,9,46,'#233b4a');rect(64,34,3,43,'#5e8790')
  layer('Detalles y materiales')
  for y=40,72,8 do box(5,y,14,5,'#957957','#dac18a');box(61,y,14,5,'#957957','#dac18a') end
  rect(28,91,24,5,'#142630');for x=30,48,6 do rect(x,92,3,2,'#5bcfc4') end
  line(21,30,21,79,'#a9d7d3');rect(30,8,20,6,'#c0d9cc');rect(36,4,8,5,'#7aafb5')
  layer('Luz y animación')
  local shift=(f-1)*4
  for y=32,73 do
    local x=39+math.floor(math.sin((y+shift)/6)*8)
    rect(x-2,y,5,1,'#31b8b5');rect(x,y,2,1,'#bdf8d8')
  end
  for n=1,5 do local x=29+(n*7)%23;local y=31+(n*9+shift)%45;pixel(x,y,'#e5ffeb') end
  rect(27,28,3,51,'#4d929f');rect(52,28,2,51,'#7dccca')
end)

sprite('lab-console',96,72,4,function(f)
  ellipse(48,66,43,5,'#142630');box(5,35,86,29,'#35505f','#8eacac');box(10,6,76,37,'#416372','#b2cfcb');box(15,11,66,26,'#142e41','#274e63')
  layer('Detalles y materiales')
  for y=15,31,4 do line(18,y,77,y,'#1c4353') end
  for x=22,74,9 do line(x,14,x,33,'#1c4353') end
  box(9,44,49,12,'#223946','#658791');for x=13,53,6 do for y=47,53,4 do rect(x,y,4,2,'#7b969b') end end
  for x=65,82,9 do ellipse(x,48,4,4,'#172d3b');ellipse(x-1,47,2,2,'#b8c4aa') end
  rect(11,61,18,5,'#122734');rect(66,61,18,5,'#122734');bolts(5,35,86,29)
  layer('Luz y animación')
  for x=18,77 do local y=24+math.floor(math.sin((x+f*3)/5)*7);pixel(x,y,'#72e7ce') end
  for x=19,51,8 do rect(x,31,4,2,'#459d98') end
  rect(65,56,5,2,f%2==0 and '#e7b779' or '#7b6052');rect(76,56,5,2,'#69ccab')
end)

sprite('lab-workbench',112,72,1,function()
  ellipse(56,66,51,5,'#142630');box(7,41,98,20,'#355665','#86a2a2');rect(12,60,8,9,'#182e3c');rect(92,60,8,9,'#182e3c')
  box(3,26,106,21,'#607f84','#bbccc0');rect(6,43,100,5,'#263f4e')
  layer('Detalles y materiales')
  for x=16,84,34 do box(x,50,25,8,'#29434f','#567982');rect(x+8,52,9,2,'#b9c8b5') end
  box(12,15,22,16,'#986645','#d9a765');rect(18,11,4,5,'#d3c6a1');rect(26,11,4,5,'#d3c6a1')
  line(34,27,47,27,'#e7b665');line(47,27,47,37,'#e7b665');line(47,37,83,37,'#e7b665')
  box(70,17,27,15,'#284859','#72a3a9');rect(74,20,19,8,'#132d3d');line(78,25,87,22,'#80d7bf')
  ellipse(56,20,7,7,'#455f67');ellipse(56,19,5,5,'#c7d1b6');line(56,19,59,16,'#c65f55')
end)

sprite('lab-battery',40,48,1,function()
  ellipse(20,43,16,4,'#142630');rect(10,5,7,6,'#b8cbb8');rect(26,5,5,6,'#c8ae7b')
  box(6,10,30,30,'#a06b4c','#e6b679');box(8,22,26,16,'#385566','#688995')
  layer('Detalles y materiales');rect(15,14,10,2,cream);rect(19,10,2,10,cream);rect(12,27,16,6,'#223647');bolts(6,10,30,30)
end)

sprite('lab-lamp',48,80,4,function(f)
  ellipse(24,73,20,4,'#142630');box(8,65,32,8,'#56747c','#a6c6bf');box(21,26,6,40,'#52727c','#a3bfbb')
  ellipse(24,23,14,16,'#273f4d');ellipse(24,20,12,13,'#66999b');ellipse(24,18,10,10,'#cdd99e')
  rect(15,32,18,7,'#4a6871');for y=33,38,2 do line(16,y,31,y,'#9bad99') end
  layer('Luz y animación');ellipse(24,18,7,8,f%2==0 and '#fff4bc' or '#f0d88b');line(21,15,23,24,'#af815c');line(27,15,24,24,'#af815c');rect(17,12,3,5,'#fff8df')
end)

sprite('lab-coil',64,64,1,function()
  ellipse(32,58,27,5,'#142630');box(8,48,48,9,'#42606b','#9aada5');box(28,17,8,32,'#4d6f79','#a0b7b3')
  for y=22,44,5 do ellipse(32,y,19,5,'#8e5d4c');ellipse(32,y-2,19,4,'#c29463');line(15,y-3,36,y-5,'#edce8b') end
  ellipse(32,12,13,10,'#507983');ellipse(29,9,10,7,'#92b7b7');rect(25,5,7,2,'#d2e1cf')
end)

sprite('math-balance',112,96,6,function(f)
  ellipse(56,87,49,6,'#2e2933');box(33,77,46,11,'#73524e','#d5a56e');box(49,31,14,47,'#9b7959','#e8c68b')
  ellipse(56,27,9,9,'#433741');ellipse(56,26,6,6,'#ddbc79');rect(12,24,88,6,'#75534b');line(12,24,99,24,'#f0d698')
  local dy=({0,1,2,1,0,-1})[f]
  for side=0,1 do local x=25+side*62;local yy=56+(side==0 and dy or -dy)
    line(x,29,x-15,yy,'#d9b37b');line(x,29,x+15,yy,'#d9b37b')
    ellipse(x,yy,19,5,'#c99960');ellipse(x,yy+2,16,5,'#896047');line(x-17,yy,x+17,yy,'#f1d795')
  end
  layer('Detalles y materiales');box(50,48,12,16,'#574447','#b58e60');ellipse(56,55,3,3,'#e9c47e');line(56,55,58,52,'#5b4947')
  for x=40,68,7 do rect(x,81,3,2,'#edc88a') end
  layer('Luz y animación');rect(16,44+dy,11,10,'#58a8a3');rect(17,44+dy,9,2,'#a5e2c4');rect(82,44-dy,11,10,'#d39062');rect(83,44-dy,9,2,'#f3cb90')
end)

sprite('math-board',128,80,1,function()
  box(4,3,120,57,'#8b6953','#e5bc7c');box(10,9,108,44,'#244b48','#406c5e');rect(13,61,7,16,'#634b43');rect(107,61,7,16,'#634b43');box(2,55,124,8,'#735447','#c89f6a')
  layer('Detalles y materiales')
  -- Diagramas de fracciones y geometría, sin texto rasterizado ilegible.
  box(19,19,26,22,'#2b5750','#acc5a0');line(32,20,32,40,'#a7c7a7');line(20,30,43,30,'#a7c7a7');rect(21,21,10,8,'#d6bb75')
  line(56,24,68,24,cream);line(56,29,68,29,cream)
  ellipse(92,28,15,15,'#9bbaa0');ellipse(92,28,13,13,'#244b48');line(92,14,92,28,'#e5c582');line(92,28,104,35,'#e5c582')
  line(20,47,41,47,'#7b9c82');line(52,47,73,47,'#7b9c82');rect(102,55,10,2,cream);rect(80,54,14,4,'#ba875f')
end)

sprite('math-library',96,112,1,function()
  ellipse(48,103,43,5,'#2e2933');box(5,5,86,98,'#7c584a','#cfa374');rect(11,11,74,84,'#302c35')
  layer('Detalles y materiales')
  local book={'#5c9291','#b86f59','#bd9e62','#647e96','#9183a2'}
  for row=0,2 do local y=15+row*28
    for n=0,9 do local x=14+n*7;local h=16+(n*3+row)%8
      box(x,y+23-h,6,h,book[(n+row)%5+1],'#d3bc91');line(x+2,y+25-h,x+2,y+19,'#493c42');pixel(x+3,y+20,'#edcf99')
    end
    box(9,y+23,78,5,'#8b654d','#d4ab77')
  end
  box(12,6,72,4,'#ae865c','#e7c68c');rect(9,100,9,7,'#533e3c');rect(78,100,9,7,'#533e3c')
end)

sprite('math-table',112,80,1,function()
  ellipse(56,73,49,4,'#2e2933');rect(15,49,9,23,'#57413c');rect(88,49,9,23,'#57413c');box(6,28,100,26,'#a37957','#e5ba7d');rect(7,50,98,7,'#705046')
  layer('Detalles y materiales');for y=33,47,7 do line(9,y,101,y,'#8b654d') end
  box(18,25,28,19,'#d9cfa7','#f7edc8');line(32,26,32,43,'#9b8566');for y=29,38,3 do line(21,y,29,y,'#82765e');line(35,y,42,y,'#82765e') end
  box(62,22,15,15,'#5c9794','#b1d7b2');box(78,31,13,13,'#bc8558','#eacf94');ellipse(87,20,7,7,'#d7b574');ellipse(85,18,3,3,'#f4dda5')
end)

sprite('math-orrery',80,104,6,function(f)
  ellipse(40,94,31,5,'#2e2933');box(20,86,40,9,'#795946','#d8b67a');box(36,53,8,34,'#a27b4f','#e4c681')
  ellipse(40,43,34,14,'#b99162');ellipse(40,43,32,12,ink);ellipse(40,43,24,28,'#c6a575');ellipse(40,43,22,26,ink)
  -- Anillos sobre un soporte oscuro para conservar contraste con el suelo.
  ellipse(40,43,13,13,'#b78151');ellipse(37,40,10,10,'#e5bb6f');ellipse(34,37,4,4,'#f6df9d')
  layer('Luz y animación');local a=f*math.pi/3;ellipse(40+math.floor(math.cos(a)*31),43+math.floor(math.sin(a)*11),5,5,'#68b3af');ellipse(40+math.floor(math.cos(a+2)*21),43+math.floor(math.sin(a+2)*25),4,4,'#c88978')
end)

sprite('math-crate',48,48,1,function()
  ellipse(24,43,21,3,'#2e2933');box(4,8,40,34,'#9b7353','#dfb67b');box(9,13,30,24,'#684d42','#b58c62');line(10,14,37,35,'#d2a674');line(11,14,38,35,'#d2a674');bolts(4,8,40,34)
end)

sprite('forest-oak',112,128,1,function()
  ellipse(55,117,43,8,'#173b35');rect(45,64,20,53,'#674b3d');rect(48,67,6,48,'#966b48');rect(60,66,5,50,'#4c3b36')
  line(48,101,35,115,'#674b3d');line(61,99,76,117,'#674b3d');line(47,88,29,67,'#674b3d');line(64,87,83,65,'#674b3d')
  for _,b in ipairs({{35,67,29,23},{72,67,30,25},{27,45,25,25},{80,42,26,24},{54,28,33,25},{52,52,43,31}}) do
    ellipse(b[1],b[2]+3,b[3],b[4],'#183e37');ellipse(b[1]-2,b[2]-2,b[3]-2,b[4]-3,'#306348');ellipse(b[1]-6,b[2]-7,b[3]-6,b[4]-7,'#4e8053')
  end
  layer('Detalles y materiales')
  for n=1,145 do local x=12+(n*37)%87;local y=9+(n*23)%72
    if ((x-55)/48)^2+((y-47)/44)^2<0.86 then
      local c=({'#64985e','#7aaa69','#42704a','#2d5942'})[n%4+1]
      rect(x,y,3+n%4,2,c);pixel(x+1,y-1,c)
    end
  end
  line(51,83,51,106,'#bb8d56');line(58,93,58,111,'#3d352f');ellipse(59,85,3,5,'#3c342e');line(43,115,69,115,'#759550')
end)

sprite('forest-pine',80,128,1,function()
  ellipse(40,118,33,6,'#173b35');box(34,91,12,28,'#76503e','#ae7c4d')
  for j=0,3 do local top=6+j*21;local half=14+j*7;local base=top+34
    for y=top,base do local width=math.floor((y-top)/34*half);rect(40-width,y,width*2+1,1,'#183f39') end
    for y=top+3,base-5 do local width=math.floor((y-top)/34*(half-3));rect(38-width,y,width*2+1,1,'#35654c') end
    for y=top+6,base-8,5 do local width=math.floor((y-top)/34*(half-4));line(38-width,y,42,y,'#5b895a') end
  end
end)

sprite('forest-fern',64,48,1,function()
  ellipse(32,41,28,4,'#173b35')
  for n=-3,3 do local ex=32+n*8;local ey=8+math.abs(n)*6
    line(32,41,ex,ey,'#7fa35c')
    for k=1,5 do local x=32+(ex-32)*k/6;local y=41+(ey-41)*k/6
      line(x,y,x-6,y-5,'#467b53');line(x,y,x+6,y-5,'#64a061');line(x,y-1,x+4,y-5,'#a4bf75')
    end
  end
end)

sprite('forest-rock',80,64,1,function()
  ellipse(40,56,34,5,'#173b35')
  for y=15,52 do local d=math.min((y-15)*2,27);rect(40-d,y,d*2+1,1,'#3c5754') end
  ellipse(37,34,28,21,'#5d7770');ellipse(32,28,21,13,'#81998a');line(19,23,41,18,'#b4c0a3');line(42,22,54,35,'#455e58');line(54,35,49,49,'#455e58')
  layer('Detalles y materiales');scatter(16,28,42,21,38,{'#6d8578','#91a18a','#405e54'},218);ellipse(22,48,13,5,'#4e8053');rect(15,45,13,2,'#80a264')
end)

sprite('forest-mushrooms',48,48,1,function()
  ellipse(24,42,21,4,'#173b35')
  for _,v in ipairs({{15,20,12},{33,29,9}}) do local x,y,r=v[1],v[2],v[3]
    box(x-3,y+4,7,17,'#c4b187','#eddbab');ellipse(x,y,r,8,'#914e4a');ellipse(x-1,y-2,r-1,6,'#c67659');line(x-r+2,y+4,x+r-2,y+4,'#e4b57c')
    rect(x-5,y-4,4,3,'#f1d7a0');rect(x+4,y-1,3,2,'#f1d7a0')
  end
end)

sprite('forest-sign',64,64,1,function()
  ellipse(32,58,23,4,'#173b35');box(28,20,8,37,'#76543f','#b8935d');box(5,9,54,26,'#8e6d48','#d2b479');bolts(5,9,54,26)
  layer('Detalles y materiales');line(17,23,44,23,'#edda9d');line(37,17,44,23,'#edda9d');line(37,29,44,23,'#edda9d');line(10,32,50,32,'#5f4e37')
end)

sprite('forest-beehive',64,80,4,function(f)
  ellipse(32,72,26,5,'#173b35');box(13,54,38,15,'#76533d','#d2a66e');rect(16,68,5,7,'#634733');rect(44,68,5,7,'#634733')
  for j=0,5 do ellipse(32,20+j*6,10+j*3,7,'#986b43');ellipse(31,18+j*6,9+j*3,5,'#d3a45d');line(22-j*2,17+j*6,31,16+j*6,'#f1ce80') end
  ellipse(32,51,7,6,'#493c31')
  layer('Luz y animación');local x=10+(f*11)%44;local y=15+(f%2)*7
  ellipse(x,y-2,3,2,'#e1ebc9');rect(x-2,y,6,4,'#ebc66e');rect(x,y,2,4,'#5a4938')
end)

sprite('forest-flower',32,40,4,function(f)
  local dx=f%2;line(15,34,15+dx,17,'#6a995d');line(15,28,8,23,'#80aa67');line(15,30,23,25,'#80aa67')
  for _,v in ipairs({{-5,0},{5,0},{0,-5},{0,5}}) do ellipse(15+dx+v[1],15+v[2],4,4,'#cf91a0') end
  ellipse(15+dx,15,4,4,'#efd890');pixel(14+dx,14,'#fff0c0')
end)

sprite('shared-planter',48,64,1,function()
  ellipse(24,58,20,4,'#172e32');box(11,38,27,18,'#aa755a','#e1ac7a');box(8,34,32,7,'#ba8963','#e8bc86')
  line(24,35,24,11,'#63916b');for _,v in ipairs({{17,22,-1},{30,18,1},{18,10,-1},{30,29,1}}) do ellipse(v[1],v[2],7,4,'#4f8061');line(24,v[2]+6,v[1],v[2],'#92b87a') end
end)

sprite('shared-door',80,112,1,function()
  box(6,5,68,105,'#496570','#9ab5ae');box(13,11,54,92,'#152c39','#314953');box(17,16,46,81,'#335161','#68928f');line(40,17,40,96,'#162f3c')
  layer('Detalles y materiales');box(23,25,34,32,'#183947','#7dafac');rect(27,29,26,23,'#387588');line(29,30,45,49,'#559aa0');rect(33,70,3,12,'#c3d8c2');rect(44,70,3,12,'#c3d8c2');rect(20,103,40,5,'#79c6b3')
end)

sprite('explorer',32,48,8,function(f)
  local walking=f>=3;local step=walking and ((f%2)*2-1) or 0;local bob=walking and f%2 or 0
  ellipse(16,44,10,3,'#172d32');box(9,31+bob,6,12-step,'#284452','#4a6770');box(18,31+bob,6,12+step,'#284452','#4a6770');rect(8,42-step,8,3,ink);rect(18,42+step,8,3,ink)
  box(6,20+bob,20,15,'#c18b5b','#f0ca88');rect(10,22+bob,12,12,'#487e83');rect(13,22+bob,6,7,'#85b8b0')
  rect(4,23+bob,4,12,'#c18b5b');rect(25,23+bob,4,12,'#c18b5b');rect(4,33+bob,4,3,'#e7b18a');rect(25,33+bob,4,3,'#e7b18a')
  box(8,6+bob,17,16,'#ca946d','#edbe8a');rect(7,4+bob,19,8,'#463c3c');rect(10,2+bob,12,4,'#463c3c');rect(9,5+bob,12,3,'#766054')
  layer('Detalles y materiales');rect(8,12+bob,17,4,'#263d47');rect(10,12+bob,5,3,'#b1e0cb');rect(18,12+bob,5,3,'#83beb9');line(14,19+bob,19,19+bob,'#a66e57');rect(22,25+bob,3,4,'#efce89')
  if f==2 then rect(10,13+bob,5,1,'#2b424b');rect(18,13+bob,5,1,'#2b424b') end
end,{{'idle',1,2},{'walk',3,8}})

local file=assert(io.open(root..'/catalog.json','w'));file:write(json.encode(catalog));file:close()
print('Recursos Aseprite creados: '..#catalog)
