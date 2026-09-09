-- Exporta cambios manuales de art/source/ sin ejecutar el generador de dibujos.
-- Conserva dimensiones, fotogramas y sus duraciones en los catálogos de la vista.
local root=assert(app.params.root,'Falta root')
local function read(path)local f=assert(io.open(path,'r'));local t=f:read('*a');f:close();return json.decode(t) end
local function write(path,value)local f=assert(io.open(path,'w'));f:write(json.encode(value));f:close() end
local manifest=read(root..'/manifest.json')
for _,asset in ipairs(manifest.assets) do
  local spr=app.open(root..'/'..asset.source)
  assert(spr.width==asset.width and spr.height==asset.height,'Se cambió el tamaño de '..asset.id..': actualiza también el tileset y sus objetos antes de exportar.')
  assert(#spr.frames==asset.frames,'Se cambiaron los fotogramas de '..asset.id..': actualiza primero su catálogo.')
  local sheet=Image(spr.width*#spr.frames,spr.height,ColorMode.RGB)
  for i,frame in ipairs(spr.frames) do
    local flat=Image(spr.width,spr.height,ColorMode.RGB);flat:drawSprite(spr,i,Point(0,0))
    sheet:drawImage(flat,Point((i-1)*spr.width,0))
    if i==1 then flat:saveAs(root..'/'..asset.image) end
  end
  if asset.sheet then sheet:saveAs(root..'/'..asset.sheet) end
  -- La vista usa un paso uniforme. Exige esa condición para no ocultar cambios.
  for _,frame in ipairs(spr.frames) do assert(math.abs(frame.duration-spr.frames[1].duration)<0.001,'Usa una duración uniforme en '..asset.id) end
  asset.frameDuration=math.floor(spr.frames[1].duration*1000+0.5)
  spr:close()
end
write(root..'/manifest.json',manifest);write(root..'/art/catalog.json',manifest.assets)
print('PNG y hojas de animación exportados desde los originales editados.')
