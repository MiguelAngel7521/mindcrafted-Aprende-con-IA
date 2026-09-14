'use strict';
const assert = require('node:assert/strict');
const BKT = require('../mindcrafted/engine/bkt.js');

// Numeric expectations from Bayes plus the learning transition, independent of UI.
assert.ok(Math.abs(BKT.update(0.25, true) - 0.648) < 1e-12);
assert.ok(Math.abs(BKT.update(0.25, false) - 0.1552) < 1e-12);
assert.ok(Math.abs(BKT.update(0.25, true, {learn: 0}) - 0.6) < 1e-12);

const values = new Map();
const storage = {
  getItem: key => values.get(key) ?? null,
  setItem: (key, value) => values.set(key, value),
};
const tracker = BKT.createTracker({scope: 'curso-uno', storage});
for (let i = 0; i < 4; i++) tracker.observe('fracciones', true, {score: 90, label: 'Fracciones'});
const restored = BKT.createTracker({scope: 'curso-uno', storage});
assert.equal(restored.storageKey, 'mindcrafted_bkt_v1');
assert.equal(restored.get('fracciones').attempts, 4);
assert.equal(restored.get('fracciones').correct, 4);
assert.equal(restored.get('fracciones').lastScore, 90);
assert.equal(restored.get('fracciones').label, 'Fracciones');
assert.equal(restored.get('fracciones').mastered, true);
assert.equal(restored.summary().skills, 1);
assert.equal(restored.summary().mastered, 1);
const independent = BKT.createTracker({scope: 'curso-dos', storage});
assert.equal(independent.get('fracciones').attempts, 0);
independent.observe('fracciones', false, {score: 30});
assert.equal(independent.summary().skills, 1);
assert.equal(restored.get('fracciones').attempts, 4);
assert.equal(restored.summary().skills, 1);

// A corrupt persisted JSON blob must not prevent a new observation.
values.set(tracker.storageKey, 'broken JSON');
const recovered = BKT.createTracker({scope: 'recuperado', storage});
assert.equal(recovered.get('algebra').attempts, 0);
recovered.observe('algebra', true, {score: 125});
assert.equal(recovered.get('algebra').lastScore, 100);
assert.equal(recovered.get('algebra').attempts, 1);
assert.equal(JSON.parse(values.get(tracker.storageKey)).version, 1);
console.log('OK: legacy BKT formula, persisted mastery, course isolation, and corrupt JSON recovery.');
