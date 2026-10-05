// The JS tree generator must match the Tk widget's (fixtures from tools/tree_fixture.py), so a session
// grows the same tree in both.
const test = require("node:test");
const assert = require("node:assert/strict");
const fixture = require("./fixtures/trees.json");

const close = (a, b, tol, msg) => assert.ok(Math.abs(a - b) <= tol, `${msg}: ${a} vs ${b}`);

test("tree generator matches the Python one", async () => {
  const T = await import("../src/tree.js");
  for (const f of fixture.trees) {
    const name = f.id || "(default)";
    assert.equal(T.crc32(f.id), f.crc, `${name} crc32`);
    const tree = T.treeFor(f.id);
    assert.equal(tree.segs.length, f.segs.length, `${name} segment count`);
    assert.equal(tree.pads.length, f.pads.length, `${name} pad count`);
    assert.equal(tree.shoots.length, f.shoots.length, `${name} shoot count`);
    tree.segs.forEach((s, i) => [s.x1, s.y1, s.x2, s.y2, s.w1, s.birth]
      .forEach((v, k) => close(v, f.segs[i][k], 1e-9, `${name} seg ${i}.${k}`)));
    tree.pads.forEach((p, i) => [p.x, p.y, p.size, p.birth].forEach((v, k) => close(v, f.pads[i][k], 1e-9, `${name} pad ${i}.${k}`)));
    tree.shoots.forEach((s, i) => [s.x, s.y, s.a, s.len, s.birth]
      .forEach((v, k) => close(v, f.shoots[i][k], 1e-9, `${name} shoot ${i}.${k}`)));
    for (const [g, pts] of Object.entries(f.leaves)) {
      const js = T.leavesAt(tree, +g);
      assert.equal(js.length, pts.length, `${name} leaves at ${g}`);
      // Python yields pads then shoots in tree order; leavesAt does the same before any sorting.
      js.forEach((l, i) => { close(l.x, pts[i][0], 1e-9, `${name} leaf ${i} x`); close(l.y, pts[i][1], 1e-9, `${name} leaf ${i} y`); });
    }
  }
});

test("leaf colors match within rounding", async () => {
  const T = await import("../src/tree.js");
  for (const [g, rgb] of fixture.colors) {
    const c = T.leafColor(fixture.stops, g);
    [c >> 16, (c >> 8) & 255, c & 255].forEach((v, k) => close(v, rgb[k], 1, `color at ${g} channel ${k}`));
  }
});
