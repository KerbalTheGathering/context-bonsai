// The living bonsai scene: a backdrop, a pot and a tree whose canopy tracks how full a session's context
// is. Leaves are sprites that move in a gusty wind; branches and trunk are vector meshes rebuilt only when
// the tree grows. Everything is drawn in the mockup's 600x480 scene units. The theme's style (src/styles.js)
// decides how each part looks; with no hook, the diorama look below is used.
import { BlurFilter, Container, FillGradient, Filter, Graphics, Rectangle, Sprite, Texture, defaultFilterVert } from "pixi.js";
import { styleOf } from "./styles.js";
import { textures } from "./textures.js";
import {
  BASELINE, TAU, clamp, hex, lerp, leafColor, leavesAt, lushness, makePile, mix, shootPoint,
} from "./tree.js";

export const CROPS = {
  focus: [30, -95, 570, 462], // extra wall above the canopy for the % readout
  grove: [70, 0, 530, 462],
  zen: [30, 0, 570, 462],
};

const shadeHex = (c, f) => (f >= 1 ? mix(hex(c), 0xffffff, f - 1) : mix(0x000000, hex(c), f));
const val = (v, d) => (typeof v === "function" ? v(d) : v);

// Pixel theme: snap the scene to a coarse grid, like the Tk widget's low-res-and-scale-up look.
function pixelateFilter(size) {
  return Filter.from({
    gl: {
      vertex: defaultFilterVert,
      fragment: `
        precision highp float;
        in vec2 vTextureCoord;
        out vec4 finalColor;
        uniform sampler2D uTexture;
        uniform vec4 uInputSize;
        uniform vec4 uOutputFrame;
        uniform vec2 uSize;
        void main() {
          vec2 c = vTextureCoord * uInputSize.xy + uOutputFrame.xy;
          c = floor(c / uSize) * uSize + uSize * 0.5;
          finalColor = texture(uTexture, (c - uOutputFrame.xy) / uInputSize.xy);
        }`,
    },
    resources: { pixelUniforms: { uSize: { value: [size, size], type: "vec2<f32>" } } },
  });
}

export class Diorama extends Container {
  constructor(app, { width, crop = CROPS.focus, theme, tree, detail = "full" }) {
    super();
    this.app = app;
    this.tex = textures();
    this.crop = crop;
    this.detail = detail;
    this.theme = theme;
    this.tree = tree;
    this.g = 0.06; // growth currently shown (tweened by the owner)
    this.cc = 0; // compactions, shown as tally marks on the pot
    this.builtKey = null;
    this.leafSprites = [];
    this.domeSprites = [];
    this.leaves = [];
    this.particles = [];
    this.pile = [];
    this.wind = 0;
    this.time = Math.random() * 100;
    this.shadowAt = 0;
    this.phase = "idle";
    this.skyTint = { color: 0xffffff, alpha: 0 };

    this.world = new Container();
    this.back = new Container();
    this.backFx = new Container(); // live backdrop effects a style may add (an aurora)
    this.tally = new Graphics();
    this.pileLayer = new Container();
    this.shadow = new Sprite();
    this.treeRoot = new Container(); // bends in the wind around the trunk base
    this.treeInner = new Container(); // scene coordinates, the source of the cast shadow
    this.branches = new Graphics();
    this.trunk = new Graphics();
    // the wood again, sharing its geometry, softened behind it: glow in glass, ink bleeding into paper in ink
    this.woodEcho = new Container();
    this.woodEcho.addChild(new Graphics(this.branches.context), new Graphics(this.trunk.context));
    this.domes = new Container();
    this.leafLayer = new Container();
    this.fx = new Container();
    this.glow = new Container();
    this.glow.blendMode = "add";
    this.sky = new Graphics();
    this.tools = new Container();

    this.treeRoot.position.set(300, 398);
    this.treeRoot.pivot.set(300, 398);
    this.treeInner.addChild(this.woodEcho, this.branches, this.trunk, this.domes, this.leafLayer);
    this.treeRoot.addChild(this.treeInner);
    this.world.addChild(this.back, this.backFx, this.tally, this.pileLayer, this.shadow, this.treeRoot, this.fx, this.glow,
      this.sky, this.tools);
    this.addChild(this.world);
    this.clip = new Graphics();
    this.addChild(this.clip);
    this.mask = this.clip;

    this.makeTools();
    this.makeShafts();
    this.resize(width);
  }

  // Scene units -> pixels for a given output width.
  resize(width) {
    const [x0, y0, x1, y1] = this.crop;
    this.k = width / (x1 - x0);
    this.w = width;
    this.h = Math.round((y1 - y0) * this.k);
    this.world.scale.set(this.k);
    this.world.position.set(-x0 * this.k, -y0 * this.k);
    this.clip.clear().rect(0, 0, this.w, this.h).fill(0xffffff);
    this.buildBack();
    this.builtKey = null;
  }

  setTheme(theme) {
    if (theme.key === this.theme?.key) return;
    this.theme = theme;
    this.buildBack();
    this.makeTools();
    this.builtKey = null;
    this.pileLayer.children.forEach((s, i) => (s.tint = leafColor(theme.stops, 0.82 + (this.pile[i]?.hue || 0) * 0.2)));
  }

