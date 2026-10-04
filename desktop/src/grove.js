// The grove: one living tree per active session, as a carousel. Drag or flick it (with momentum),
// scroll the wheel, use the arrows or dots. Each card keeps its project's theme.
import { Container, Graphics, Rectangle } from "pixi.js";
import { CROPS, Diorama } from "./diorama.js";
import { fmtAgo, nowSec } from "./format.js";
import { clamp, stageFor, treeFor } from "./tree.js";
import { styleOf } from "./styles.js";
import { Button, C, DISPLAY, MONO, ease, fit, label, recolor, tween } from "./ui.js";

const CARD_W = 124, GAP = 10, PER = 4;
const SCENE_H = Math.round(((CROPS.grove[3] - CROPS.grove[1]) * CARD_W) / (CROPS.grove[2] - CROPS.grove[0]));

class Card extends Container {
  constructor(app, view, path) {
    super();
    this.path = path;
    this.view = view;
    this.lift = 0;
    this.g = null;
    this.glowRing = new Graphics();
    this.tile = new Graphics(); // a pane behind the card, for styles that use them
    this.bg = new Graphics();
    this.scene = new Diorama(app, { width: CARD_W, crop: CROPS.grove, theme: view.ctrl.themeFor(null), tree: treeFor(""),
      detail: "lite" });
    this.sceneMask = new Graphics().roundRect(0, 0, CARD_W, SCENE_H, 8).fill(0xffffff);
    this.sceneWrap = new Container();
    this.sceneWrap.addChild(this.scene, this.sceneMask);
    this.sceneWrap.mask = this.sceneMask;
    this.title = label("", 12, 0xffffff, { weight: "600" });
    this.proj = label("", 10, 0xffffff, { family: MONO });
    this.pct = label("", 19, 0xffffff, { weight: "600", family: DISPLAY });
    this.meter = new Graphics();
    this.status = label("", 10, 0xffffff, { family: MONO });
    this.info = new Container();
    this.info.addChild(this.title, this.proj, this.pct, this.meter, this.status);
    this.addChild(this.tile, this.glowRing, this.bg, this.sceneWrap, this.info);
    this.eventMode = "static";
    this.cursor = "pointer";
    this.on("pointerover", () => { view.hover = path; tween(this, { lift: 1 }, 180); });
    this.on("pointerout", () => { if (view.hover === path) view.hover = null; tween(this, { lift: 0 }, 260); });
  }

  layout(s, theme, zen) {
    const col = C(theme);
    this.col = col;
    this.s = s;
    this.scene.setTheme(theme);
    this.scene.setTree(treeFor(s.id));
    this.scene.cc = s.compactions;
    this.info.visible = !zen;
    const cx = CARD_W / 2;
    const center = (t, y) => t.position.set(cx - t.width / 2, y);
    let y = SCENE_H + 8;
    recolor(this.title, col.ink);
    fit(this.title, s.title || s.name, CARD_W);
    center(this.title, y);
    y += 17;
    recolor(this.proj, col.muted);
    fit(this.proj, s.title && s.title !== s.name ? s.name : "", CARD_W);
    center(this.proj, y);
    y += 15;
    this.pctY = y;
    y += 26;
    this.meterY = y;
    y += 10;
    const status = fmtAgo(s.mtime ? nowSec() - s.mtime : 9e9);
    recolor(this.status, status === "live" ? col.ok : col.muted);
    fit(this.status, status);
    center(this.status, y);
    this.h = zen ? SCENE_H : y + 14;
    const S = styleOf(theme);
    if (this.pct.style.fontFamily !== S.display) this.pct.style.fontFamily = S.display;
    this.tile.clear();
    if (!zen) S.cardTile?.(this.tile, CARD_W, this.h, theme);
    this.hitArea = new Rectangle(-5, -5, CARD_W + 10, this.h + 10);
  }

