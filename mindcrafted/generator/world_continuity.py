"""Browser-only observer used by the deterministic gate, never shipped as gameplay."""

INSTALL = r"""() => {
  const canvas = document.getElementById('world');
  let engine = window.worldEngine;
  const violations = new Set();
  const forbidden = 'iframe, #mini-game-overlay, #overlay, #arena, #arena-hud, [data-mode="arena"]';
  const inspect = node => {
    if (node.nodeType !== 1) return;
    if (node.matches(forbidden) || node.querySelector(forbidden)) violations.add('Separate encounter UI');
    if ((node.matches('canvas') && node !== canvas) || [...node.querySelectorAll('canvas')].some(c => c !== canvas)) violations.add('Second game canvas');
  };
  new MutationObserver(records => {
    for (const record of records) {
      for (const node of record.addedNodes) inspect(node);
      for (const node of record.removedNodes) if (node === canvas || node.contains?.(canvas)) violations.add('World canvas removed');
    }
  }).observe(document.body, {childList: true, subtree: true});
  function check({sameEngine = false, pixels = false} = {}) {
    if (document.getElementById('world') !== canvas || !canvas.isConnected) violations.add('World canvas replaced');
    if (document.querySelectorAll('canvas').length !== 1) violations.add('Second game canvas');
    if (document.querySelector(forbidden)) violations.add('Separate encounter UI');
    if (sameEngine && window.worldEngine !== engine) violations.add('WorldEngine replaced during puzzle');
    for (let node = canvas; node; node = node.parentElement) {
      const style = getComputedStyle(node);
      if (style.display === 'none' || style.visibility !== 'visible' || Number(style.opacity) === 0) violations.add('World hidden');
    }
    const box = canvas.getBoundingClientRect();
    if (!box.width || !box.height) violations.add('World hidden');
    const x = Math.max(0, box.left) + Math.min(box.width, innerWidth - box.left) / 2;
    const top = Math.max(0, box.top), bottom = Math.min(innerHeight, box.bottom);
    if (bottom > top && x >= 0 && x < innerWidth && document.elementFromPoint(x, (top + bottom) / 2) !== canvas) violations.add('World covered');
    // A legacy encounter can reuse the same canvas. Verify actual map floor pixels.
    if (pixels) {
      const {camera, cell} = __MINDCRAFTED_TEST__.getView(), region = worldEngine.region;
      const ctx = canvas.getContext('2d'); let samples = 0, matches = 0;
      for (let y = Math.ceil(camera.y); y < Math.min(region.height, camera.y + canvas.height / cell - 1); y++) {
        for (let x = Math.ceil(camera.x); x < Math.min(region.width, camera.x + canvas.width / cell - 1); x++) {
          if (region.tiles[y][x] !== '.' || region.entities.some(e => e.x === x && e.y === y)) continue;
          const pixel = ctx.getImageData(Math.round((x - camera.x) * cell) + 3, Math.round((y - camera.y) * cell) + 20, 1, 1).data;
          const expected = (x + y) % 2 ? [21, 45, 52] : [23, 49, 55];
          samples++; if (expected.every((value, i) => pixel[i] === value)) matches++;
        }
      }
      if (samples < 8 || matches / samples < .6) violations.add('World map replaced by another scene');
    }
    return [...violations];
  }
  function frame() { check(); requestAnimationFrame(frame); }
  // CampaignSession replaces the region engine at a declared transition. Keep
  // the canvas identity and all historical violations across that boundary.
  window.__WORLD_CONTINUITY__ = {check, enterRegion: () => { engine = window.worldEngine; }};
  frame();
}"""


def install_continuity_guard(page):
    page.evaluate(INSTALL)


def assert_world_continuity(page, *, same_engine=False, pixels=False):
    violations = page.evaluate("options => __WORLD_CONTINUITY__.check(options)",
                               {"sameEngine": same_engine, "pixels": pixels})
    assert not violations, "WORLD_INTEGRATION_ERROR: " + "; ".join(violations)
