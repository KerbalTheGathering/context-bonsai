// Art styles. A theme's `style` picks one; each style is a set of hooks the scene (Diorama) and the cards
// (FocusView, GroveView) call into. Anything a style leaves out falls back to the diorama look.
//
//   diorama  the living bonsai on a wooden stand: lit bark, leaf sprites, a cast shadow
//   glass    glass & glow: an aurora behind frosted panels, a glass pot, leaves as glowing orbs, neon meters
//   ink      sumi-e: washi paper, brush-stroke wood with ink bleeding into the paper, ink-dab foliage,
//            a red seal, calm motion
import { BlurFilter, Container, FillGradient, Graphics, Sprite, Text, Texture, TilingSprite } from "pixi.js";
import { textures } from "./textures.js";
import { TAU, clamp, hex, leafColor, lerp, mix, mulberry } from "./tree.js";

// --- procedural textures ---
const texCache = new Map();
function canvasTex(key, w, h, draw) {
  if (!texCache.has(key)) {
    const c = document.createElement("canvas");
    c.width = w;
    c.height = h;
    draw(c.getContext("2d"), w, h);
    texCache.set(key, Texture.from(c));
  }
  return texCache.get(key);
}

// A glowing orb: a bright core in a soft halo (glass leaves).
const orb = () => canvasTex("orb", 64, 64, (x, w) => {
  const g = x.createRadialGradient(w / 2, w / 2, 0, w / 2, w / 2, w / 2);
  g.addColorStop(0, "rgba(255,255,255,1)");
  g.addColorStop(0.22, "rgba(255,255,255,0.9)");
  g.addColorStop(0.45, "rgba(255,255,255,0.35)");
  g.addColorStop(1, "rgba(255,255,255,0)");
  x.fillStyle = g;
  x.fillRect(0, 0, w, w);
});

// Ink dabs: irregular, darker at the wet edge, a few variants so the canopy doesn't repeat.
const blots = () => [0, 1, 2, 3].map((v) => canvasTex(`blot${v}`, 72, 56, (x, w, h) => {
  const r = mulberry(91 + v * 7);
  x.translate(w / 2, h / 2);
  for (let i = 0; i < 7; i++) {
    const ox = (r() - 0.5) * w * 0.32, oy = (r() - 0.5) * h * 0.3;
    const rx = w * (0.18 + r() * 0.16), ry = h * (0.16 + r() * 0.16);
    const g = x.createRadialGradient(ox, oy, 0, ox, oy, Math.max(rx, ry));
    g.addColorStop(0, "rgba(255,255,255,0.55)");
    g.addColorStop(0.75, "rgba(255,255,255,0.7)");
    g.addColorStop(0.92, "rgba(255,255,255,0.95)"); // pigment gathers at the edge as it dries
    g.addColorStop(1, "rgba(255,255,255,0)");
    x.fillStyle = g;
    x.beginPath();
    x.ellipse(ox, oy, rx, ry, r() * TAU, 0, TAU);
    x.fill();
  }
  x.globalCompositeOperation = "destination-out"; // dry-brush speckle
  for (let i = 0; i < 40; i++) {
    x.fillStyle = `rgba(0,0,0,${0.2 + r() * 0.5})`;
    x.fillRect((r() - 0.5) * w, (r() - 0.5) * h, 1 + r() * 2, 1);
  }
}));

// Washi: warm paper with fibers and grain, tinted by the theme's wall color.
const paper = (base, light) => canvasTex(`paper${base}`, 256, 256, (x, w, h) => {
  x.fillStyle = base;
  x.fillRect(0, 0, w, h);
  const img = x.getImageData(0, 0, w, h), d = img.data, r = mulberry(5);
  for (let i = 0; i < d.length; i += 4) {
    const n = (r() - 0.5) * (light ? 14 : 10);
    d[i] += n; d[i + 1] += n; d[i + 2] += n;
  }
  x.putImageData(img, 0, 0);
  x.lineCap = "round";
  for (let i = 0; i < 70; i++) { // fibers
    x.strokeStyle = light ? `rgba(120,100,70,${0.04 + r() * 0.05})` : `rgba(255,245,225,${0.025 + r() * 0.03})`;
    x.lineWidth = 0.6 + r();
    x.beginPath();
    const sx = r() * w, sy = r() * h, a = r() * TAU, l = 8 + r() * 26;
    x.moveTo(sx, sy);
    x.quadraticCurveTo(sx + Math.cos(a + 0.6) * l / 2, sy + Math.sin(a + 0.6) * l / 2, sx + Math.cos(a) * l, sy + Math.sin(a) * l);
    x.stroke();
  }
});