  setTree(tree) {
    if (tree === this.tree) return;
    this.tree = tree;
    this.builtKey = null;
  }

  C(name) {
    return hex(this.theme.colors[name]);
  }

  get S() {
    return styleOf(this.theme);
  }

  // Leaf sprite scale for a texture, so every style's leaf covers the same ground.
  leafScale(texture, s) {
    const L = this.S.leaf;
    const k = (8.8 * s * L.mul) / texture.width;
    return [k * L.aspect[0], k * L.aspect[1]];
  }

  // --- static backdrop: wall, shelf, stand, pot (cached to a texture) ---
  buildBack() {
    this.back.cacheAsTexture(false);
    this.back.removeChildren().forEach((c) => c.destroy({ children: true }));
    this.backFx.removeChildren().forEach((c) => c.destroy());
    const S = this.S, t = this.theme, [x0, y0, x1, y1] = this.crop;
    (S.back || ((d) => d.dioramaBack()))(this);
    S.backFx?.(this);
    this.back.cacheAsTexture({ resolution: Math.max(1, this.k * devicePixelRatio), antialias: true });
    this.filters = t.pixel ? [pixelateFilter(Math.max(2, Math.round(3 * this.k * devicePixelRatio)))] : null;
    this.sky.clear().rect(x0, y0, x1 - x0, y1 - y0).fill(0xffffff);
    this.sky.alpha = 0;
    const echo = S.woodEcho?.(this);
    this.woodEcho.visible = !!echo;
    if (echo) {
      this.woodEcho.children.forEach((g) => (g.tint = echo.tint));
      this.woodEcho.alpha = echo.alpha;
      this.woodEcho.blendMode = echo.blend;
      this.woodEcho.filters = [new BlurFilter({ strength: echo.blur, quality: 3 })];
    }
    if (!S.shadow) this.shadow.visible = false;
  }

  // wall, shelf, wooden stand, a glazed pot with moss
  dioramaBack() {
    const t = this.theme, c = t.colors, [x0, y0, x1, y1] = this.crop;
    const g = new Graphics();
    const wall = new FillGradient({
      type: "linear", start: { x: 0, y: 0 }, end: { x: 0, y: 1 },
      colorStops: [{ offset: 0, color: c.wall }, { offset: 1, color: c.wall2 }],
    });
    g.rect(x0, y0, x1 - x0, y1 - y0).fill(wall);
    g.rect(x0, 452, x1 - x0, y1 - 452).fill(c.wall2);
    g.rect(x0, 452, x1 - x0, 1.5).fill(c.line);
    // stand: plank with a lit top edge, legs
    g.rect(140, 446, 14, 10).fill(c.woodDark);
    g.rect(446, 446, 14, 10).fill(c.woodDark);
    g.rect(116, 438, 368, 10).fill(c.wood);
    g.rect(116, 438, 368, 1.6).fill(shadeHex(c.wood, 1.3));
    g.rect(116, 446, 368, 2).fill(c.woodDark);
    this.back.addChild(g);

    // a pool of warm light from the top left, so the scene has a light source
    const pool = new Sprite(this.tex.glow);
    pool.anchor.set(0.5);
    pool.position.set(170, y0 + 90);
    pool.scale.set(5.2, 4);
    pool.tint = hex(c.glow);
    pool.alpha = t.light ? 0.35 : 0.11;
    pool.blendMode = t.light ? "normal" : "add";
    this.back.addChild(pool);

    const shadow = new Graphics().ellipse(306, 438.5, 142, 5).fill({ color: 0x000000, alpha: t.light ? 0.45 : 0.6 });
    shadow.filters = [new BlurFilter({ strength: 4, quality: 3 })];
    this.back.addChild(shadow);

    const p = new Graphics();
    p.rect(192, 430, 22, 8).fill(c.potDark);
    p.rect(386, 430, 22, 8).fill(c.potDark);
    const body = new FillGradient({
      type: "linear", start: { x: 0, y: 0 }, end: { x: 1, y: 0 },
      colorStops: [{ offset: 0, color: c.potHi }, { offset: 0.3, color: c.pot }, { offset: 1, color: c.potDark }],
    });
    p.poly([172, 402, 428, 402, 412, 432, 188, 432]).fill(body);
    p.rect(180, 409, 240, 1.6).fill(shadeHex(c.pot, 1.18)); // a thrown ring around the body
    p.rect(166, 395, 268, 9).fill(c.potDark); // rim
    p.rect(168, 395.6, 264, 1.5).fill(shadeHex(c.potHi, 1.15));
    p.rect(176, 394, 248, 4).fill(c.soil);
    let s = 5;
    const rnd = () => ((s = (s * 16807) % 2147483647) / 2147483647);
    for (let i = 0; i < 46; i++) {
      p.ellipse(180 + rnd() * 240, 394 + rnd() * 2, 3 + rnd() * 5, 1.6 + rnd() * 1.4).fill(c.moss);
    }
    this.back.addChild(p);
  }

