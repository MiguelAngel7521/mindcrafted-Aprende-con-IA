/* Persistent WorldEngine. Only trusted runtime code executes; packages are data. */
(function (root) {
  'use strict';
  const directions = {up: [0, -1], down: [0, 1], left: [-1, 0], right: [1, 0]};
  const copy = value => JSON.parse(JSON.stringify(value));
  const key = p => `${p.x},${p.y}`;
  const distance = (a, b) => Math.abs(a.x - b.x) + Math.abs(a.y - b.y);

  const {EventBus, FlagSystem, QuestSystem, DialogueSystem} = typeof module !== 'undefined'
    ? {...require('./event-bus.js'), ...require('./flag-system.js'), ...require('./quest-system.js'), ...require('./dialogue-system.js')}
    : root.MindCraftedWorld;
  const {nodeConnectResult} = typeof module !== 'undefined' ? require('./node-connect.js') : root.MindCraftedWorld;

  function options(m) {
    const result = Object.create(null);
    for (const edge of m.edges) (result[edge.source] ||= []).push(edge.target);
    return result;
  }

  function sequenceResult(m, sequence) {
    const complete = sequence.length === m.switches.length && new Set(sequence).size === m.switches.length && m.switches.every(s => sequence.includes(s.id));
    const rules = Object.create(null);
    for (const c of m.constraints) rules[c.ruleId] = (rules[c.ruleId] ?? true) && complete && sequence.indexOf(c.before) < sequence.indexOf(c.after);
    return {ok: complete && Object.values(rules).every(Boolean), rules};
  }

  function networkResult(m, routes) {
    const nodes = new Map(m.nodes.map(n => [n.id, n]));
    const loads = Object.fromEntries(m.nodes.map(n => [n.id, 0]));
    const rules = Object.fromEntries([...m.nodes, ...m.packets].map(n => [n.ruleId, true]));
    let delivered = 0;
    const paths = [];
    for (const packet of m.packets) {
      let current = packet.source, arrived = false;
      const seen = new Set(), path = [];
      while (nodes.has(current) && !seen.has(current)) {
        seen.add(current); path.push(current); loads[current] += packet.amount;
        if (current === packet.target) { arrived = true; delivered++; break; }
        const next = routes[current];
        if (!m.edges.some(e => e.source === current && e.target === next)) break;
        current = next;
      }
      paths.push(path);
      rules[packet.ruleId] &&= arrived;
    }
    const congested = m.nodes.filter(n => loads[n.id] > n.capacity);
    for (const n of congested) rules[n.ruleId] = false;
    const congestion = new Set(congested.map(n => n.id));
    const successfulRoutes = paths.filter((path, i) => path.at(-1) === m.packets[i].target && !path.some(id => congestion.has(id))).length;
    return {ok: Object.values(rules).every(Boolean), rules, loads, delivered, successfulRoutes, paths, congested: [...congestion]};
  }

  function blocksResult(m, positions) {
    const goals = new Map(m.goals.map(g => [key(g), g]));
    const rules = Object.fromEntries(m.blocks.map(g => [g.ruleId, true]));
    let occupied = 0;
    for (let i = 0; i < positions.length; i++) {
      const goal = goals.get(key(positions[i]));
      if (goal) { occupied++; rules[m.blocks[i].ruleId] &&= goal.accepts.includes(m.blocks[i].kind); }
      else rules[m.blocks[i].ruleId] = false;
    }
    return {ok: occupied === m.blocks.length && Object.values(rules).every(Boolean), rules, complete: occupied === m.blocks.length};
  }

  function initialPuzzle(p) {
    return {sequence: [], routes: {}, blocks: (p.mechanics.blocks || []).map(b => ({x: b.x, y: b.y})),
      solved: false, attempts: 0, errors: 0, hintsUsed: 0, restarts: 0, correctRoutes: 0, invalidRoutes: 0,
      congestionEvents: 0, solutionTime: 0, elapsed: 0, correctActions: 0, invalidActions: 0, solutionSteps: 0, effect: null,
      ...(p.archetype === 'node_connect' ? {connections: [], selectedNode: null} : {})};
  }

  class WorldEngine {
    constructor(spec, {events = new EventBus()} = {}) {
      if (spec.version !== 2 || spec.regions.length !== 1 || !spec.puzzles.length) throw new Error('WorldSpec incompatible');
      this.spec = copy(spec); this.events = events;
      this.region = this.spec.regions[0];
      this.entities = new Map(this.region.entities.map(e => [e.id, e]));
      this.puzzles = new Map(this.spec.puzzles.map(p => [p.id, p]));
      this.dialogues = new Map(this.spec.dialogues.map(d => [d.id, d]));
      this.state = {player: {x: spec.player.x, y: spec.player.y, direction: 'down'}, flags: {}, inventory: [],
        quests: {}, puzzles: Object.fromEntries(spec.puzzles.map(p => [p.id, initialPuzzle(p)])),
        dialogue: null, completedDialogues: [], activePuzzle: spec.puzzles[0].id, xp: 0, completed: false};
      this.initialState = copy(this.state);
      // Campaign observers share events; systems belong to exactly one world.
      this.systemEvents = new EventBus();
      const dependencies = {state: () => this.state, events: this.systemEvents, emit: (name, data) => this.emit(name, data)};
      this.flagSystem = new FlagSystem(dependencies);
      this.questSystem = new QuestSystem({...dependencies, quests: this.spec.quests});
      this.dialogueSystem = new DialogueSystem({...dependencies, dialogues: this.dialogues, entities: this.entities,
        puzzles: this.puzzles, changed: () => this.changed()});
    }
    emit(name, data) { this.systemEvents.emit(name, data); this.events.emit(name, data); }
    changed() { this.emit('world.changed', this.snapshot()); }
    message(text) { this.emit('world.message', {text}); }
    quest(puzzleId) { return this.questSystem.forPuzzle(puzzleId); }
    active(puzzleId) { return this.questSystem.active(puzzleId); }
    currentPuzzle() {
      return [...this.puzzles.values()].reduce((best, p) => distance(this.state.player, this.entities.get(p.world.anchorEntity)) < distance(this.state.player, this.entities.get(best.world.anchorEntity)) ? p : best);
    }
    tick(seconds) {
      if (!this.state.dialogue && !this.state.completed) {
        const p = this.currentPuzzle(), s = this.state.puzzles[p.id];
        if (this.active(p.id) && !s.solved) s.elapsed += Math.max(0, Math.min(seconds, .1));
      }
    }
    isOpen(entity) { return entity.type === 'door' && this.flagSystem.has(entity.requiresFlag); }
    tileFree(x, y) {
      return Number.isInteger(x) && Number.isInteger(y) && this.region.tiles[y]?.[x] === '.' &&
        ![...this.entities.values()].some(e => e.x === x && e.y === y && !['goal', 'exit'].includes(e.type) && !this.isOpen(e));
    }
    blockAt(x, y) {
      for (const p of this.puzzles.values()) {
        if (p.archetype !== 'push_blocks') continue;
        const offset = p.world.offset;
        const index = this.state.puzzles[p.id].blocks.findIndex(b => b.x + offset.x === x && b.y + offset.y === y);
        if (index >= 0) return {p, index};
      }
      return null;
    }
    move(direction) {
      if (!directions[direction] || this.state.dialogue || this.state.completed) return false;
      const [dx, dy] = directions[direction], player = this.state.player;
      player.direction = direction;
      const x = player.x + dx, y = player.y + dy;
      if (!this.tileFree(x, y)) return false;
      const hit = this.blockAt(x, y);
      if (hit) {
        const {p, index} = hit, s = this.state.puzzles[p.id], b = s.blocks[index];
        if (!this.active(p.id) || s.solved) { this.message('Habla con Luna para activar esta misión.'); return false; }
        if (!this.tileFree(x + dx, y + dy) || this.blockAt(x + dx, y + dy) || p.mechanics.board[b.y + dy]?.[b.x + dx] !== '.') { s.invalidActions++; this.changed(); return false; }
        s.solutionSteps++; s.correctActions++;
        b.x += dx; b.y += dy; this.state.activePuzzle = p.id;
        player.x = x; player.y = y;
        const result = blocksResult(p.mechanics, s.blocks);
        if (result.complete) this.assess(p, result);
      } else { player.x = x; player.y = y; }
      this.emit('player.moved', {...this.state.player}); this.changed(); return true;
    }
    nearby() {
      return [...this.entities.values()].filter(e => distance(e, this.state.player) <= 1 && !['door', 'goal'].includes(e.type))
        .sort((a, b) => distance(a, this.state.player) - distance(b, this.state.player));
    }
    interact(entityId) {
      if (this.state.dialogue) { this.advanceDialogue(); return true; }
      if (this.state.completed) return false;
      const e = entityId ? this.entities.get(entityId) : this.nearby()[0];
      if (!e || distance(e, this.state.player) > 1) return false;
      if (e.type === 'exit') {
        if (![...this.puzzles.keys()].every(id => this.state.puzzles[id].solved)) { this.message('Falta restaurar un distrito.'); return false; }
        this.state.completed = true; this.emit('region.completed', {regionId: this.region.id}); this.changed(); return true;
      }
      const p = this.puzzles.get(e.puzzleId);
      if (!p) return false;
      const s = this.state.puzzles[p.id]; this.state.activePuzzle = p.id;
      if ((p.prerequisites || []).some(id => !this.state.puzzles[id]?.solved)) { this.message('Primero restaura los distritos anteriores.'); return false; }
      if (e.type === 'npc') {
        this.emit('entity.interacted', {entityId: e.id});
        return true;
      }
      if (s.solved) { this.message('Este distrito ya está restaurado.'); return false; }
      if (!this.active(p.id)) { this.message('Luna te espera junto a la consola. Habla con ella primero.'); return false; }
      if (e.type === 'switch') {
        if (s.sequence.includes(e.controlId)) { this.message('Ese interruptor ya está activo. R reinicia la cadena.'); return false; }
        s.sequence.push(e.controlId);
        s.solutionSteps++;
        this.message(`${e.label}: energía conectada (${s.sequence.length}/${p.mechanics.switches.length}).`);
        if (s.sequence.length === p.mechanics.switches.length) this.assess(p, sequenceResult(p.mechanics, s.sequence));
      } else if (e.type === 'router') {
        const choices = options(p.mechanics)[e.controlId];
        if (!choices) { this.message(`${e.label}: punto de llegada.`); return false; }
        const index = choices.indexOf(s.routes[e.controlId]);
        s.routes[e.controlId] = choices[(index + 1) % choices.length];
        s.solutionSteps++;
        s.effect = null;
        this.message(`${e.label} → ${s.routes[e.controlId]}. E cambia el cable. Envía los paquetes desde la consola.`);
      } else if (e.type === 'connection_node') {
        s.solutionSteps++; s.effect = null;
        if (!s.selectedNode) {
          s.selectedNode = e.controlId;
          this.message(`${e.label}: origen seleccionado. Camina al destino y pulsa E para conectar o desconectar. E aquí cancela.`);
        } else if (s.selectedNode === e.controlId) {
          s.selectedNode = null; this.message('Selección cancelada. Las conexiones se conservan.');
        } else {
          const edge = p.mechanics.edges.find(edge => edge.source === s.selectedNode && edge.target === e.controlId);
          if (!edge) { s.invalidActions++; this.message('No hay un enlace físico posible en esa dirección. Elige otro destino o cancela en el origen.'); }
          else {
            const index = s.connections.indexOf(edge.id), removed = index >= 0;
            if (removed) s.connections.splice(index, 1); else s.connections.push(edge.id);
            this.message(`${s.selectedNode} → ${e.controlId}: ${removed ? 'desconectado' : 'conectado'}. Comprueba las relaciones en la consola.`);
            s.selectedNode = null;
          }
        }
      } else if (e.type === 'console' && p.archetype === 'node_connect') {
        s.solutionSteps++; s.selectedNode = null;
        this.assess(p, nodeConnectResult(p.mechanics, s.connections));
      } else if (e.type === 'console' && p.archetype === 'route_network') {
        s.solutionSteps++;
        this.assess(p, networkResult(p.mechanics, s.routes));
      } else if (e.type === 'console') this.message(p.objective + ' Consulta tus reglas en el cuaderno.');
      else return false;
      this.changed(); return true;
    }
    openDialogue(id) { this.dialogueSystem.open(id); }
    dialogueLine() { return this.dialogueSystem.line(); }
    advanceDialogue() { this.dialogueSystem.advance(); }
    setFlag(flag) { return this.flagSystem.set(flag); }
    assess(p, result) {
      const s = this.state.puzzles[p.id];
      if (s.solved) return;
      s.attempts++;
      s.effect = p.archetype === 'route_network' ? {...result, routes: {...s.routes}} : result;
      s.correctRoutes += result.successfulRoutes || 0;
      s.invalidRoutes += p.archetype === 'route_network' ? p.mechanics.packets.length - result.successfulRoutes : 0;
      s.congestionEvents += result.congested?.length || 0;
      s.correctActions += Object.values(result.rules).filter(Boolean).length;
      s.invalidActions += Object.values(result.rules).filter(value => !value).length;
      if (!result.ok) s.errors++;
      for (const r of p.knowledge.requiredRules) {
        this.emit('learning.observation', {puzzleId: p.id, skill: r.skill, label: r.description, correct: result.rules[r.id] === true,
          observations: {correctRoutes: s.correctRoutes, invalidRoutes: s.invalidRoutes, congestionEvents: s.congestionEvents,
            correctActions: s.correctActions, invalidActions: s.invalidActions, solutionSteps: s.solutionSteps,
            hintsUsed: s.hintsUsed, solutionTime: Math.round(s.elapsed), solutionTimeMs: Math.round(s.elapsed * 1000), restarts: s.restarts, attempts: s.attempts}});
      }
      if (result.ok) {
        s.solved = true; s.solutionTime = Math.round(s.elapsed);
        this.state.xp += p.success.xp; this.state.inventory.push(p.id + '_energy');
        for (const flag of p.success.setFlags) this.setFlag(flag);
        this.emit('puzzle.solved', {puzzleId: p.id, score: Math.max(.2, 1 - s.errors * .1 - s.hintsUsed * .05), observations: copy(s)});
        this.message('¡Energía restaurada! La compuerta se abrió.');
      } else {
        this.message(p.archetype === 'node_connect' ? 'La infraestructura sigue desconectada. Observa los enlaces del último intento y las reglas incumplidas; puedes reconstruir con E o limpiar con R.' : result.congested?.length ? 'Los routers se saturaron: las luces del distrito se apagaron. Reparte la carga.' : 'La energía no llega a destino. Revisa las reglas y vuelve a intentarlo.');
        this.emit('puzzle.failed', {puzzleId: p.id, worldEffect: p.failure.worldEffect});
        this.reset(p.id, false);
        if (s.attempts >= 2) this.message(this.hintText(p, s.attempts - 1));
      }
    }
    reset(puzzleId = this.currentPuzzle().id, manual = true) {
      const p = this.puzzles.get(puzzleId), s = this.state.puzzles[puzzleId];
      if (!p || s.solved || !this.active(puzzleId) || this.state.dialogue) return false;
      s.sequence = []; s.routes = {}; s.blocks = initialPuzzle(p).blocks;
      if (p.archetype === 'node_connect') { s.connections = []; s.selectedNode = null; }
      if (manual) { s.restarts++; s.effect = null; }
      if (p.archetype === 'push_blocks') this.state.player = {x: p.world.offset.x + p.mechanics.spawn.x, y: p.world.offset.y + p.mechanics.spawn.y, direction: 'down'};
      this.emit('puzzle.reset', {puzzleId, manual}); this.changed(); return true;
    }
    hint() {
      const p = this.currentPuzzle(), s = this.state.puzzles[p.id];
      if (s.solved || !this.active(p.id) || this.state.dialogue || this.state.completed) return;
      s.hintsUsed++; this.message(this.hintText(p, s.hintsUsed)); this.emit('puzzle.hint', {puzzleId: p.id}); this.changed();
    }
    hintText(p, level) {
      const s = this.state.puzzles[p.id], m = p.mechanics;
      if (level <= 0) return '';
      if (level >= Math.max(4, p.failure.hintAfterAttempts)) return p.hint;
      if (level === 1) {
        if (p.archetype === 'node_connect') return 'Un enlace representa una dependencia dirigida. Compara la función de sus dos componentes y sigue la cadena hasta el destino.';
        if (p.archetype === 'route_network') return 'Cada paquete necesita un camino completo. La carga acumulada no debe superar la capacidad de los routers.';
        if (p.archetype === 'switch_sequence') return 'Una etapa solo puede funcionar después de sus requisitos. Busca qué necesita cada etapa.';
        return 'Cada puesto necesita una función. Compara esa necesidad con la función de los módulos antes de empujarlos.';
      }
      if (level >= 3) {
        const rule = p.knowledge.requiredRules.find(r => s.effect?.rules?.[r.id] === false) || p.knowledge.requiredRules[0];
        if (p.archetype === 'node_connect') return `Revisa el componente ${m.nodes.find(n => n.id === m.goals[0].source).label}. E lo selecciona como origen; camina al destino y pulsa E. Repetir el par desconecta. Regla a comprobar: ${rule.description}.`;
        if (p.archetype === 'route_network') {
          const branching = Object.entries(options(m)).find(([, targets]) => targets.length > 1)?.[0];
          return `Acércate al router ${branching || m.packets[0].source}: E cambia su salida. Prueba un camino alternativo y envía desde la consola. Regla a comprobar: ${rule.description}.`;
        }
        return 'Comprueba esta restricción al mover o activar el siguiente objeto: ' + rule.description + '. ' + rule.evidence;
      }
      if (p.archetype === 'node_connect') return s.effect?.invalidEdges?.length ? `Hay ${s.effect.invalidEdges.length} enlaces entre tipos incompatibles. Reconstruye las dependencias sin saltarte las funciones intermedias.` : `${s.connections.length} enlaces construidos. Sigue las flechas, verifica los límites de entrada/salida y busca cadenas incompletas.`;
      if (p.archetype === 'route_network') return s.effect?.congested?.length ? `Sobrecarga observada en ${s.effect.congested.join(', ')}. Compara su carga con la capacidad y busca otro camino.` : `${Object.keys(s.routes).length} salidas conectadas. Sigue cada cable hasta el destino antes de enviar los paquetes.`;
      if (p.archetype === 'switch_sequence') return `${s.sequence.length} de ${m.switches.length} etapas activadas. Observa qué necesita cada etapa antes de empezar; R permite probar otro orden.`;
      return `${s.blocks.filter(b => m.goals.some(g => g.x === b.x && g.y === b.y)).length} módulos sobre puestos. Compara la función de cada módulo con la necesidad del puesto; R recupera módulos atascados.`;
    }
    snapshot() { return copy(this.state); }
    restore(raw) {
      if (!raw || typeof raw !== 'object') return false;
      this.state = copy(this.initialState);
      // Derive gates, rewards and completion from validated solutions, never stored flags.
      for (const p of this.puzzles.values()) {
        const saved = raw.puzzles?.[p.id], fresh = initialPuzzle(p);
        if (!saved || typeof saved !== 'object') continue;
        for (const name of ['attempts', 'errors', 'hintsUsed', 'restarts', 'correctRoutes', 'invalidRoutes', 'congestionEvents', 'solutionTime', 'elapsed', 'correctActions', 'invalidActions', 'solutionSteps']) {
          if (Number.isFinite(saved[name]) && saved[name] >= 0) fresh[name] = Math.min(saved[name], 1000000);
        }
        if (Array.isArray(saved.sequence) && new Set(saved.sequence).size === saved.sequence.length && saved.sequence.every(id => p.mechanics.switches?.some(s => s.id === id))) fresh.sequence = [...saved.sequence];
        if (saved.routes && typeof saved.routes === 'object' && p.archetype === 'route_network') {
          for (const [node, target] of Object.entries(saved.routes)) if (options(p.mechanics)[node]?.includes(target)) fresh.routes[node] = target;
        }
        if (p.archetype === 'node_connect') {
          const allowed = new Set(p.mechanics.edges.map(edge => edge.id));
          fresh.connections = Array.isArray(saved.connections) ? [...new Set(saved.connections.filter(id => allowed.has(id)))] : [];
          fresh.selectedNode = p.mechanics.nodes.some(node => node.id === saved.selectedNode) ? saved.selectedNode : null;
        }
        if (p.archetype === 'push_blocks' && Array.isArray(saved.blocks) && saved.blocks.length === p.mechanics.blocks.length &&
            saved.blocks.every(b => b && Number.isInteger(b.x) && Number.isInteger(b.y) && p.mechanics.board[b.y]?.[b.x] === '.') && new Set(saved.blocks.map(key)).size === saved.blocks.length) fresh.blocks = copy(saved.blocks);
        const result = p.archetype === 'node_connect' ? nodeConnectResult(p.mechanics, fresh.connections) : p.archetype === 'route_network' ? networkResult(p.mechanics, fresh.routes) : p.archetype === 'switch_sequence' ? sequenceResult(p.mechanics, fresh.sequence) : blocksResult(p.mechanics, fresh.blocks);
        fresh.solved = saved.solved === true && result.ok;
        if (p.archetype === 'node_connect') {
          if (fresh.solved) { fresh.effect = result; fresh.selectedNode = null; }
          else if (fresh.attempts > 0 && Array.isArray(saved.effect?.connections)) {
            const allowed = new Set(p.mechanics.edges.map(edge => edge.id));
            const connections = [...new Set(saved.effect.connections.filter(id => allowed.has(id)))];
            const failure = nodeConnectResult(p.mechanics, connections);
            if (!failure.ok) fresh.effect = failure;
          }
        }
        if (p.archetype === 'route_network') {
          if (fresh.solved) fresh.effect = {...result, routes: {...fresh.routes}};
          else if (fresh.attempts > 0 && saved.effect?.routes && typeof saved.effect.routes === 'object') {
            const routes = Object.fromEntries(Object.entries(saved.effect.routes).filter(([node, target]) => options(p.mechanics)[node]?.includes(target)));
            const failure = networkResult(p.mechanics, routes);
            if (!failure.ok) fresh.effect = {...failure, routes};
          }
        }
        this.state.puzzles[p.id] = fresh;
        const q = this.quest(p.id);
        if (raw.quests?.[q.id] === 'active' || fresh.solved) this.state.quests[q.id] = fresh.solved ? 'complete' : 'active';
        if (fresh.solved) {
          for (const flag of p.success.setFlags) this.state.flags[flag] = true;
          this.state.inventory.push(p.id + '_energy'); this.state.xp += p.success.xp;
          for (const effect of this.dialogues.get(p.success.dialogue).onComplete) if (effect.type === 'setFlag' && raw.flags?.[effect.target] === true) this.state.flags[effect.target] = true;
        }
      }
      const dialogueAllowed = d => {
        if (d.trigger.event === 'puzzle.solved') return this.state.puzzles[d.trigger.puzzleId]?.solved === true;
        const npc = this.entities.get(d.trigger.entityId);
        return npc?.dialogueId === d.id && !!this.state.quests[this.quest(npc.puzzleId)?.id];
      };
      for (const d of this.dialogues.values()) {
        if (!dialogueAllowed(d)) continue;
        // Older saves recorded dialogue effects, but had no completedDialogues list.
        const completed = Array.isArray(raw.completedDialogues) ? raw.completedDialogues.includes(d.id) :
          d.onComplete.some(e => e.type === 'startQuest' || (e.type === 'setFlag' && raw.flags?.[e.target] === true));
        if (!completed) continue;
        this.state.completedDialogues.push(d.id);
        for (const effect of d.onComplete) if (effect.type === 'setFlag') this.state.flags[effect.target] = true;
      }
      if (raw.player && this.tileFree(raw.player.x, raw.player.y) && !this.blockAt(raw.player.x, raw.player.y)) {
        const start = this.initialState.player, queue = [{x: start.x, y: start.y}], visited = new Set([key(start)]);
        for (let i = 0; i < queue.length; i++) for (const [dx, dy] of Object.values(directions)) {
          const next = {x: queue[i].x + dx, y: queue[i].y + dy};
          if (!visited.has(key(next)) && this.tileFree(next.x, next.y) && !this.blockAt(next.x, next.y)) { visited.add(key(next)); queue.push(next); }
        }
        if (visited.has(key(raw.player))) this.state.player = {x: raw.player.x, y: raw.player.y, direction: directions[raw.player.direction] ? raw.player.direction : 'down'};
      }
      if (raw.dialogue && this.dialogues.has(raw.dialogue.id) && Number.isInteger(raw.dialogue.line) && raw.dialogue.line >= 0 && raw.dialogue.line < this.dialogues.get(raw.dialogue.id).lines.length) {
        const d = this.dialogues.get(raw.dialogue.id), npc = this.entities.get(d.speaker);
        if (d.trigger.event === 'puzzle.solved' ? dialogueAllowed(d) : npc?.dialogueId === d.id && distance(npc, this.state.player) <= 1) this.state.dialogue = {id: d.id, line: raw.dialogue.line};
      }
      this.state.activePuzzle = this.currentPuzzle().id;
      this.state.completed = raw.completed === true && [...this.puzzles.keys()].every(id => this.state.puzzles[id].solved);
      this.changed(); return true;
    }
  }

  class SaveSystem {
    constructor(storage, scope, hash) { this.storage = storage; this.key = `mindcrafted_world_v2:${scope}:${hash}`; this.hash = hash; }
    save(engine) { try { this.storage?.setItem(this.key, JSON.stringify({version: 2, hash: this.hash, state: engine.snapshot()})); return !!this.storage; } catch (_) { return false; } }
    load(engine) { try { const data = JSON.parse(this.storage?.getItem(this.key) || 'null'); return data?.version === 2 && data.hash === this.hash ? engine.restore(data.state) : false; } catch (_) { return false; } }
  }

  const api = {WorldEngine, EventBus, FlagSystem, QuestSystem, DialogueSystem, SaveSystem, directions, sequenceResult, networkResult, blocksResult, nodeConnectResult};
  root.MindCraftedWorld = api;
  if (typeof module !== 'undefined') module.exports = api;
})(typeof window === 'undefined' ? globalThis : window);