// Far mountains in a pale wash, blurred as they're painted (a blur filter would be clipped once cached).
// Covers scene x 0..600, y 220..460.
const hills = (color) => canvasTex(`hills${color}`, 600, 240, (x, w, h) => {
  const n = parseInt(color.replace("#", ""), 16), rgb = `${n >> 16},${(n >> 8) & 255},${n & 255}`;
  const r = mulberry(17);
  x.filter = "blur(4px)";
  for (const [base, amp, alpha, f] of [[90, 64, 0.06, 0.012], [140, 40, 0.09, 0.019]]) {
    x.fillStyle = `rgba(${rgb},${alpha})`;
    x.beginPath();
    x.moveTo(0, h);
    const ph = r() * 6;
    for (let px = 0; px <= w; px += 6) {
      x.lineTo(px, base - amp * (0.55 + 0.45 * Math.sin(px * f + ph) * Math.sin(px * f * 2.7 + ph * 1.3)));
    }
    x.lineTo(w, h);
    x.closePath();
    x.fill();
  }
});

// A tapered brush stroke along a polyline, with a little wobble and dry-brush gaps.
function brush(g, pts, w0, w1, color, alpha, seed = 1, paperColor = null) {
  const r = mulberry(seed), L = [], R = [];
  pts.forEach(([x, y], i) => {
    const a = pts[Math.max(0, i - 1)], b = pts[Math.min(pts.length - 1, i + 1)];
    const tx = b[0] - a[0], ty = b[1] - a[1], n = Math.hypot(tx, ty) || 1;
    const u = i / (pts.length - 1);
    const w = lerp(w0, w1, u) * (0.85 + r() * 0.3) * Math.sin(Math.min(1, u * 6 + 0.25) * Math.PI / 2);
    L.push(x - (ty / n) * w / 2, y + (tx / n) * w / 2);
    R.push([x + (ty / n) * w / 2, y - (tx / n) * w / 2]);
  });
  g.poly([...L, ...R.reverse().flat()]).fill({ color, alpha });
  if (paperColor != null) { // bristle gaps show the paper through
    for (let k = 0; k < 3; k++) {
      const off = (r() - 0.5) * 0.5, from = Math.floor(r() * pts.length * 0.4);
      g.moveTo(...pts[from]);
      for (let i = from + 1; i < pts.length; i++) {
        const [x, y] = pts[i];
        g.lineTo(x + off * lerp(w0, w1, i / pts.length), y + off * 0.3);
      }
      g.stroke({ width: 0.5 + r() * 0.6, color: paperColor, alpha: 0.35, cap: "round" });
    }
  }
}

const line = (x0, y0, x1, y1, n = 12) => Array.from({ length: n }, (_, i) => [lerp(x0, x1, i / (n - 1)), lerp(y0, y1, i / (n - 1))]);