  // --- tree geometry ---
  rebuild() {
    const g = this.g, tree = this.tree, c = this.theme.colors, stops = this.theme.stops, S = this.S;
    const W = S.wood(this), bark = W.bark;
    const cc = this.cc;
    this.branches.clear();
    const bw = 0.6 + 0.4 * clamp(g / 0.6, 0, 1);
    for (const s of tree.segs) {
      if (s.trunk) continue;
      const p = clamp((g - s.birth) / s.dur, 0, 1);
      if (p <= 0) continue;
      const x2 = lerp(s.x1, s.x2, p), y2 = lerp(s.y1, s.y2, p);
      const w1 = Math.max(1.2, s.w1 * bw), w2 = Math.max(0.9, lerp(s.w1, s.w2, p) * bw);
      const dx = x2 - s.x1, dy = y2 - s.y1, n = Math.hypot(dx, dy) || 1e-6;
      const nx = -dy / n, ny = dx / n;
      this.branches.poly([s.x1 + nx * w1 / 2, s.y1 + ny * w1 / 2, x2 + nx * w2 / 2, y2 + ny * w2 / 2,
        x2 - nx * w2 / 2, y2 - ny * w2 / 2, s.x1 - nx * w1 / 2, s.y1 - ny * w1 / 2]).fill(bark);
      this.branches.circle(s.x1, s.y1, w1 / 2).fill(bark);
      this.branches.circle(x2, y2, w2 / 2).fill(bark);
      // a lit top edge on the thicker limbs
      if (w1 > 4) {
        this.branches.moveTo(s.x1 - nx * w1 * 0.3, s.y1 - ny * w1 * 0.3).lineTo(x2 - nx * w2 * 0.3, y2 - ny * w2 * 0.3)
          .stroke({ width: Math.max(0.8, w2 * 0.25), color: W.hi, alpha: W.edgeAlpha, cap: "round" });
      }
    }
    for (const sh of tree.shoots) {
      const f = clamp((g - sh.birth) / 0.08, 0, 1);
      if (f <= 0) continue;
      this.branches.moveTo(sh.x, sh.y);
      for (let i = 1; i <= 12; i++) this.branches.lineTo(...shootPoint(sh, (i / 12) * f));
      this.branches.stroke({ width: 1.5, color: bark, cap: "round", join: "round" });
    }
    this.drawTrunk(1 + 0.08 * Math.min(cc, 6), W);

    // foliage: a darker dome under each pad, then leaves lit from the top left
    const lush = lushness(g);
    const domes = [];
    for (const p of tree.pads) {
      const f = clamp((g - p.birth) / 0.12, 0, 1);
      if (f <= 0) continue;
      const R = p.size * lush * (0.45 + 0.55 * f);
      domes.push({ x: p.x, y: p.y + R * 0.02, rx: R * 0.86, ry: R * 0.4 });
    }
    const D = S.dome, domeTex = D.texture(this);
    this.pool(this.domeSprites, this.domes, domes.length, domeTex);
    this.domes.blendMode = val(D.blend, this);
    this.domes.alpha = val(D.alpha, this);
    const domeTint = leafColor(stops, g, D.dl);
    domes.forEach((d, i) => {
      const s = this.domeSprites[i];
      s.texture = domeTex;
      s.position.set(d.x, d.y);
      s.width = d.rx * 2 * D.mul;
      s.height = d.ry * 2 * D.mul;
      s.tint = domeTint;
      s.bx = d.x;
      s.by = d.y;
    });

    const leaves = leavesAt(tree, g).sort((a, b) => (a.pad < 0) - (b.pad < 0) || b.depth - a.depth);
    this.leaves = leaves;
    const L = S.leaf;
    this.pool(this.leafSprites, this.leafLayer, leaves.length, L.texture(this, 0));
    this.leafLayer.blendMode = val(L.blend, this);
    leaves.forEach((l, i) => {
      const s = this.leafSprites[i];
      s.texture = L.texture(this, i);
      s.position.set(l.x, l.y);
      s.rotation = l.rot;
      s.scale.set(...this.leafScale(s.texture, l.s));
      s.tint = L.tint(this, l, i);
      s.alpha = L.alpha(this, l, i);
      s.bx = l.x;
      s.by = l.y;
      s.brot = l.rot;
      s.ph = (i * 2.399) % TAU;
    });

    this.tally.clear();
    if (S.tally) S.tally(this, cc);
    else for (let i = 0; i < Math.min(cc, 12); i++) {
      const tx = 286 + (i % 6) * 6 - Math.min(cc, 6) * 3 + 3 + (i >= 6 ? 3 : 0);
      const ty = i >= 6 ? 424 : 416;
      this.tally.moveTo(tx, ty - 5).lineTo(tx, ty + 2).stroke({ width: 1.6, color: c.potHi, cap: "round" });
    }
    this.shadowDirty = true;
  }

  pool(list, parent, n, texture) {
    while (list.length < n) {
      const s = new Sprite(texture);
      s.anchor.set(0.5);
      parent.addChild(s);
      list.push(s);
    }
    list.forEach((s, i) => (s.visible = i < n));
  }