  update(ctx, parallax) {
    const s = this.s, col = this.col;
    if (!s) return;
    this.g = this.g == null ? s.g : this.g + (s.g - this.g) * Math.min(1, ctx.dt / 400);
    this.scene.g = this.g;
    this.scene.world.x = -CROPS.grove[0] * this.scene.k + parallax * 6; // depth while the carousel moves
    const age = nowSec() - (s.mtime || 0); // each tree sways only while its own session works
    this.scene.update({ ...ctx, working: age < 8, sleeping: age > 1800 });
    fit(this.pct, `${Math.round(this.g * 100)}%`);
    recolor(this.pct, col.ink);
    this.pct.position.set(CARD_W / 2 - this.pct.width / 2, this.pctY);
    const [, state] = stageFor(this.g);
    const mkey = `${Math.round(this.g * 400)}|${state}|${col.line}|${this.meterY}`;
    if (mkey !== this.mkey) { // redraw geometry only when it changes
      this.mkey = mkey;
      this.meter.clear().roundRect(0, this.meterY, CARD_W, 4, 2).fill(col.line)
        .roundRect(0, this.meterY, Math.max(4, CARD_W * clamp(this.g, 0, 1)), 4, 2).fill(col[state]);
    }
    // hover: the card lifts and catches the light
    this.sceneWrap.y = -3 * this.lift;
    const hkey = `${Math.round(this.lift * 40)}|${state}|${this.h}|${col.line}`;
    if (hkey === this.hkey) return;
    this.hkey = hkey;
    this.bg.clear();
    if (this.lift > 0.01) {
      this.bg.roundRect(-5, -5 - 3 * this.lift, CARD_W + 10, this.h + 10, 10).fill({ color: col.line, alpha: 0.55 * this.lift });
      this.glowRing.clear().roundRect(-1, -1 - 3 * this.lift, CARD_W + 2, SCENE_H + 2, 9)
        .stroke({ width: 2, color: col[state], alpha: 0.6 * this.lift });
    } else this.glowRing.clear();
  }
}

export class GroveView extends Container {
  constructor(app, ctrl) {
    super();
    this.app = app;
    this.ctrl = ctrl;
    this.pad = 16;
    this.zen = false;
    this.cards = new Map();
    this.scroll = 0; // in cards
    this.target = 0;
    this.vel = 0;
    this.hover = null;
    this.drag = null;

    this.panelFx = new Container();
    this.panel = new Graphics();
    this.title = label("Grove", 15, 0xffffff, { weight: "600", family: DISPLAY });
    this.count = label("", 10.5, 0xffffff, { family: MONO });
    this.prev = new Button("‹", { onTap: () => this.page(-1), size: 14, padX: 8, h: 22 });
    this.next = new Button("›", { onTap: () => this.page(1), size: 14, padX: 8, h: 22 });
    this.header = new Container();
    this.header.addChild(this.title, this.count, this.prev, this.next);
    this.viewport = new Container();
    this.strip = new Container();
    this.clip = new Graphics();
    this.viewport.addChild(this.strip, this.clip);
    this.viewport.mask = this.clip;
    this.footer = new Container();
    this.dots = new Graphics();
    this.hint = label("Click a tree to open it · drag to browse", 11, 0xffffff);
    this.footer.addChild(this.dots, this.hint);
    this.zenTag = new Container();
    this.zenTagBg = new Graphics();
    this.zenTagTxt = label("", 11, 0xffffff);
    this.zenTag.addChild(this.zenTagBg, this.zenTagTxt);
    this.addChild(this.panelFx, this.panel, this.header, this.viewport, this.footer, this.zenTag);

    this.viewport.eventMode = "static";
    this.viewport.on("pointerdown", (e) => this.down(e));
    this.viewport.on("globalpointermove", (e) => this.move(e));
    this.viewport.on("pointerup", (e) => this.up(e));
    this.viewport.on("pointerupoutside", (e) => this.up(e));
    this.viewport.on("wheel", (e) => this.page(e.deltaY > 0 || e.deltaX > 0 ? 1 : -1));
    this.dots.eventMode = "static";
    this.dots.cursor = "pointer";
    this.dots.isUi = true;
    this.dots.on("pointertap", (e) => {
      const p = this.dots.toLocal(e.global);
      const k = Math.round((p.x - this.dotsX0) / 16);
      if (k >= 0 && k < this.pages) this.goTo(k * this.per);
    });
  }

  order() {
    return this.ctrl.order;
  }

  get motion() {
    let m = this.panelMoving ? 1 : 0;
    for (const c of this.cards.values()) if (c.visible) m = Math.max(m, c.scene.motion);
    return m;
  }

  get n() {
    return this.ctrl.order.length;
  }

  get per() {
    return Math.min(this.n, PER);
  }

  get last() {
    return Math.max(0, this.n - this.per);
  }

  get pages() {
    return Math.ceil(this.n / Math.max(1, this.per));
  }

  goTo(first) {
    this.target = clamp(first, 0, this.last);
  }

  // A page left or right, wrapping around at either end.
  page(step) {
    if (this.n <= this.per) return;
    const first = Math.round(this.target);
    if (step > 0) this.goTo(first >= this.last ? 0 : first + this.per);
    else this.goTo(first <= 0 ? this.last : first - this.per);
  }