// --- the default look (the diorama style uses these as is) ---
const base = {
  display: ["Segoe UI Variable Display", "Segoe UI", "system-ui", "sans-serif"],
  shadow: true,
  wind: 1,
  fall: 1,
  shafts: true,
  motes: true,
  wood: (d) => {
    const c = d.theme.colors;
    return { bark: hex(c.bark), hi: hex(c.barkHi), hiAlpha: 1, edgeAlpha: 0.55, shade: 0.8, fissure: 0.68 };
  },
  woodEcho: null,
  dome: { texture: (d) => d.tex.disc, alpha: 1, blend: "normal", mul: 1, dl: -15 },
  leaf: {
    texture: (d) => d.tex.leaf,
    mul: 1.22,
    aspect: [1.08, 1],
    blend: "normal",
    tint: (d, l) => leafColor(d.theme.stops, l.cg, l.lift * (d.theme.light ? 1 : 0.75)),
    alpha: () => 1,
  },

  // the card behind the content
  panel(view, { W, h, col }) {
    view.panelFx.removeChildren().forEach((c) => c.destroy());
    view.panel.clear().rect(0, 0, W, h).fill(vgrad(col.panel, col.wall));
  },
  animatePanel() {},
  divider(g, x, y, w, col) {
    g.rect(x, y, w, 1).fill(col.line);
  },
  // the context meter along the shelf edge
  meter(view, { W, y, mh, g, color, col, compacting, now, fresh }) {
    const m = view.meter, glow = view.meterGlow;
    m.clear().rect(0, y - mh / 2, W, mh).fill(col.line);
    glow.clear();
    if (compacting) {
      const span = W * 0.3, a = (W + span) * ((now * 0.6) % 1) - span;
      m.rect(Math.max(0, a), y - mh / 2, Math.min(W, a + span) - Math.max(0, a), mh).fill(color);
    } else {
      const fw = W * clamp(g, 0, 1);
      m.rect(0, y - mh / 2, fw, mh).fill(color);
      glow.rect(Math.max(0, fw - 18), y - mh / 2 - 2, Math.min(18, fw), mh + 4).fill(color); // leading edge
      m.rect(W * 0.85 - 1, y - 5, 2, 10).fill(col.muted);
    }
    if (fresh) glow.filters = null;
  },
};

// Vertical gradients, cached by color pair: FillGradient owns a texture, so don't make one per redraw.
const grads = new Map();
export function vgrad(top, bottom) {
  const key = `${top}|${bottom}`;
  if (!grads.has(key)) {
    grads.set(key, new FillGradient({
      type: "linear", start: { x: 0, y: 0 }, end: { x: 0, y: 1 },
      colorStops: [{ offset: 0, color: top }, { offset: 1, color: bottom }],
    }));
  }
  return grads.get(key);
}