  // A smooth, tapered trunk with a root flare, shaded from a light at the top left.
  drawTrunk(thick, W) {
    const g = this.g, segs = this.tree.segs.filter((s) => s.trunk);
    const pts = [], ws = [];
    for (let i = 0; i < segs.length; i++) {
      const s = segs[i];
      const p = clamp((g - s.birth) / s.dur, 0, 1);
      if (p <= 0 && i > 0) break;
      const pp = i === 0 ? Math.max(p, 0.35) : p;
      if (!pts.length) { pts.push([s.x1, s.y1]); ws.push(s.w1); }
      pts.push([lerp(s.x1, s.x2, pp), lerp(s.y1, s.y2, pp)]);
      ws.push(lerp(s.w1, s.w2, pp));
      if (p < 1) break;
    }
    const wmul = thick * (0.55 + 0.45 * clamp(g / 0.5, 0, 1));
    const cr = (a, b, cc, e, t) => 0.5 * (2 * b + (cc - a) * t + (2 * a - 5 * b + 4 * cc - e) * t * t
      + (3 * b - a - 3 * cc + e) * t ** 3);
    const line = [];
    for (let i = 0; i < pts.length - 1; i++) {
      const p0 = pts[Math.max(0, i - 1)], p1 = pts[i], p2 = pts[i + 1], p3 = pts[Math.min(pts.length - 1, i + 2)];
      for (let k = 0; k < 8; k++) {
        const t = k / 8;
        line.push([cr(p0[0], p1[0], p2[0], p3[0], t), cr(p0[1], p1[1], p2[1], p3[1], t), lerp(ws[i], ws[i + 1], t)]);
      }
    }
    const last = pts[pts.length - 1];
    line.push([last[0], last[1], ws[ws.length - 1]]);
    const out = line.map(([x, y, w], j) => {
      const u = j / Math.max(1, line.length - 1);
      const flare = 1 + 1.15 * Math.max(0, 1 - u / 0.14) ** 2; // roots spreading into the soil
      return [x, y, Math.max(1.2, w * wmul * flare)];
    });
    const right = [], left = [], nrm = [];
    out.forEach(([x, y, w], j) => {
      const a = out[Math.max(0, j - 1)], b = out[Math.min(out.length - 1, j + 1)];
      const tx = b[0] - a[0], ty = b[1] - a[1], n = Math.hypot(tx, ty) || 1e-6;
      const nx = -ty / n, ny = tx / n;
      nrm.push([nx, ny]);
      right.push(x + nx * w / 2, y + ny * w / 2);
      left.push([x - nx * w / 2, y - ny * w / 2]);
    });
    const leftFlat = left.reverse().flat();
    const T = this.trunk.clear();
    T.poly([...right, ...leftFlat]).fill(W.bark);
    const along = (off) => out.map(([x, y, w], j) => [x + nrm[j][0] * w * off, y + nrm[j][1] * w * off]);
    const shaded = along(0.06).flat();
    const rightPairs = [];
    for (let j = right.length - 2; j >= 0; j -= 2) rightPairs.push(right[j], right[j + 1]);
    T.poly([...shaded, ...rightPairs]).fill(mix(0x000000, W.bark, W.shade));
    const litA = along(-0.36).flat(), litB = along(-0.16);
    T.poly([...litA, ...litB.reverse().flat()]).fill({ color: W.hi, alpha: W.hiAlpha });
    // bark texture: broken lines running along the trunk (or, in ink, the paper showing through)
    const fissure = W.fissure != null ? mix(0x000000, W.bark, W.fissure) : W.fissureColor;
    const fissureAlpha = W.fissure != null ? 1 : W.fissureAlpha;
    for (const [off, start] of [[0.1, 2], [0.3, 5], [-0.05, 9]]) {
      for (let j = start; j < out.length - 3; j += 9) {
        const run = out.slice(j, j + 4).map(([x, y, w], m) => [x + nrm[j + m][0] * w * off, y + nrm[j + m][1] * w * off]);
        T.moveTo(...run[0]);
        run.slice(1).forEach((q) => T.lineTo(...q));
        T.stroke({ width: 0.9, color: fissure, alpha: fissureAlpha, cap: "round" });
      }
    }
    const [ex, ey, ew] = out[out.length - 1];
    T.circle(ex, ey, ew / 2).fill(W.bark);
  }

  // A soft shadow of the tree on the wall, down and to the right. Baked to a texture, refreshed when the tree changes.
  bakeShadow() {
    if (!this.S.shadow) {
      this.shadow.visible = false;
      return;
    }
    const r = this.app.renderer;
    const b = this.treeInner.getLocalBounds();
    if (b.width < 1 || b.height < 1) {
      this.shadow.visible = false;
      return;
    }
    const res = Math.max(0.25, this.k * 0.6);
    const src = r.generateTexture({ target: this.treeInner, resolution: res });
    const pad = 24;
    const holder = new Container();
    const sil = new Sprite(src);
    sil.position.set(b.x, b.y);
    sil.tint = this.theme.light ? 0x0c100e : 0x000000;
    sil.filters = [new BlurFilter({ strength: 7 * res, quality: 3 })];
    holder.addChild(sil);
    const baked = r.generateTexture({
      target: holder, resolution: res, frame: new Rectangle(b.x - pad, b.y - pad, b.width + pad * 2, b.height + pad * 2),
    });
    const old = this.shadow.texture;
    this.shadow.texture = baked;
    // free the old textures once this frame no longer has them bound
    requestAnimationFrame(() => {
      holder.destroy({ children: true });
      src.destroy(true);
      if (old && old !== baked && old !== Texture.EMPTY) old.destroy(true);
    });
    this.shadow.position.set(b.x - pad + 10, b.y - pad + 7);
    this.shadow.alpha = this.theme.light ? 0.2 : 0.42;
    this.shadow.visible = true;
  }

