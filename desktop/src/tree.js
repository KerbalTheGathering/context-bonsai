// Tree structure, ported from the Tk widget so each session grows the same shape in both:
// seeded by the CRC-32 of its transcript file name. Coordinates are in the mockup's 600x480 scene.
export const TAU = Math.PI * 2;
export const BASELINE = 0.14;

export const clamp = (v, a, b) => Math.min(b, Math.max(a, v));
export const lerp = (a, b, t) => a + (b - a) * t;

export function mulberry(seed) {
  let s = seed >>> 0;
  return () => {
    s = (s + 0x6d2b79f5) >>> 0;
    let t = s;
    t = Math.imul(t ^ (t >>> 15), 1 | t) >>> 0;
    t = ((t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t) >>> 0;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const CRC = (() => {
  const t = new Uint32Array(256);
  for (let n = 0; n < 256; n++) {
    let c = n;
    for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    t[n] = c >>> 0;
  }
  return t;
})();

export function crc32(str) {
  const bytes = new TextEncoder().encode(str);
  let c = 0xffffffff;
  for (const b of bytes) c = CRC[(c ^ b) & 0xff] ^ (c >>> 8);
  return (c ^ 0xffffffff) >>> 0;
}

// The mockup's tree for seed 11. With vary=true the seed also picks the tree's overall style
// (lean, trunk zigzag, height, branch length and spread, mirroring) so sessions look distinct.
export function buildTree(seed = 11, vary = false) {
  const r = mulberry(seed);
  const segs = [], pads = [], shoots = [];
  let S = 1.45, zig = 0.34, lean = 0, trunkN = 6, branchMul = 1, spreadMul = 1, mirror = false;
  if (vary) {
    const v = mulberry((seed ^ 0x5bd1e995) >>> 0);
    zig = 0.16 + v() * 0.32;
    lean = (v() - 0.5) * 0.44;
    trunkN = 5 + Math.floor(v() * 3);
    branchMul = 0.8 + v() * 0.28;
    spreadMul = 0.8 + v() * 0.5;
    mirror = v() < 0.5;
    S = 1.32 + v() * 0.18;
  }

  const makePad = (x, y, birth, scale) => {
    const leaves = [];
    for (let i = 0; i < 30; i++) {
      const ang = r() * TAU, rad = Math.sqrt(r());
      leaves.push({ dx: Math.cos(ang) * rad, dy: Math.sin(ang) * rad * 0.55 - 0.18, s: 0.6 + r() * 0.6,
        turn: r() * 0.12, rot: r() * TAU, order: r() });
    }
    return { x, y, birth, leaves, size: (17 + r() * 8) * scale * 1.35 };
  };

  const branch = (x, y, a, ln, w, depth, birth) => {
    const ex = x + Math.cos(a) * ln;
    const ey = y + Math.sin(a) * ln + (depth === 0 ? ln * 0.06 : 0);
    segs.push({ x1: x, y1: y, x2: ex, y2: ey, w1: w, w2: w * 0.68, birth, dur: 0.045, depth });
    const end = birth + 0.045;
    if (depth >= 3 || ln < 13 * S) {
      pads.push(makePad(ex, ey, end, 1));
      return;
    }
    for (let k = 0; k < 2; k++) {
      const spread = (k === 0 ? -1 : 1) * (0.34 + r() * 0.3) * spreadMul;
      let na = a + spread;
      if (Math.sin(na) > 0.2) na = a + spread * 0.25;
      branch(ex, ey, na, ln * (0.62 + r() * 0.12), w * 0.68, depth + 1, end + 0.005 + r() * 0.025);
    }
    pads.push(makePad(ex, ey, end + (depth === 0 ? 0.005 : 0.04), depth === 0 ? 0.7 : 0.85));
  };

  let x = 300, y = 398, w = 30, side = 1;
  const segScale = 6 / trunkN; // taller trunks get shorter segments so the tree stays in frame
  for (let i = 0; i < trunkN; i++) {
    const ln = (46 - i * 4 * segScale) * S * segScale;
    const a = -Math.PI / 2 + (i % 2 ? 1 : -1) * zig + (lean * (i + 1)) / trunkN + (r() - 0.5) * 0.08;
    const nx = x + Math.cos(a) * ln, ny = y + Math.sin(a) * ln;
    const birth = i * 0.03;
    segs.push({ x1: x, y1: y, x2: nx, y2: ny, w1: w, w2: w * 0.83, birth, dur: 0.04, trunk: true });
    if (i >= 1) {
      side = -side;
      const ba = side > 0 ? -0.16 - r() * 0.22 : Math.PI + 0.16 + r() * 0.22;
      branch(nx, ny, ba, (66 - i * 7 * segScale + r() * 12) * S * branchMul, w * 0.42, 0, birth + 0.02);
    }
    x = nx; y = ny; w *= 0.83;
  }
  branch(x, y, -Math.PI / 2 + lean + (r() - 0.5) * 0.4, 26 * S, w * 0.85, 1, trunkN * 0.03 + 0.02);

  for (const p of pads) {
    if (r() < 0.5) {
      const a = -Math.PI / 2 + (r() - 0.5) * 2.0;
      const ln = (28 + r() * 36) * S;
      const leaves = [];
      for (let i = 0; i < 5; i++) {
        leaves.push({ t: 0.35 + r() * 0.65, s: 0.5 + r() * 0.4, turn: r() * 0.12, side: r() < 0.5 ? -1 : 1,
          rot: r() * TAU });
      }
      shoots.push({ x: p.x, y: p.y, a, len: ln, bend: (r() - 0.5) * 0.6, birth: 0.64 + r() * 0.26, leaves });
    }
  }
  if (mirror) { // flip around the pot's center line
    for (const s of segs) { s.x1 = 600 - s.x1; s.x2 = 600 - s.x2; }
    for (const p of pads) {
      p.x = 600 - p.x;
      for (const l of p.leaves) l.dx = -l.dx;
    }
    for (const sh of shoots) {
      sh.x = 600 - sh.x; sh.a = Math.PI - sh.a; sh.bend = -sh.bend;
      for (const l of sh.leaves) l.side = -l.side;
    }
  }
  return { segs, pads, shoots };
}

const treeCache = new Map();
export function treeFor(id) {
  if (!id) return buildTree();
  if (!treeCache.has(id)) treeCache.set(id, buildTree(crc32(id), true));
  return treeCache.get(id);
}

export const lushness = (g) => 0.6 + 0.55 * clamp(g, 0, 1) + 0.35 * clamp((g - 0.7) / 0.3, 0, 1);

export function shootPoint(sh, t) {
  const ex = sh.x + Math.cos(sh.a) * sh.len, ey = sh.y + Math.sin(sh.a) * sh.len;
  const perp = sh.a + Math.PI / 2;
  const cx = (sh.x + ex) / 2 + Math.cos(perp) * sh.len * sh.bend * 0.5;
  const cy = (sh.y + ey) / 2 + Math.sin(perp) * sh.len * sh.bend * 0.5;
  const u = 1 - t;
  return [u * u * sh.x + 2 * u * t * cx + t * t * ex, u * u * sh.y + 2 * u * t * cy + t * t * ey];
}

// Every leaf at growth g: { x, y, s, rot, cg (color fill), birth, lift, pad }
export function leavesAt(tree, g) {
  const out = [];
  const lush = lushness(g);
  tree.pads.forEach((p, pi) => {
    const f = clamp((g - p.birth) / 0.12, 0, 1);
    if (f <= 0) return;
    const R = p.size * lush * (0.45 + 0.55 * f);
    for (const l of p.leaves) {
      if (l.order > f) continue;
      out.push({ x: p.x + l.dx * R, y: p.y + l.dy * R, s: l.s, rot: l.rot, cg: g + l.turn, birth: p.birth,
        lift: -l.dy * 14 - l.dx * 3 + (l.turn - 0.06) * 40, depth: l.dy, pad: pi });
    }
  });
  for (const sh of tree.shoots) {
    const f = clamp((g - sh.birth) / 0.08, 0, 1);
    if (f <= 0) continue;
    const perp = sh.a + Math.PI / 2;
    for (const l of sh.leaves) {
      if (l.t > f) continue;
      const [px, py] = shootPoint(sh, l.t);
      out.push({ x: px + Math.cos(perp) * 4 * l.side, y: py + Math.sin(perp) * 4 * l.side, s: l.s, rot: l.rot,
        cg: g + l.turn, birth: sh.birth, lift: 3, depth: -1, pad: -1 });
    }
  }
  return out;
}

export function makePile(count, seed) {
  const r = mulberry(seed);
  const out = [];
  const n = Math.min(90, Math.round(count));
  for (let i = 0; i < n; i++) {
    const left = r() < 0.5;
    const x = left ? lerp(128, 168, r() ** 0.7) : lerp(432, 472, 1 - r() ** 0.7);
    out.push({ x, y: 437 - r() * 3 * (1 - Math.abs((x - 300) / 300)), rot: r() * TAU, s: 0.6 + r() * 0.5, hue: r() });
  }
  for (let i = 0; i < Math.floor(n / 3); i++) {
    out.push({ x: lerp(185, 415, r()), y: 399 + r() * 2, rot: r() * TAU, s: 0.5 + r() * 0.4, hue: r() });
  }
  return out;
}

// Leaf color for a context fill level, as 0xRRGGBB; dl shifts lightness.
export function leafColor(stops, g, dl = 0) {
  g = clamp(g, 0, 1);
  let i = 0;
  while (i < stops.length - 2 && g > stops[i + 1][0]) i++;
  const a = stops[i], b = stops[i + 1];
  const t = clamp((g - a[0]) / (b[0] - a[0]), 0, 1);
  const dh = ((b[1] - a[1] + 540) % 360) - 180; // blend hue the short way round
  return hsl(((a[1] + dh * t) % 360 + 360) % 360, lerp(a[2], b[2], t), clamp(lerp(a[3], b[3], t) + dl, 4, 96));
}

export function hsl(h, s, l) {
  s /= 100; l /= 100;
  const k = (n) => (n + h / 30) % 12;
  const a = s * Math.min(l, 1 - l);
  const f = (n) => Math.round(255 * (l - a * Math.max(-1, Math.min(k(n) - 3, Math.min(9 - k(n), 1)))));
  return (f(0) << 16) | (f(8) << 8) | f(4);
}

export function hex(c) {
  return parseInt(c.replace("#", ""), 16);
}

export function mix(a, b, t) {
  const ar = a >> 16, ag = (a >> 8) & 255, ab = a & 255;
  const br = b >> 16, bg = (b >> 8) & 255, bb = b & 255;
  return (Math.round(lerp(ar, br, t)) << 16) | (Math.round(lerp(ag, bg, t)) << 8) | Math.round(lerp(ab, bb, t));
}

export function stageFor(g) {
  if (g < 0.35) return ["New growth", "ok", "plenty of room"];
  if (g < 0.66) return ["Full canopy", "ok", "still comfortable"];
  if (g < 0.8) return ["Wild shoots", "warn", "old detail piling up"];
  if (g < 0.92) return ["Leaves turning", "warn", "finish this step, then compact"];
  return ["Dropping leaves", "crit", "compact now"];
}