// --- glass ---
const glass = {
  ...base,
  shadow: false,
  wind: 1.25,
  glowAlpha: 0.6,
  wood: (d) => {
    const c = d.theme.colors;
    return { bark: hex(c.bark), hi: hex(c.barkHi), hiAlpha: 0.9, edgeAlpha: 0.8, shade: 0.86, fissure: 0.9 };
  },
  woodEcho: (d) => ({ tint: hex(d.theme.colors.glow), alpha: d.theme.light ? 0.35 : 0.75, blur: 5,
    blend: d.theme.light ? "normal" : "add" }),
  // light themes can't add light, so there leaves lay down color instead
  dome: { texture: (d) => d.tex.glow, alpha: (d) => (d.theme.light ? 0.12 : 0.2), blend: (d) => (d.theme.light ? "normal" : "add"),
    mul: 1.5, dl: 0 },
  leaf: {
    texture: () => orb(),
    mul: 1.9,
    aspect: [1, 1],
    blend: (d) => (d.theme.light ? "normal" : "add"),
    tint: (d, l) => leafColor(d.theme.stops, l.cg, l.lift * 0.4 + 6),
    // additive orbs pile up toward white, so keep each faint enough that the hue survives a dense canopy
    alpha: (d, l, i) => (d.theme.light ? 0.6 : 0.3) + 0.25 * ((i * 0.618) % 1),
  },
  back(d) {
    const t = d.theme, c = t.colors, [x0, y0, x1, y1] = d.crop;
    const g = new Graphics();
    g.rect(x0, y0, x1 - x0, y1 - y0).fill(vgrad(c.wall, c.wall2));
    // a horizon of light where the glass shelf meets the wall, and its reflection fading below
    g.rect(x0, 452, x1 - x0, y1 - 452).fill(vgrad(mixHex(c.wall2, c.glow, t.light ? 0.25 : 0.12), c.wall2));
    d.back.addChild(g);
    const horizon = new Graphics().rect(x0, 451, x1 - x0, 2).fill({ color: c.glow, alpha: t.light ? 0.9 : 0.7 });
    horizon.filters = [new BlurFilter({ strength: 3, quality: 2 })];
    d.back.addChild(horizon, new Graphics().rect(x0, 451.5, x1 - x0, 1).fill({ color: 0xffffff, alpha: t.light ? 0.9 : 0.5 }));

    // the pot: frosted glass with a bright rim, a specular streak and a glow inside
    const p = new Graphics();
    p.poly([172, 402, 428, 402, 412, 436, 188, 436]).fill({ color: c.pot, alpha: t.light ? 0.35 : 0.22 })
      .stroke({ width: 1.4, color: c.potHi, alpha: 0.85 });
    p.poly([180, 405, 196, 405, 204, 432, 192, 432]).fill({ color: 0xffffff, alpha: t.light ? 0.55 : 0.28 });
    p.rect(166, 395, 268, 8).fill({ color: c.pot, alpha: t.light ? 0.5 : 0.35 }).stroke({ width: 1.2, color: c.potHi, alpha: 0.9 });
    p.rect(176, 394, 248, 3).fill({ color: c.soil, alpha: 0.9 });
    d.back.addChild(p);
    const soil = new Graphics().rect(180, 393, 240, 3).fill({ color: c.moss, alpha: 0.9 });
    soil.filters = [new BlurFilter({ strength: 4, quality: 2 })];
    soil.blendMode = t.light ? "normal" : "add";
    d.back.addChild(soil);
  },

  // An aurora: soft colored light drifting slowly behind the tree.
  backFx(d) {
    const c = d.theme.colors, [x0, y0, x1] = d.crop;
    const colors = c.aurora || [c.glow, c.ok, c.potHi];
    d.aurora = colors.map((col, i) => {
      const s = new Sprite(d.tex.glow);
      s.anchor.set(0.5);
      s.tint = hex(col);
      s.alpha = d.theme.light ? 0.4 : 0.32;
      s.blendMode = d.theme.light ? "normal" : "add";
      s.bx = lerp(x0 + 60, x1 - 60, (i + 0.5) / colors.length);
      s.by = y0 + 120 + i * 50;
      s.ph = i * 2.1;
      s.position.set(s.bx, s.by); // where it rests until it drifts
      s.scale.set(4.2, 2.6);
      d.backFx.addChild(s);
      return s;
    });
  },
  animate(d, t) {
    for (const s of d.aurora || []) {
      s.x = s.bx + Math.sin(t * 0.11 + s.ph) * 60;
      s.y = s.by + Math.cos(t * 0.08 + s.ph) * 26;
      s.rotation = Math.sin(t * 0.05 + s.ph) * 0.4;
    }
    return true;
  },

  tally(d, cc) {
    const c = d.theme.colors;
    for (let i = 0; i < Math.min(cc, 12); i++) {
      const tx = 300 + (i % 6) * 8 - (Math.min(cc, 6) - 1) * 4, ty = i >= 6 ? 426 : 418;
      d.tally.circle(tx, ty, 1.8).fill(c.potHi).circle(tx, ty, 3.5).fill({ color: c.potHi, alpha: 0.25 });
    }
  },

  panel(view, { W, h, col, theme, tiles = [] }) {
    const fx = view.panelFx;
    const key = `${theme.key}|${W}|${h}`;
    if (fx.key !== key) {
      fx.key = key;
      fx.removeChildren().forEach((c) => c.destroy());
      const bg = new Graphics().rect(0, 0, W, h).fill(vgrad(col.wall, col.wall2));
      fx.addChild(bg);
      const colors = theme.colors.aurora || [theme.colors.glow, theme.colors.ok, theme.colors.potHi];
      view.blobs = colors.map((c, i) => {
        const s = new Sprite(textures().glow);
        s.anchor.set(0.5);
        s.tint = hex(c);
        s.alpha = theme.light ? 0.5 : 0.38;
        s.blendMode = theme.light ? "normal" : "add";
        s.bx = W * (0.2 + 0.3 * i);
        s.by = h * (0.25 + 0.28 * i);
        s.ph = i * 1.9;
        s.position.set(s.bx, s.by);
        s.scale.set((W / 128) * 1.3, (h / 128) * 0.7);
        fx.addChild(s);
        return s;
      });
    }
    // the frosted pane over the light, a bright top edge, then glass tiles for the sections
    const p = view.panel.clear().rect(0, 0, W, h).fill({ color: col.panel, alpha: theme.light ? 0.55 : 0.62 });
    p.rect(0, 0, W, 1).fill({ color: 0xffffff, alpha: theme.light ? 0.9 : 0.14 });
    for (const t of tiles) {
      p.roundRect(t.x, t.y, t.w, t.h, 12).fill({ color: 0xffffff, alpha: theme.light ? 0.45 : 0.045 })
        .stroke({ width: 1, color: 0xffffff, alpha: theme.light ? 0.8 : 0.1 });
    }
  },
  animatesPanel: true,
  animatePanel(view, t) {
    for (const s of view.blobs || []) {
      s.x = s.bx + Math.sin(t * 0.13 + s.ph) * 40;
      s.y = s.by + Math.cos(t * 0.1 + s.ph) * 24;
    }
  },
  divider() {}, // the glass tiles separate the sections
  cardTile(g, w, h, theme) {
    g.roundRect(-6, -6, w + 12, h + 12, 12).fill({ color: 0xffffff, alpha: theme.light ? 0.4 : 0.04 })
      .stroke({ width: 1, color: 0xffffff, alpha: theme.light ? 0.8 : 0.09 });
  },
  meter(view, { W, y, mh, g, color, col, compacting, now }) {
    const m = view.meter, glow = view.meterGlow, x0 = 12, w = W - 24, h = mh + 1;
    m.clear().roundRect(x0, y - h / 2, w, h, h / 2).fill({ color: col.line, alpha: 0.8 });
    glow.clear();
    if (!glow.filters) {
      glow.filters = [new BlurFilter({ strength: 6, quality: 2 })];
      glow.blendMode = "add";
    }
    if (compacting) {
      const span = w * 0.3, a = x0 + (w + span) * ((now * 0.6) % 1) - span;
      const s0 = Math.max(x0, a), s1 = Math.min(x0 + w, a + span);
      if (s1 > s0) {
        m.roundRect(s0, y - h / 2, s1 - s0, h, h / 2).fill(color);
        glow.roundRect(s0, y - h, s1 - s0, h * 2, h).fill(color);
      }
    } else {
      const fw = Math.max(h, w * clamp(g, 0, 1));
      m.roundRect(x0, y - h / 2, fw, h, h / 2).fill(color);
      m.roundRect(x0 + 2, y - h / 2 + 1, fw - 4, 1, 0.5).fill({ color: 0xffffff, alpha: 0.6 });
      glow.roundRect(x0, y - h, fw, h * 2, h).fill(color); // neon bloom
      m.rect(x0 + w * 0.85 - 1, y - 6, 2, 12).fill({ color: col.ink, alpha: 0.5 });
    }
  },
};