  setPile(pile) {
    this.pile = pile;
    this.pileLayer.removeChildren().forEach((c) => c.destroy());
    this.pileLayer.blendMode = val(this.S.leaf.blend, this);
    pile.forEach((l, i) => {
      const s = new Sprite(this.S.leaf.texture(this, i));
      s.anchor.set(0.5);
      s.position.set(l.x, l.y);
      s.rotation = l.rot;
      s.scale.set(...this.leafScale(s.texture, l.s));
      s.tint = leafColor(this.theme.stops, 0.82 + l.hue * 0.2);
      s.alpha = 0.9;
      this.pileLayer.addChild(s);
    });
  }

  // --- tools for compaction: pruning shears and a watering can ---
  makeTools() {
    this.tools.removeChildren().forEach((c) => c.destroy({ children: true }));
    const c = this.theme.colors;
    const steel = this.theme.light ? 0x8a9398 : 0xc9d1d6;
    const blade = () => new Graphics()
      .poly([0, -1.6, -34, 3.5, -36, 5, -30, 5.5, 0, 2.2]).fill(steel)
      .moveTo(-2, -0.6).lineTo(-30, 4).stroke({ width: 0.6, color: 0xffffff, alpha: 0.6 });
    const handle = () => new Graphics()
      .moveTo(0, 0).bezierCurveTo(10, -2, 22, -8, 30, -6).stroke({ width: 4.5, color: c.crit, cap: "round" })
      .circle(30, -6, 3.2).fill(shadeHex(c.crit, 0.75));
    this.shears = new Container();
    this.bladeA = new Container();
    this.bladeB = new Container();
    this.bladeA.addChild(blade(), handle());
    this.bladeB.addChild(blade(), handle());
    this.bladeB.scale.y = -1;
    this.shears.addChild(this.bladeA, this.bladeB, new Graphics().circle(0, 0, 2.2).fill(0x444444));
    this.shears.rotation = -0.65;
    this.shears.alpha = 0;
    this.shearState = { x: 470, y: 110, tx: 470, ty: 110, next: 0, snipAt: null, snap: 0, i: 0, edge: [] };

    this.can = new Container();
    const body = new Graphics()
      .roundRect(-16, -14, 34, 28, 6).fill(c.pot)
      .roundRect(-16, -14, 34, 6, 3).fill(c.potHi)
      .poly([-14, 6, -60, -22, -62, -18, -16, 12]).fill(c.potDark) // spout
      .ellipse(-61, -21, 4, 2.4).fill(c.potHi)
      .moveTo(14, -10).bezierCurveTo(32, -18, 32, 14, 14, 8).stroke({ width: 3, color: c.potDark });
    this.can.addChild(body);
    this.can.alpha = 0;
    this.tools.addChild(this.shears, this.can);
    this.canAt = -1e9;
  }

  makeShafts() {
    this.shafts = [];
    if (this.detail !== "full") return;
    for (let i = 0; i < 3; i++) {
      const s = new Sprite(this.tex.shaft);
      s.anchor.set(0.5, 0);
      s.position.set(60 + i * 70, this.crop[1] - 20);
      s.rotation = -0.62 + i * 0.07;
      s.scale.set(1.2 + i * 0.5, 2.6);
      s.alpha = 0;
      s.ph = i * 1.7;
      this.glow.addChild(s);
      this.shafts.push(s);
    }
  }

  // --- particles ---
  spawnLeaf(x, y, s, rot, color, burst) {
    const sp = new Sprite(this.S.leaf.texture(this, Math.floor(Math.random() * 4)));
    sp.anchor.set(0.5);
    sp.tint = color;
    sp.blendMode = val(this.S.leaf.blend, this);
    const [kx, ky] = this.leafScale(sp.texture, s);
    sp.scale.set(kx, ky);
    this.fx.addChild(sp);
    this.particles.push({
      kind: "leaf", sp, x, y, rot, s, ky, life: 1, landed: false,
      vx: (Math.random() - 0.5) * (burst ? 1.6 : 0.5), vy: burst ? -Math.random() * 1.2 : 0,
      vr: (Math.random() - 0.5) * 0.15, sway: Math.random() * TAU,
    });
  }

  spawn(kind, props, texture, layer, tint) {
    const sp = new Sprite(texture);
    sp.anchor.set(0.5);
    if (tint != null) sp.tint = tint;
    sp.visible = false;
    layer.addChild(sp);
    const p = { kind, sp, life: 1, wait: 0, ...props };
    this.particles.push(p);
    return p;
  }

