-- Crea una copia editable del escenario completo: un objeto por capa Aseprite.
local root=assert(app.params.root,'Falta root')
local function read(path)local f=assert(io.open(path,'r'));local t=f:read('*a');f:close();return json.decode(t) end
local manifest=read(root..'/manifest.json')
local assets={};for _,a in ipairs(manifest.assets) do assets[a.id]=a end
for _,world in ipairs(manifest.worlds) do
  if not app.params.world or app.params.world==world.id then
  local map=read(root..'/'..world.map)
  local spr=Sprite(map.width*32,map.height*32,ColorMode.RGB);spr.gridBounds=Rectangle(0,0,32,32)
  local ground=Image(spr.width,spr.height,ColorMode.RGB)
  local atlas=Image{fromFile=root..'/art/exports/terrain-'..world.id..'.png'}
  for i,gid in ipairs(map.layers[1].data) do
    local tile=Image(32,32,ColorMode.RGB);local n=gid-1
    tile:drawImage(atlas,Point(-(n%8)*32,-math.floor(n/8)*32))
    ground:drawImage(tile,Point(((i-1)%map.width)*32,math.floor((i-1)/map.width)*32))
  end
  spr.layers[1].name='Suelo · '..world.subject;spr:newCel(spr.layers[1],1,ground,Point(0,0))
  -- json.decode devuelve arrays con metatabla: ordenar una tabla Lua normal.
  local objects={};for _,obj in ipairs(map.layers[2].objects) do objects[#objects+1]=obj end
  table.sort(objects,function(a,b) return a.y<b.y or (a.y==b.y and a.id<b.id) end)
  for _,obj in ipairs(objects) do
    local id;for _,p in ipairs(obj.properties) do if p.name=='asset_id' then id=p.value end end
    local asset=assets[id];local image=Image{fromFile=root..'/'..asset.image}
    local layer=spr:newLayer();layer.name=id..' · '..obj.id
    spr:newCel(layer,1,image,Point(obj.x,obj.y-obj.height))
  end
  spr:saveAs(root..'/scenes/'..world.id..'.aseprite')
  spr:close()
  end
end
print('Escenarios seleccionados guardados en scenes/.')