// --- ink (sumi-e) ---
const ink = {
  ...base,
  display: ["Yu Mincho", "Hiragino Mincho ProN", "MS Mincho", "Georgia", "serif"],
  shadow: false,
  wind: 0.55,
  fall: 0.55,
  shafts: false,
  motes: false,
  wood: (d) => {
    const c = d.theme.colors;
    return { bark: hex(c.bark), hi: hex(c.wall), hiAlpha: 0.32, edgeAlpha: 0.3, shade: d.theme.light ? 0.7 : 0.85,
      fissure: null, fissureColor: hex(c.wall), fissureAlpha: 0.5 };
  },
  woodEcho: (d) => ({ tint: hex(d.theme.colors.bark), alpha: 0.22, blur: 3.5, blend: "normal", spread: 1.35 }),
  // ink on light paper multiplies, so overlapping dabs darken like real ink
  dome: { texture: () => blots()[0], alpha: 0.16, blend: (d) => (d.theme.light ? "multiply" : "normal"), mul: 1.25, dl: 8 },
  leaf: {
    texture: (d, i) => blots()[i % 4],
    mul: 1.55,
    aspect: [1.25, 1],
    blend: (d) => (d.theme.light ? "multiply" : "normal"),
    tint: (d, l) => leafColor(d.theme.stops, l.cg, l.lift * 0.25),
    alpha: (d, l, i) => 0.42 + 0.4 * ((i * 0.618) % 1), // washes of different strength
  },
  back(d) {
    const t = d.theme, c = t.colors, [x0, y0, x1, y1] = d.crop;
    const tile = new TilingSprite({ texture: paper(c.wall, t.light), width: x1 - x0, height: y1 - y0 });
    tile.position.set(x0, y0);
    tile.tileScale.set(0.5);
    d.back.addChild(tile);
    const far = new Sprite(hills(c.bark));
    far.position.set(0, 220);
    d.back.addChild(far);
    const r = mulberry(17);
    // the ground: one loaded stroke, and the tray as a few confident marks with a wash inside
    const g = new Graphics();
    brush(g, line(70, 441, 530, 443, 16), 2, 5, hex(c.bark), 0.55, 3, hex(c.wall));
    g.poly([172, 402, 428, 402, 412, 432, 188, 432]).fill({ color: c.pot, alpha: 0.14 });
    brush(g, line(166, 400, 434, 399, 14), 8, 6, hex(c.pot), 0.9, 4, hex(c.wall));
    brush(g, line(176, 404, 190, 432, 6), 3, 2, hex(c.pot), 0.85, 5);
    brush(g, line(424, 404, 410, 432, 6), 3, 2, hex(c.pot), 0.85, 6);
    brush(g, line(190, 432, 410, 432, 12), 2.5, 3.5, hex(c.pot), 0.8, 7, hex(c.wall));
    for (let i = 0; i < 18; i++) g.ellipse(184 + r() * 232, 396 + r() * 2, 2 + r() * 4, 1 + r()).fill({ color: c.moss, alpha: 0.5 });
    d.back.addChild(g);
    // a red seal in the corner
    const seal = new Container();
    const stamp = new Graphics().roundRect(0, 0, 30, 30, 3).fill({ color: c.seal || c.crit, alpha: 0.85 });
    const chars = new Text({ text: "盆\n栽", style: { fontFamily: ink.display, fontSize: 12, fill: c.wall, lineHeight: 13,
      fontWeight: "700", align: "center" } });
    chars.anchor.set(0.5);
    chars.position.set(15, 15);
    seal.addChild(stamp, chars);
    seal.position.set(x1 - 58, 448 - 44);
    seal.rotation = -0.03;
    d.back.addChild(seal);
  },

  tally(d, cc) { // brush ticks on the tray
    const c = d.theme.colors;
    for (let i = 0; i < Math.min(cc, 12); i++) {
      const tx = 286 + (i % 6) * 6 - Math.min(cc, 6) * 3 + 3 + (i >= 6 ? 3 : 0), ty = i >= 6 ? 424 : 416;
      brush(d.tally, line(tx, ty - 5, tx + 1, ty + 3, 5), 2, 1, hex(c.seal || c.crit), 0.85, 10 + i);
    }
  },

  panel(view, { W, h, col, theme }) {
    const fx = view.panelFx;
    const key = `${theme.key}|${W}|${h}`;
    if (fx.key !== key) {
      fx.key = key;
      fx.removeChildren().forEach((c) => c.destroy());
      const tile = new TilingSprite({ texture: paper(theme.colors.panel, theme.light), width: W, height: h });
      tile.tileScale.set(0.5);
      fx.addChild(tile);
    }
    view.panel.clear(); // the paper is the panel
  },
  divider(g, x, y, w, col, seed = 1) {
    brush(g, line(x, y + 0.5, x + w, y + 0.5, 14), 0.6, 2.2, col.ink, 0.35, seed);
  },
  meter(view, { W, y, g, color, col, compacting, now }) {
    const m = view.meter;
    m.clear();
    view.meterGlow.clear();
    brush(m, line(10, y, W - 10, y, 18), 2, 3, col.ink, 0.12, 21);
    if (compacting) {
      const span = (W - 20) * 0.3, a = 10 + (W - 20 + span) * ((now * 0.5) % 1) - span;
      const s0 = Math.max(10, a), s1 = Math.min(W - 10, a + span);
      if (s1 - s0 > 4) brush(m, line(s0, y, s1, y, 8), 3, 4.5, color, 0.85, 22);
    } else if (g > 0.01) {
      brush(m, line(10, y, 10 + (W - 20) * clamp(g, 0, 1), y + 0.5, 18), 3.5, 5, color, 0.85, 23, col.panel);
      brush(m, line(10 + (W - 20) * 0.85, y - 6, 10 + (W - 20) * 0.85 + 1, y + 6, 4), 1.5, 1, col.ink, 0.5, 24);
    }
  },
};

function mixHex(a, b, t) {
  return mix(hex(a), hex(b), t);
}

export const STYLES = { diorama: base, glass, ink };
export const styleOf = (theme) => STYLES[theme?.style] || base;
