(async function () {
  'use strict';
  const $ = id => document.getElementById(id), core = window.MindCraftedWorld;
  const canvas = $('world'), ctx = canvas.getContext('2d');
  const reduced = matchMedia('(prefers-reduced-motion: reduce)');
  let engine, session, packageData, tracker, saves, paused = false, last = 0, held = null, heldAt = 0;
  let uiKey = '', camera = {x: 0, y: 0}, time = 0;
  const sprites = {}, cell = 48;
  const keyMap = {ArrowUp: 'up', ArrowDown: 'down', ArrowLeft: 'left', ArrowRight: 'right', w: 'up', s: 'down', a: 'left', d: 'right'};
  function node(tag, text, cls) { const n = document.createElement(tag); if (text !== undefined) n.textContent = text; if (cls) n.className = cls; return n; }
  function status(text) { $('feedback').textContent = text; }
  function localStorageSafe() { try { return window.localStorage; } catch (_) { return null; } }
  function safeLink(value) { try { const url = new URL(value, location.href); return url.origin === location.origin && ['http:', 'https:'].includes(url.protocol) ? url.href : '#'; } catch (_) { return '#'; } }
  function refresh() {
    const s = engine.state, p = engine.currentPuzzle(), state = s.puzzles[p.id];
    $('position').textContent = session ? `REGIÓN ${session.index + 1} / ${packageData.campaign.regions.length} · SECTOR ${engine.spec.puzzles.indexOf(p) + 1}` : `SECTOR ${engine.spec.puzzles.indexOf(p) + 1} / ${engine.spec.puzzles.length}`;
    $('progress').textContent = `${Object.values(s.puzzles).filter(p => p.solved).length} / ${engine.spec.puzzles.length}`;
    $('xp').textContent = (session ? session.xp : s.xp) + ' XP';
    $('quest-title').textContent = p.title; $('objective').textContent = state.solved ? 'Compuerta abierta. Avanza hacia el este para continuar.' : p.objective;
    const nearby = engine.nearby()[0];
    $('interaction').textContent = s.dialogue ? 'Luna está conversando contigo. El mundo sigue aquí.' : nearby ? `${nearby.label} · E para ${nearby.type === 'npc' ? 'conversar' : nearby.type === 'router' ? 'cambiar la ruta' : nearby.type === 'connection_node' ? state.selectedNode ? 'conectar/desconectar con el origen seleccionado' : 'seleccionar como origen' : nearby.type === 'exit' ? 'continuar' : nearby.type === 'switch' ? 'activar' : 'usar la consola'}.` : state.selectedNode ? 'Origen seleccionado. Camina a otro componente y pulsa E. R reinicia.' : 'Explora el distrito. Acércate a un objeto para interactuar.';
    $('interact').disabled = !nearby && !s.dialogue;
    $('dialogue').hidden = !s.dialogue;
    const line = engine.dialogueLine();
    if (line) { $('speaker').textContent = line.speaker; $('dialogue-text').textContent = line.text; }
    $('completion').hidden = !(session ? session.completed : s.completed);
    $('inventory').textContent = `${(session ? session.inventory : s.inventory).length} núcleos de energía recuperados.`;
    $('reset').disabled = state.solved || !engine.active(p.id) || !!s.dialogue;
    const nextKey = JSON.stringify([p.id, s.quests, tracker.summary().records]);
    if (nextKey !== uiKey) {
      uiKey = nextKey;
      $('missions').replaceChildren(...engine.spec.quests.map(q => node('div', `${s.quests[q.id] === 'complete' ? '✓' : s.quests[q.id] === 'active' ? '◇' : '○'} ${q.title}`, 'mission ' + (s.quests[q.id] || 'locked'))));
      $('rule-list').replaceChildren(...p.knowledge.requiredRules.map(r => { const n = node('p', r.description); n.append(node('small', r.evidence)); return n; }));
      $('mastery').replaceChildren(...tracker.summary().records.map(r => { const n = node('div', r.label + ' · ' + Math.round(r.mastery * 100) + '%', 'skill'); const meter = node('meter'); meter.min = 0; meter.max = 1; meter.value = r.mastery; meter.setAttribute('aria-label', r.label); n.append(meter); return n; }));
    }
  }
  function screen(x, y) { return [(x - camera.x) * cell, (y - camera.y) * cell]; }
  function rect(x, y, w, h, color) { ctx.fillStyle = color; ctx.fillRect(Math.round(x), Math.round(y), w, h); }
  function label(text, x, y, color = '#c5e1d9', max = 130) {
    ctx.font = '12px Pixel, monospace'; ctx.fillStyle = '#0b1820e8';
    const clipped = text.length > 23 ? text.slice(0, 21) + '…' : text;
    const width = Math.min(max, ctx.measureText(clipped).width + 10);
    ctx.fillRect(x - width / 2, y - 11, width, 17); ctx.fillStyle = color; ctx.textAlign = 'center'; ctx.fillText(clipped, x, y + 1, max - 6);
  }
  function drawConnections(p) {
    const state = engine.state.puzzles[p.id], connections = new Set(state.effect?.connections || state.connections);
    const controls = new Map([...engine.entities.values()].filter(e => e.puzzleId === p.id && e.type === 'connection_node').map(e => [e.controlId, e]));
    for (const edge of p.mechanics.edges) {
      const a = controls.get(edge.source), b = controls.get(edge.target);
      const [ax, ay] = screen(a.x + .5, a.y + .5), [bx, by] = screen(b.x + .5, b.y + .5);
      // Curves separate opposite directions and avoid drawing a long edge through
      // an unrelated component on the same row or column.
      const dx = bx - ax, dy = by - ay, length = Math.hypot(dx, dy), bend = Math.min(64, length * .3);
      const cx = (ax + bx) / 2 - dy / length * bend, cy = (ay + by) / 2 + dx / length * bend;
      const point = t => [(1 - t) ** 2 * ax + 2 * (1 - t) * t * cx + t * t * bx,
        (1 - t) ** 2 * ay + 2 * (1 - t) * t * cy + t * t * by];
      const active = connections.has(edge.id), candidate = state.selectedNode === edge.source;
      ctx.strokeStyle = active ? state.solved ? '#96efbe' : state.effect?.invalidEdges.includes(edge.id) ? '#ee977a' : state.effect ? '#e0bf7e' : '#73babc' : candidate ? '#e0bf7e' : '#315058';
      ctx.lineWidth = active ? 4 : candidate ? 2 : 1; ctx.setLineDash(active ? [] : [4, 7]);
      ctx.beginPath(); ctx.moveTo(ax, ay); ctx.quadraticCurveTo(cx, cy, bx, by); ctx.stroke(); ctx.setLineDash([]);
      if (active || candidate) {
        const t = .68, [mx, my] = point(t), angle = Math.atan2((1 - t) * (cy - ay) + t * (by - cy), (1 - t) * (cx - ax) + t * (bx - cx));
        ctx.beginPath(); ctx.moveTo(mx - Math.cos(angle - .5) * 10, my - Math.sin(angle - .5) * 10);
        ctx.lineTo(mx, my); ctx.lineTo(mx - Math.cos(angle + .5) * 10, my - Math.sin(angle + .5) * 10); ctx.stroke();
        if (state.solved) {
          const phase = reduced.matches ? .5 : time / 1.8 % 1;
          const [px, py] = point(phase);
          rect(px - 3, py - 3, 6, 6, '#e8ffd1');
        }
      }
    }
  }
  function draw() {
    const {player} = engine.state, region = engine.region;
    const columns = canvas.width / cell;
    const targetX = Math.max(0, Math.min(region.width - columns, player.x - columns / 2 + .5));
    const targetY = Math.max(0, Math.min(region.height - 13, player.y - 7));
    camera.x = reduced.matches ? targetX : camera.x + (targetX - camera.x) * .22;
    camera.y = reduced.matches ? targetY : camera.y + (targetY - camera.y) * .22;
    ctx.imageSmoothingEnabled = false; rect(0, 0, canvas.width, canvas.height, '#11232b');
    for (let y = Math.max(0, Math.floor(camera.y)); y < Math.min(region.height, camera.y + 14); y++) {
      for (let x = Math.max(0, Math.floor(camera.x)); x < Math.min(region.width, camera.x + columns + 1); x++) {
        const [sx, sy] = screen(x, y), wall = region.tiles[y][x] === '#';
        rect(sx, sy, cell, cell, wall ? '#283e45' : (x + y) % 2 ? '#152d34' : '#173137');
        if (wall) { rect(sx + 2, sy + 2, 44, 7, '#42575b'); rect(sx + 3, sy + 13, 42, 25, '#31484e'); rect(sx, sy + 42, 48, 6, '#0b1920'); }
        else { rect(sx, sy, 47, 1, '#254249'); rect(sx + 47, sy, 1, 48, '#0d252b'); if ((x * 17 + y * 13) % 9 === 0) rect(sx + 11, sy + 36, 5, 2, '#34564c'); }
      }
    }
    for (const p of engine.puzzles.values()) {
      const s = engine.state.puzzles[p.id];
      if (p.archetype === 'node_connect') { drawConnections(p); continue; }
      if (p.archetype !== 'route_network') continue;
      // Automatic recovery clears controls, but leaves the failed traffic visible.
      const routes = s.effect?.routes || s.routes;
      const byControl = new Map([...engine.entities.values()].filter(e => e.puzzleId === p.id && e.type === 'router').map(e => [e.controlId, e]));
      for (const edge of p.mechanics.edges) {
        const a = byControl.get(edge.source), b = byControl.get(edge.target);
        const [ax, ay] = screen(a.x + .5, a.y + .5), [bx, by] = screen(b.x + .5, b.y + .5);
        const active = routes[edge.source] === edge.target;
        ctx.strokeStyle = active ? s.solved ? '#96efbe' : s.effect && !s.effect.ok ? '#e68d77' : '#73babc' : '#315058';
        ctx.lineWidth = active ? 4 : 1; ctx.setLineDash(active ? [] : [4, 7]);
        ctx.beginPath(); ctx.moveTo(ax, ay); ctx.lineTo(bx, by); ctx.stroke(); ctx.setLineDash([]);
        if (active) {
          const traversed = s.effect?.paths.some(path => path.some((id, i) => id === edge.source && path[i + 1] === edge.target));
          if (traversed) {
            const jammed = s.effect.congested.includes(edge.target);
            const phase = jammed ? .82 : reduced.matches ? .5 : time / 1.6 % 1;
            rect(ax + (bx - ax) * phase - 3, ay + (by - ay) * phase - 3, 6, 6, jammed ? '#ee977a' : '#e8ffd1');
          }
          const mid = .68, angle = Math.atan2(by - ay, bx - ax), mx = ax + (bx - ax) * mid, my = ay + (by - ay) * mid;
          ctx.beginPath(); ctx.moveTo(mx, my); ctx.lineTo(mx - Math.cos(angle - .5) * 9, my - Math.sin(angle - .5) * 9); ctx.moveTo(mx, my); ctx.lineTo(mx - Math.cos(angle + .5) * 9, my - Math.sin(angle + .5) * 9); ctx.stroke();
        }
      }
    }
    const actors = [...engine.entities.values(), {type: 'player', ...player}];
    for (const p of engine.puzzles.values()) if (p.archetype === 'push_blocks') engine.state.puzzles[p.id].blocks.forEach((b, i) => actors.push({type: 'block', x: b.x + p.world.offset.x, y: b.y + p.world.offset.y, label: p.mechanics.blocks[i].kind}));
    actors.sort((a, b) => a.y - b.y || (a.type === 'goal' ? -1 : 1));
    for (const e of actors) {
      const [x, y] = screen(e.x, e.y), s = engine.state.puzzles[e.puzzleId];
      if (x < -100 || x > canvas.width + 100) continue;
      if (e.type === 'goal') { rect(x + 2, y + 2, 44, 44, '#728c4960'); ctx.strokeStyle = '#b9ca7b'; ctx.lineWidth = 2; ctx.strokeRect(x + 4, y + 4, 40, 40); label(e.label, x + 24, y + 46, '#cddbad', 115); }
      else if (e.type === 'door') {
        if (engine.isOpen(e)) { rect(x + 3, y, 5, 48, '#7fcf9f'); rect(x + 40, y, 5, 48, '#7fcf9f'); }
        else { rect(x + 3, y - 12, 42, 60, '#496776'); rect(x + 10, y - 7, 28, 51, '#213b46'); for (let n = 0; n < 4; n++) rect(x + 11, y + 2 + n * 10, 26, 4, '#c78869'); }
      } else if (e.type === 'exit') { rect(x + 7, y - 8, 34, 51, '#598a72'); rect(x + 11, y - 4, 26, 43, '#a9efba'); label('SALIDA →', x + 24, y - 17, '#b6edc2'); }
      else if (e.type === 'player' || e.type === 'npc') {
        ctx.fillStyle = '#07171b99'; ctx.beginPath(); ctx.ellipse(x + 24, y + 40, 15, 6, 0, 0, Math.PI * 2); ctx.fill();
        const sprite = sprites.player;
        if (sprite?.complete && sprite.naturalWidth) {
          const frames = {down: 0, left: 4, right: 8, up: 12}, frame = e.type === 'npc' ? 0 : frames[player.direction] + (held && !reduced.matches ? Math.floor(time * 8) % 4 : 0);
          if (e.type === 'npc') ctx.filter = 'hue-rotate(100deg)';
          ctx.drawImage(sprite, frame * 32, 0, 32, 48, x + 5, y - 20, 38, 58); ctx.filter = 'none';
        } else { rect(x + 14, y + 7, 20, 29, e.type === 'npc' ? '#bcaada' : '#6cd3aa'); rect(x + 14, y - 3, 20, 17, '#edcc9d'); rect(x + 12, y - 6, 24, 8, '#3f596c'); rect(x + 16, y + 35, 6, 7, '#172129'); rect(x + 27, y + 35, 6, 7, '#172129'); }
        if (e.type === 'npc') label(s.solved ? 'Luna · ✓' : 'Luna · !', x + 24, y - 24, '#d5c2e9');
      } else if (e.type === 'block') { rect(x + 7, y + 6, 34, 34, '#b88e58'); rect(x + 11, y + 10, 26, 24, '#665b46'); label(e.label, x + 24, y + 24, '#fff0c1', 42); }
      else if (e.type === 'connection_node') {
        const m = engine.puzzles.get(e.puzzleId).mechanics, selected = s.selectedNode === e.controlId;
        const failed = s.effect && (s.effect.degreeErrors.includes(e.controlId) || s.effect.cycleNodes.includes(e.controlId) ||
          m.edges.some(edge => s.effect.invalidEdges.includes(edge.id) && [edge.source, edge.target].includes(e.controlId)));
        const connected = m.edges.some(edge => (s.effect?.connections || s.connections).includes(edge.id) && [edge.source, edge.target].includes(e.controlId));
        const color = s.solved ? '#86d9ab' : selected ? '#e0bf7e' : failed ? '#ee977a' : connected ? '#73babc' : '#30494f';
        rect(x + 8, y + 4, 32, 35, '#4a686c'); rect(x + 14, y + 8, 20, 14, color);
        for (let i = 0; i < 3; i++) rect(x + 13 + i * 9, y + 29, 5, 5, color);
        if (selected) { ctx.strokeStyle = '#e0bf7e'; ctx.lineWidth = 2; ctx.strokeRect(x + 4, y, 40, 43); }
        label(e.label, x + 24, y - 9, selected ? '#e0bf7e' : '#c5e1d9', 145);
        label(m.nodes.find(n => n.id === e.controlId).kind.replaceAll('_', ' '), x + 24, y + 54, color, 130);
        if (failed) label('REVISAR RELACIÓN', x + 24, y + 72, '#ee977a', 120);
      }
      else {
        const network = ['route_network', 'node_connect'].includes(engine.puzzles.get(e.puzzleId)?.archetype);
        const routes = s?.effect?.routes || s?.routes;
        const active = s?.solved || (e.type === 'switch' ? s?.sequence.includes(e.controlId) : !!routes?.[e.controlId]);
        const congested = s?.effect?.congested?.includes(e.controlId);
        const power = network && (e.type === 'console' || congested) && s?.effect && !s.effect.ok ? '#ee977a' : active ? '#86d9ab' : '#30494f';
        rect(x + 8, y + 8, 32, 33, '#0a1d25'); rect(x + 10, y + 4, 28, 28, '#4a686c'); rect(x + 14, y + 8, 20, 14, power);
        rect(x + 14, y + 26, 7, 3, s?.effect && !s.effect.ok ? '#ee977a' : '#d7bd7c');
        const text = e.type === 'router' ? `${e.controlId}${routes?.[e.controlId] ? ' → ' + routes[e.controlId] : ''}` : e.type === 'console' ? network && s.solved ? 'RED RESTAURADA' : 'ENVIAR / CONTROL' : e.label;
        label(text, x + 24, y - 6, active ? '#b2edc2' : '#b4ccd0', 120);
        if (e.type === 'router') {
          const n = engine.puzzles.get(e.puzzleId).mechanics.nodes.find(n => n.id === e.controlId);
          label(`carga ${s?.effect?.loads?.[e.controlId] || 0}/${n.capacity}`, x + 24, y + 49, congested ? '#ee977a' : '#d0bd91', 80);
          if (congested) for (let i = 0; i < Math.min(6, s.effect.loads[e.controlId]); i++) rect(x + 2 + i * 7, y + 35, 5, 5, '#ee977a');
        }
        if (network && e.type === 'console') {
          for (let i = 0; i < 3; i++) rect(x + 5 + i * 14, y + 37, 10, 5, s.solved ? '#96efbe' : '#30494f');
          label(s.solved ? 'DISTRITO CON ENERGÍA' : s.effect ? 'RED CAÍDA · R reinicia' : 'DISTRITO SIN ENERGÍA', x + 24, y + 56, s.solved ? '#96efbe' : '#e0bf7e', 150);
        }
      }
    }
    const near = engine.nearby()[0];
    if (near && !engine.state.dialogue) { const [x, y] = screen(near.x + .5, near.y); label('E', x, y - 41, '#132f25', 20); }
  }
  function action(fn) { if (!paused && engine) { fn(); if (session) session.advance(); refresh(); } }
  function release() { held = null; }
  function pause() { paused = !paused; release(); $('pause-note').hidden = !paused; $('pause').textContent = paused ? 'Continuar · Esc' : 'Pausa · Esc'; }
  function frame(now) {
    const dt = Math.min((now - last) / 1000 || 0, .1); last = now;
    if (!paused) { time += dt; engine.tick(dt); if (held && now - heldAt >= 145) { heldAt = now; engine.move(held); } }
    draw(); requestAnimationFrame(frame);
  }
  try {
    const embedded = $('world-data');
    if (embedded) packageData = JSON.parse(embedded.textContent);
    else {
      const params = new URLSearchParams(location.search), course = params.get('course'), game = params.get('game');
      if (!course) throw new Error('Falta seleccionar el curso.');
      const response = await fetch(game ? `/api/play/${encodeURIComponent(course)}/${encodeURIComponent(game)}/package` : `/api/v2/campaigns/${encodeURIComponent(course)}/package`);
      if (!response.ok) throw new Error('No se pudo cargar la región.');
      packageData = await response.json();
    }
    const config = packageData.config || {}, world = packageData.world;
    session = packageData.campaign ? new core.CampaignSession(packageData.campaign) : null;
    engine = session ? session.engine : new core.WorldEngine(world);
    const storage = localStorageSafe(), scope = (config.courseId || config.sourceHash || world.id) + ':' + (session ? 'campaign' : config.chunkId || world.id);
    tracker = window.MindCraftedBKT.createTracker({scope: config.courseId || config.sourceHash || world.id, storage});
    saves = new core.SaveSystem(storage, scope, config.worldHash);
    saves.load(session || engine);
    if (session) engine = session.engine;
    const events = session ? session.events : engine.events;
    events.on('world.message', event => status(event.text));
    events.on('learning.observation', event => tracker.observe(event.skill, event.correct, {label: event.label, score: event.correct ? 100 : 0, observations: event.observations}));
    events.on('world.changed', () => { if (!saves.save(session || engine)) status('El guardado no está disponible. Puedes continuar en esta sesión.'); refresh(); });
    events.on('region.completed', () => status('Región completada. Puedes continuar el viaje cuando quieras.'));
    events.on('campaign.region.changed', () => {
      engine = session.engine; release(); camera = {x: 0, y: 0}; uiKey = '';
      $('region-name').textContent = engine.region.title;
      $('introduction').textContent = engine.spec.introduction;
      status('Entraste en ' + engine.region.title + '. Tu progreso anterior está guardado.');
    });
    for (const [id, source] of Object.entries(packageData.sprites || {})) if (/^data:image\/png;base64,/.test(source)) { const image = new Image(); image.src = source; sprites[id] = image; }
    $('title').textContent = packageData.title; document.title = packageData.title + ' · MindCrafted';
    $('region-name').textContent = engine.region.title; $('introduction').textContent = engine.spec.introduction;
    $('back').href = config.courseId ? '/courses/' + encodeURIComponent(config.courseId) + '/' : '/';
    $('next').href = safeLink(config.nextGameUrl || $('back').href);
    $('interact').onclick = () => action(() => engine.interact());
    $('advance').onclick = () => action(() => engine.advanceDialogue());
    $('hint').onclick = () => action(() => engine.hint());
    $('reset').onclick = () => action(() => engine.reset());
    $('pause').onclick = pause;
    window.addEventListener('keydown', event => {
      if (event.altKey || event.ctrlKey || event.metaKey || /^(INPUT|TEXTAREA|SELECT)$/.test(event.target.tagName)) return;
      const k = event.key.length === 1 ? event.key.toLowerCase() : event.key;
      if (k === 'Escape') { if (!event.repeat) pause(); return; }
      if (keyMap[k]) { event.preventDefault(); if (!event.repeat) { held = keyMap[k]; heldAt = performance.now(); action(() => engine.move(held)); } }
      else if (['e', 'r', 'h'].includes(k)) { event.preventDefault(); if (!event.repeat) action(() => k === 'e' ? engine.interact() : k === 'r' ? engine.reset() : engine.hint()); }
    });
    window.addEventListener('keyup', event => { if (keyMap[event.key] || keyMap[event.key.toLowerCase()]) release(); });
    window.addEventListener('blur', release);
    document.addEventListener('visibilitychange', () => { release(); saves.save(session || engine); });
    for (const b of document.querySelectorAll('[data-direction]')) {
      b.onpointerdown = event => { event.preventDefault(); b.setPointerCapture(event.pointerId); held = b.dataset.direction; heldAt = performance.now(); action(() => engine.move(held)); };
      b.onpointerup = b.onpointercancel = release;
    }
    window.addEventListener('pagehide', () => saves.save(session || engine));
    const resize = () => { canvas.width = innerWidth <= 600 ? 576 : 864; };
    window.addEventListener('resize', resize); resize();
    if (config.debug === true) {
      Object.defineProperty(window, 'worldEngine', {get: () => engine});
      window.__MINDCRAFTED_TEST__ = {getState: () => engine.snapshot(), getBKT: () => tracker.summary(), getCampaign: () => session?.snapshot(), getView: () => ({camera: {...camera}, cell})};
    }
    window.render_game_to_text = () => JSON.stringify({coordinates: 'tile coordinates; x right, y down', player: engine.state.player, nearby: engine.nearby(), quests: engine.state.quests, puzzles: engine.state.puzzles, flags: engine.state.flags, dialogue: engine.dialogueLine(), completed: engine.state.completed});
    $('app').hidden = false; $('loading').hidden = true; refresh(); $('stage').focus(); requestAnimationFrame(frame);
  } catch (error) { $('loading').textContent = 'No se pudo abrir el mundo: ' + error.message; $('loading').dataset.error = 'true'; }
})();
