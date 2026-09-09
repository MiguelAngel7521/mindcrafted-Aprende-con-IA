-- Arte nativo adicional. Solo escribe dentro del directorio temporal indicado.
local root=assert(app.params.output)
local catalog={}
local ink='#101b2b'
local function rgba(s) return app.pixelColor.rgba(tonumber(s:sub(2,3),16),tonumber(s:sub(4,5),16),tonumber(s:sub(6,7),16),255) end
local img
local function rect(x,y,w,h,c)
  for yy=y,y+h-1 do for xx=x,x+w-1 do
    if xx>=0 and yy>=0 and xx<img.width and yy<img.height then img:drawPixel(xx,yy,rgba(c)) end
  end end
end
local function box(x,y,w,h,c)
  rect(x,y,w,h,ink);rect(x+1,y+1,w-2,h-2,c);rect(x+2,y+2,w-4,1,'#67869b')
end
local function sprite(id,w,h,frames,draw,tags)
  local s=Sprite(w,h,ColorMode.RGB);s.layers[1].name='Volumen';local light=s:newLayer();light.name='Luz y detalles'
  local sheet=Image(w*frames,h,ColorMode.RGB)
  for f=1,frames do
    if f>1 then s:newEmptyFrame() end
    s.frames[f].duration=0.16
    img=Image(w,h,ColorMode.RGB);draw(f,false);s:newCel(s.layers[1],f,img,Point(0,0))
    local flat=Image(w,h,ColorMode.RGB);flat:drawImage(img,Point(0,0))
    img=Image(w,h,ColorMode.RGB);draw(f,true);s:newCel(light,f,img,Point(0,0));flat:drawImage(img,Point(0,0))
    if f==1 then flat:saveAs(root..'/exports/'..id..'.png') end
    sheet:drawImage(flat,Point((f-1)*w,0))
  end
  for _,t in ipairs(tags or {{'idle',1,frames}}) do local tag=s:newTag(t[2],t[3]);tag.name=t[1] end
  s:saveAs(root..'/source/'..id..'.aseprite')
  if frames>1 then sheet:saveAs(root..'/exports/'..id..'-sheet.png') end
  catalog[#catalog+1]={id=id,width=w,height=h,frames=frames,frameDuration=160,source='art/source/'..id..'.aseprite',image='art/exports/'..id..'.png',sheet=frames>1 and ('art/exports/'..id..'-sheet.png') or nil,tags=tags or {{'idle',1,frames}}}
  s:close()
end
sprite('terrain-technology',256,64,1,function(f,light)
  for i=0,15 do local x=(i%8)*32;local y=math.floor(i/8)*32
    if not light then
      box(x,y,32,32,i>=8 and i<12 and '#35415c' or '#202d43')
      rect(x+3,y+3,26,1,'#3d5267');rect(x+3,y+28,26,1,'#142035')
      for j=1,5 do rect(x+4+(j*7+i*3)%24,y+5+(j*11+i*2)%21,1,1,'#3b4b61') end
    elseif i>=12 then rect(x+14,y,3,32,'#4bdaca');rect(x+18,y,1,32,'#24616c')
    elseif i>=8 then rect(x+5,y+12,22,2,'#65748b');rect(x+6,y+18,18,2,'#172237') end
  end
end)
sprite('tech-server',64,96,4,function(f,light)
  if not light then box(6,8,52,82,'#26364f');box(10,13,44,72,'#162538');rect(13,87,38,5,'#101b2b')
    for i=0,4 do box(14,18+i*13,36,10,'#334962') end
  else for i=0,4 do rect(18,22+i*13,19,2,'#607b90');rect(42,21+i*13,3,3,(i+f)%3==0 and '#e8b977' or '#58dacb') end end
end)
sprite('tech-terminal',48,64,4,function(f,light)
  if not light then box(5,8,38,35,'#334962');box(9,13,30,23,'#132d3d');box(20,43,8,9,'#526279');box(4,52,40,9,'#2b3d54')
  else rect(13,17,18,2,'#62e4d4');rect(13,23,11+f*2,2,'#7fa4ba');rect(13,29,8,2,'#e8b977');for i=0,7 do rect(8+i*4,55,2,2,'#86a3b6') end end
end)
sprite('tech-beacon',32,48,4,function(f,light)
  if not light then box(5,30,22,15,'#33445d');box(12,14,8,17,'#273951');box(7,5,18,12,'#245f70')
  else rect(10,8,12,5,f%2==0 and '#9ffff0' or '#56cdbf');rect(9,34,14,2,'#e8b977') end
end)
sprite('adventure-explorer',32,48,16,function(f,light)
  local d=math.floor((f-1)/4);local step=(f-1)%4;local bob=step%2;local side=d==1 or d==2
  if not light then
    rect(7,44,20,3,ink);box(9,30+bob,6,13-step%2,'#34475a');box(18,30+bob,6,12+step%2,'#34475a')
    box(side and 9 or 6,19+bob,side and 16 or 21,16,'#c7986c');rect(11,22+bob,11,11,'#347789')
    box(8,5+bob,17,15,'#d8a57f');rect(7,3+bob,19,7,'#4a3b42');rect(10,1+bob,13,3,'#71535a')
    if d==3 then box(9,21+bob,16,13,'#5d6571') end
  elseif d~=3 then
    rect(d==1 and 8 or d==2 and 18 or 9,11+bob,side and 7 or 16,4,'#152c42')
    rect(d==1 and 8 or d==2 and 20 or 10,12+bob,side and 4 or 5,2,'#8ff5e5')
    if not side then rect(19,12+bob,4,2,'#8ff5e5') end
  else rect(12,24+bob,10,2,'#7acdbf') end
end,{{'down',1,4},{'left',5,8},{'right',9,12},{'up',13,16}})
for variant=1,3 do
  sprite('adventure-boss-'..variant,96,96,4,function(f,light)
    local palettes={'#4bcfca','#e8b977','#9dd283'};local c=palettes[variant];local bob=f%2*2
    if not light then
      box(22,20+bob,52,55,'#2f3b55');box(30,10+bob,36,20,'#485c72');box(30,35+bob,36,24,'#122d40')
      for i=0,2 do box(8+i*3,34+i*13+bob,14,9,'#52677b');box(74-i*3,34+i*13+bob,14,9,'#52677b') end
      box(28,75+bob,12,14,'#34475e');box(56,75+bob,12,14,'#34475e')
      if variant==2 then box(41,1+bob,14,14,'#977451') elseif variant==3 then box(12,8+bob,17,24,'#42674f');box(67,8+bob,17,24,'#42674f') end
    else
      rect(34,40+bob,9,6,c);rect(53,40+bob,9,6,c);rect(39,53+bob,18,2,c)
      for i=0,3 do rect(29+i*10,64+bob,6,3,(i+f)%3==0 and '#f4e5b8' or c) end
      rect(37,15+bob,22,3,c)
    end
  end)
end
local out=assert(io.open(root..'/catalog.json','w'));out:write(json.encode(catalog));out:close()