  // Compaction: leaves grown after the baseline fall, and a pile settles on the stand.
  prune(frm, to, seed) {
    const falling = leavesAt(this.tree, frm).filter((l) => l.birth > BASELINE);
    for (let i = falling.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [falling[i], falling[j]] = [falling[j], falling[i]];
    }
    for (const l of falling.slice(0, 130)) {
      this.spawnLeaf(l.x, l.y, l.s, l.rot, leafColor(this.theme.stops, l.cg), true);
    }
    this.setPile(makePile(Math.max(0, frm - to) * 110, seed));
  }

  // Rehydrate: a watering can tips in and pours onto the soil, ripples spread, then buds open.
  water(nextG) {
    this.canAt = performance.now();
    const potHi = this.C("potHi");
    for (let i = 0; i < 30; i++) {
      this.spawn("pour", { x: null, y: null, vx: -(0.15 + Math.random() * 0.08), vy: Math.random() * 0.03,
        wait: 450 + i * 55 }, this.tex.disc, this.fx, mix(potHi, 0xffffff, 0.35));
    }
    const buds = leavesAt(this.tree, Math.min(1, nextG)).sort(() => Math.random() - 0.5).slice(0, 26);
    buds.forEach((l, i) => {
      this.spawn("bud", { x: l.x, y: l.y, wait: 1300 + i * 55, cg: l.cg }, this.tex.disc, this.fx,
        leafColor(this.theme.stops, l.cg, 12));
      this.spawn("spark", { x: l.x, y: l.y, wait: 1300 + i * 55 }, this.tex.glow, this.glow, hex(this.theme.colors.glow));
    });
  }

  spout() {
    const t = (performance.now() - this.canAt) / 1000;
    let tilt;
    if (t < 0.4) tilt = -0.6 * (1 - (1 - t / 0.4) ** 2);
    else if (t < 2.5) tilt = -0.6;
    else tilt = -0.6 * Math.max(0, 1 - (t - 2.5) / 0.5);
    const px = 482, py = this.crop[1] + 46;
    const sx = -62, sy = -20;
    return { px, py, tilt, tip: [px + sx * Math.cos(tilt) - sy * Math.sin(tilt), py + sx * Math.sin(tilt) + sy * Math.cos(tilt)] };
  }

  // Outer leaves from left to right over the top, for the shears to work along.
  canopyEdge() {
    const pool = this.leaves;
    if (!pool.length) return [];
    const cx = pool.reduce((a, l) => a + l.x, 0) / pool.length;
    const cy = pool.reduce((a, l) => a + l.y, 0) / pool.length;
    const far = new Map();
    for (const l of pool) {
      let a = Math.atan2(l.y - cy, l.x - cx);
      if (a > Math.PI - 0.35) a -= TAU;
      if (a > 0.35) continue;
      const b = Math.floor((a + Math.PI + 0.35) * 8);
      const d2 = (l.x - cx) ** 2 + (l.y - cy) ** 2;
      if (!far.has(b) || far.get(b).d2 < d2) far.set(b, { ...l, d2 });
    }
    return [...far.keys()].sort((a, b) => a - b).map((k) => far.get(k));
  }

  // --- per frame ---
  // ctx: { dt (ms), working, sleeping, night, ambient, phase, sky: { color, alpha } }
  update(ctx) {
    const dt = Math.min(ctx.dt, 50);
    this.time += dt / 1000;
    const t = this.time;
    const key = `${this.g.toFixed(3)}|${this.cc}|${this.theme.key}`;
    if (key !== this.builtKey) {
      this.builtKey = key;
      if (this.treeRoot.isCachedAsTexture) this.treeRoot.cacheAsTexture(false);
      this.rebuild();
    }
    const now = performance.now();
    if (this.shadowDirty && now - this.shadowAt > 140) {
      this.shadowDirty = false;
      this.shadowAt = now;
      this.bakeShadow();
    }

    // wind: a breeze while Claude works, a whisper while it waits, still at night
    const target = !ctx.ambient ? 0 : ctx.sleeping ? 0.08 : ctx.working ? 1 : 0.28;
    this.wind += (target - this.wind) * Math.min(1, dt / 900);
    const gust = 0.65 + 0.35 * Math.sin(t * 0.63) * Math.sin(t * 1.37 + 1.1);
    const w = this.wind * gust * this.S.wind;
    this.S.animate?.(this, t, dt);
    // a still tree is baked into one texture until the wind picks up or it grows
    const still = target === 0 && this.wind < 0.004;
    if (still !== this.still) {
      this.still = still;
      if (!still) this.treeRoot.cacheAsTexture(false);
    }
    if (still) {
      if (!this.treeRoot.isCachedAsTexture) {
        this.treeRoot.skew.x = 0;
        for (const s of this.leafSprites) { s.x = s.bx; s.rotation = s.brot; }
        for (const s of this.domeSprites) s.x = s.bx;
        this.treeRoot.cacheAsTexture({ resolution: Math.max(1, this.k * devicePixelRatio) });
      }
      this.shadow.skew.x = 0;
    } else this.swayTree(t, w);
    this.updateShafts(ctx, dt, t);
    this.updateSky(ctx, dt);
    this.updateAmbient(ctx, dt);
    this.updateTools(ctx, dt, now);
    this.updateParticles(dt, now);
  }