  // Show the page holding this session.
  reveal(path) {
    const i = this.ctrl.order.indexOf(path);
    if (i < 0) return;
    const first = clamp(Math.floor(i / this.per) * this.per, 0, this.last);
    this.scroll = this.target = first;
  }

  down(e) {
    this.drag = { x0: e.global.x, s0: this.scroll, moved: false, t: performance.now(), lastX: e.global.x, v: 0 };
  }

  move(e) {
    const d = this.drag;
    if (!d) return;
    const dx = e.global.x - d.x0;
    if (Math.abs(dx) > 4) d.moved = true;
    if (!d.moved) return;
    const now = performance.now();
    const step = CARD_W + GAP;
    let s = d.s0 - dx / step;
    if (s < 0) s *= 0.35; // rubber band past the ends
    if (s > this.last) s = this.last + (s - this.last) * 0.35;
    d.v = ((d.lastX - e.global.x) / step) / Math.max(1, now - d.t) * 1000; // cards per second
    d.lastX = e.global.x;
    d.t = now;
    this.scroll = this.target = s;
  }

  up(e) {
    const d = this.drag;
    this.drag = null;
    if (!d) return;
    if (d.moved) { // flick: carry on with the release velocity, then settle on a card
      this.target = clamp(Math.round(this.scroll + clamp(d.v, -12, 12) * 0.22), 0, this.last);
      return;
    }
    const p = this.strip.toLocal(e.global);
    const i = Math.floor((p.x + GAP / 2) / (CARD_W + GAP));
    const path = this.ctrl.order[i];
    if (path) this.ctrl.openFocus(path, this.cards.get(path));
  }

  layout() {
    const ctrl = this.ctrl, theme = ctrl.widgetTheme(), col = C(theme), pad = this.pad;
    const order = ctrl.order, per = this.per;
    this.col = col;
    for (const [p, card] of this.cards) {
      if (!order.includes(p)) {
        card.destroy({ children: true });
        this.cards.delete(p);
      }
    }
    order.forEach((p, i) => {
      let card = this.cards.get(p);
      if (!card) {
        card = new Card(this.app, this, p);
        this.cards.set(p, card);
        this.strip.addChild(card);
      }
      card.x = i * (CARD_W + GAP);
      card.layout(ctrl.sessions.get(p), ctrl.themeFor(ctrl.sessions.get(p)), this.zen);
    });
    this.target = clamp(this.target, 0, this.last);
    this.scroll = clamp(this.scroll, -0.5, this.last + 0.5);
    const zen = this.zen;
    const vw = per * CARD_W + (per - 1) * GAP;
    const W = (zen ? 12 : pad * 2) + vw;
    const cardH = Math.max(...[...this.cards.values()].map((c) => c.h), SCENE_H);
    this.header.visible = this.footer.visible = !zen;
    let y;
    if (zen) {
      this.viewport.position.set(6, 6);
      y = 6 + cardH + 6;
    } else {
      this.title.style.fill = col.ink;
      this.title.position.set(pad, pad - 2);
      const paged = this.n > per;
      this.prev.visible = this.next.visible = paged;
      for (const b of [this.prev, this.next]) b.style({ fg: col.muted, accent: col.muted, panel: col.panel });
      this.next.position.set(W - pad - this.next.w / 2, pad + 9);
      this.prev.position.set(this.next.x - this.next.w / 2 - 4 - this.prev.w / 2, pad + 9);
      this.prev.draw();
      this.next.draw();
      recolor(this.count, col.muted);
      this.viewport.position.set(pad, pad + 34);
      y = pad + 34 + cardH + 10;
      this.footer.position.set(0, y);
      this.hint.visible = !paged;
      recolor(this.hint, col.muted);
      this.hint.position.set(W / 2 - this.hint.width / 2, 0);
      y += 16 + pad - 4;
    }
    this.clip.clear().rect(-6, -8, vw + 12, cardH + 16).fill(0xffffff);
    this.viewport.hitArea = new Rectangle(-6, -8, vw + 12, cardH + 16);
    this.W = W;
    this.h = y;
    this.S = styleOf(theme);
    if (this.title.style.fontFamily !== this.S.display) this.title.style.fontFamily = this.S.display;
    const key = `${theme.key}|${W}|${y}`;
    if (key !== this.panelKey) { // Windows rounds the window's corners
      this.panelKey = key;
      this.S.panel(this, { W, h: y, col, theme });
    }
    return { w: W, h: y };
  }