  swayTree(t, w) {
    this.treeRoot.skew.x = -0.012 * w * (0.6 + 0.4 * Math.sin(t * 1.1));
    for (const s of this.leafSprites) {
      if (!s.visible) continue;
      const height = clamp((398 - s.by) / 260, 0, 1.2);
      const drift = 2.6 * Math.sin(t * 1.9 + s.bx * 0.025 + s.by * 0.02) * height * w;
      const flutter = Math.sin(t * 7.3 + s.ph) * 0.09 * w;
      s.x = s.bx + drift;
      s.rotation = s.brot + drift * 0.06 + flutter;
    }
    for (const s of this.domeSprites) {
      if (!s.visible) continue;
      s.x = s.bx + 1.6 * Math.sin(t * 1.9 + s.bx * 0.025 + s.by * 0.02) * clamp((398 - s.by) / 260, 0, 1.2) * w;
    }
    this.shadow.skew.x = this.treeRoot.skew.x * 0.8;
  }

  updateShafts(ctx, dt, t) {
    // light shafts drift in while working by day
    for (const s of this.shafts) {
      const want = this.S.shafts && ctx.ambient && !ctx.night ? (ctx.working ? 0.07 : 0.035) : 0;
      s.alpha += (want * (0.7 + 0.3 * Math.sin(t * 0.5 + s.ph)) - s.alpha) * Math.min(1, dt / 600);
      s.tint = hex(this.theme.colors.glow);
    }
  }

  updateSky(ctx, dt) {
    // sky: the clock's tint over the scene, deeper when the session sleeps
    const sky = ctx.sky || { color: 0xffffff, alpha: 0 };
    this.skyTint.alpha += (sky.alpha - this.skyTint.alpha) * Math.min(1, dt / 1500);
    this.skyTint.color = sky.color;
    this.sky.tint = this.skyTint.color;
    this.sky.alpha = this.skyTint.alpha;
  }

  updateAmbient(ctx, dt) {
    if (this.detail !== "full") return;
    const now = performance.now();
    if (this.S.motes && ctx.ambient && ctx.working && this.phase === "idle" && now >= (this.nextMote || 0)) { // motes
      this.nextMote = now + 220 + Math.random() * 260;
      this.spawn("mote", { x: this.crop[0] - 4, y: lerp(this.crop[1] + 60, 380, Math.random()),
        vx: 0.04 + Math.random() * 0.05, ph: Math.random() * TAU, size: 0.05 + Math.random() * 0.06 },
      this.tex.glow, this.glow, hex(this.theme.colors.glow));
    }
    const flies = this.particles.filter((p) => p.kind === "fly");
    if (ctx.ambient && ctx.sleeping && flies.length < 9) {
      this.spawn("fly", { x: lerp(160, 440, Math.random()), y: lerp(140, 380, Math.random()), vx: 0, vy: 0,
        ph: Math.random() * TAU, fade: 0 }, this.tex.glow, this.glow, hex(this.theme.colors.warn));
    }
    // while waiting on you, an occasional single leaf lets go
    if (ctx.ambient && !ctx.working && !ctx.sleeping && this.phase === "idle" && this.g > 0.2
      && now >= (this.nextLeaf ??= now + 6000)) {
      this.nextLeaf = now + 9000 + Math.random() * 8000;
      const l = this.leaves[Math.floor(Math.random() * this.leaves.length)];
      if (l) this.spawnLeaf(l.x, l.y, l.s, l.rot, leafColor(this.theme.stops, l.cg), false);
    }
    // dropping leaves: past 90% the tree sheds on its own
    if (this.phase === "idle" && this.g > 0.9 && now >= (this.nextShed || 0)) {
      this.nextShed = now + 600;
      const pool = this.leaves.filter((l) => l.cg > 0.93);
      const l = pool[Math.floor(Math.random() * pool.length)];
      if (l) this.spawnLeaf(l.x, l.y, l.s, l.rot, leafColor(this.theme.stops, l.cg), false);
    }
  }

  updateTools(ctx, dt, now) {
    const sh = this.shearState;
    const on = this.phase === "compacting";
    this.shears.alpha += ((on ? 1 : 0) - this.shears.alpha) * Math.min(1, dt / 250);
    if (on) {
      if (now >= sh.next) {
        if (!sh.edge.length) { sh.edge = this.canopyEdge(); sh.i = 0; }
        if (sh.edge.length) { // work along the canopy edge, left to right over the top
          const l = sh.edge[sh.i % sh.edge.length];
          sh.i += 2;
          sh.tx = l.x + 30;
          sh.ty = l.y - 24;
        }
        sh.next = now + 1100;
        sh.snipAt = now + 600;
      }
      if (sh.snipAt && now >= sh.snipAt) {
        sh.snipAt = null;
        sh.snap = now;
        const pool = this.leaves;
        for (let i = 0; i < Math.min(3, pool.length); i++) {
          const l = pool[Math.floor(Math.random() * pool.length)];
          this.spawnLeaf(sh.tx - 30 + (Math.random() - 0.5) * 10, sh.ty + 24 + (Math.random() - 0.5) * 8, l.s, l.rot,
            leafColor(this.theme.stops, l.cg), true);
        }
      }
    } else {
      sh.edge = [];
      sh.tx = 470;
      sh.ty = 110 + Math.sin(now / 500) * 4;
    }
    const ease = 1 - Math.pow(0.8, dt / 16);
    sh.x += (sh.tx - sh.x) * ease;
    sh.y += (sh.ty - sh.y) * ease;
    const since = (now - sh.snap) / 1000;
    const open = since < 0.12 ? lerp(0.42, 0.02, since / 0.12) : since < 0.45 ? lerp(0.02, 0.42, (since - 0.12) / 0.33) : 0.42;
    this.bladeA.rotation = -open / 2;
    this.bladeB.rotation = open / 2;
    this.shears.position.set(sh.x, sh.y);

    const sinceCan = (now - this.canAt) / 1000;
    const canOn = sinceCan < 3.2;
    this.can.alpha += ((canOn ? 1 : 0) - this.can.alpha) * Math.min(1, dt / 220);
    if (this.can.alpha > 0.01) {
      const s = this.spout();
      this.can.position.set(s.px, s.py);
      this.can.rotation = s.tilt;
    }
  }