  // Cards pop in one after another.
  enter() {
    [...this.cards.values()].forEach((c, i) => {
      const vis = i - Math.round(this.scroll);
      c.alpha = 0;
      c.scale.set(0.92);
      c.pivot.set(0, 0);
      tween(c, { alpha: 1 }, 320, { delay: 40 + Math.max(0, vis) * 55 });
      tween(c.scale, { x: 1, y: 1 }, 420, { delay: 40 + Math.max(0, vis) * 55, fn: ease.back });
    });
    this.header.alpha = 0;
    tween(this.header, { alpha: 1 }, 300);
  }

  // The chosen tree swells while the others fall back; resolves when it's time to switch views.
  async zoomInto(path) {
    const jobs = [];
    for (const [p, c] of this.cards) {
      if (p === path) {
        jobs.push(tween(c.scale, { x: 1.08, y: 1.08 }, 220, { fn: ease.out }));
        jobs.push(tween(c, { lift: 1 }, 160));
      } else jobs.push(tween(c, { alpha: 0.15 }, 200));
    }
    jobs.push(tween(this.header, { alpha: 0 }, 160), tween(this.footer, { alpha: 0 }, 160));
    await Promise.all(jobs);
  }

  update(ctx) {
    const dt = Math.min(ctx.dt, 50) / 1000;
    const anyWorking = this.order().some((p) => nowSec() - (this.ctrl.sessions.get(p)?.mtime || 0) < 8);
    this.panelMoving = !!this.S?.animatesPanel && ctx.ambient && (anyWorking || ctx.hovering);
    if (this.panelMoving) this.S.animatePanel(this, performance.now() / 1000);
    if (!this.drag) { // a critically damped spring toward the target card
      const k = 90, c = 2 * Math.sqrt(k);
      this.vel += (k * (this.target - this.scroll) - c * this.vel) * dt;
      this.scroll += this.vel * dt;
      if (Math.abs(this.target - this.scroll) < 0.0005 && Math.abs(this.vel) < 0.001) {
        this.scroll = this.target;
        this.vel = 0;
      }
    } else this.vel = 0;
    const step = CARD_W + GAP;
    this.strip.x = -this.scroll * step;
    const vw = this.per * step;
    for (const [, card] of this.cards) {
      const sx = card.x + this.strip.x;
      const on = sx + CARD_W > -10 && sx < vw + 10;
      card.visible = on;
      if (!on) continue;
      const parallax = clamp((sx + CARD_W / 2 - vw / 2) / vw, -1, 1);
      card.update(ctx, -parallax);
    }
    const col = this.col;
    if (!col) return;
    if (!this.zen) {
      const first = clamp(Math.round(this.scroll), 0, this.last);
      fit(this.count, this.n > this.per ? `${first + 1}–${Math.min(this.n, first + this.per)} of ${this.n}` : `${this.n} active`);
      this.count.position.set((this.prev.visible ? this.prev.x - this.prev.w / 2 - 8 : this.W - this.pad) - this.count.width,
        this.pad + 3);
      // page dots: the current one stretches into a pill
      const pages = this.pages;
      this.dots.clear();
      if (this.n > this.per) {
        const pos = this.scroll / this.per;
        this.dotsX0 = this.W / 2 - ((pages - 1) * 16) / 2;
        for (let k = 0; k < pages; k++) {
          const near = clamp(1 - Math.abs(pos - k), 0, 1);
          const w = 7 + near * 10, x = this.dotsX0 + k * 16;
          this.dots.roundRect(x - w / 2, 3, w, 7, 3.5).fill({ color: near > 0.5 ? col.ink : col.muted, alpha: 0.35 + 0.65 * near });
        }
        this.dots.hitArea = new Rectangle(this.dotsX0 - 10, -4, pages * 16 + 4, 20);
      }
    }
    // zen: a small tag on the hovered tree
    this.zenTag.visible = this.zen && !!this.hover;
    if (this.zenTag.visible) {
      const card = this.cards.get(this.hover), s = card?.s;
      if (s) {
        fit(this.zenTagTxt, `${Math.round(s.g * 100)}% · ${s.title || s.name}`, CARD_W - 24);
        recolor(this.zenTagTxt, col.ink);
        this.zenTagTxt.position.set(8, 3);
        this.zenTagBg.clear().roundRect(0, 0, this.zenTagTxt.width + 16, 20, 10).fill({ color: col.panel, alpha: 0.88 })
          .stroke({ width: 1, color: col.line });
        this.zenTag.position.set(this.viewport.x + card.x + this.strip.x + 5, this.viewport.y + 5);
      }
    }
  }
}