  updateParticles(dt, now) {
    const f = dt / 16;
    for (const p of this.particles) {
      if (p.wait > 0) {
        p.wait -= dt;
        continue;
      }
      const sp = p.sp;
      sp.visible = true;
      switch (p.kind) {
        case "leaf":
          if (!p.landed) {
            const fall = this.S.fall;
            p.vy = Math.min(1.6 * fall, p.vy + 0.035 * f * fall);
            p.sway += 0.05 * f;
            p.x += (p.vx + Math.sin(p.sway) * 0.5 + this.wind * 0.25) * f;
            p.y += p.vy * f;
            p.rot += p.vr * f;
            const floor = p.x > 116 && p.x < 484 ? 437 : 451;
            if (p.y >= floor) { p.y = floor; p.landed = true; }
          } else p.life -= dt / 1600;
          sp.position.set(p.x, p.y);
          sp.rotation = p.rot;
          sp.scale.y = p.ky * (0.15 + 0.85 * Math.abs(Math.cos(p.sway * 0.8))); // tumbling
          sp.alpha = Math.min(1, p.life * 2);
          break;
        case "mote":
          p.x += p.vx * dt;
          p.y += Math.sin(p.ph + p.x * 0.03) * 0.012 * dt;
          if (p.x > this.crop[2] + 4) p.life = 0;
          sp.position.set(p.x, p.y);
          sp.scale.set(p.size);
          sp.alpha = 0.55 * Math.min(1, (p.x - this.crop[0]) / 40);
          break;
        case "fly": { // fireflies wander and fade out once the session wakes
          p.vx = clamp(p.vx + (Math.random() - 0.5) * 0.004 * dt, -0.03, 0.03);
          p.vy = clamp(p.vy + (Math.random() - 0.5) * 0.004 * dt, -0.03, 0.03);
          p.x += p.vx * dt;
          p.y += p.vy * dt;
          if (p.x < 130 || p.x > 470) p.vx = -p.vx;
          if (p.y < 110 || p.y > 390) p.vy = -p.vy;
          p.fade = Math.min(1, p.fade + dt / 1200);
          if (this.wind > 0.15 || this.phase !== "idle") p.life -= dt / 1500;
          const pulse = 0.5 + 0.5 * Math.sin(now / 420 + p.ph);
          sp.position.set(p.x, p.y);
          sp.scale.set(0.09 + pulse * 0.05);
          sp.alpha = p.fade * Math.min(1, p.life) * (0.35 + 0.65 * pulse);
          break;
        }
        case "pour":
          if (p.x == null) [p.x, p.y] = this.spout().tip;
          p.vy += 0.00145 * dt;
          p.x += p.vx * dt;
          p.y += p.vy * dt;
          if (p.y >= 395) {
            p.life = 0;
            this.spawn("ripple", { x: p.x, y: 396 }, this.tex.ring, this.fx, this.C("potHi"));
          }
          sp.position.set(p.x, p.y);
          sp.scale.set(0.045, 0.07);
          break;
        case "ripple":
          p.life -= dt / 650;
          sp.position.set(p.x, p.y);
          sp.scale.set(0.05 + (1 - p.life) * 0.22, (0.05 + (1 - p.life) * 0.22) * 0.3);
          sp.alpha = p.life;
          break;
        case "bud":
          p.life -= dt / 1100;
          sp.position.set(p.x, p.y);
          sp.scale.set(Math.sin(Math.min(1, (1 - p.life) * 2) * Math.PI / 2) * 0.09);
          sp.alpha = Math.min(1, p.life * 2.5);
          break;
        case "spark":
          p.life -= dt / 700;
          sp.position.set(p.x, p.y);
          sp.scale.set(0.15 * (1 - p.life) + 0.04);
          sp.alpha = p.life * 0.8;
          break;
      }
    }
    const keep = [];
    for (const p of this.particles) {
      if (p.life > 0) keep.push(p);
      else p.sp.destroy();
    }
    this.particles = keep;
  }

  get moving() {
    return !this.still || this.particles.length > 0;
  }

  get busy() {
    return this.particles.length > 0 || this.phase !== "idle" || this.can.alpha > 0.01 || this.shears.alpha > 0.01;
  }
}
