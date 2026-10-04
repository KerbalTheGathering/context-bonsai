// Context Bonsai renderer: owns the view (focus card or grove), the compaction choreography and the
// ambience, and keeps the window sized to the card. Data arrives from the main process every ~2s.
import "pixi.js/unsafe-eval";
import { Application, UPDATE_PRIORITY } from "pixi.js";
import { resolveTheme } from "../shared/themes.js";
import { FocusView } from "./focus.js";
import { GroveView } from "./grove.js";
import { BASELINE, lerp, mix } from "./tree.js";
import { stepTweens, tween } from "./ui.js";

const api = window.bonsai;

class Controller {
  async init() {
    this.app = new Application();
    await this.app.init({
      width: 300, height: 420, background: "#1A201F", antialias: true, preference: "webgl",
      resolution: window.devicePixelRatio || 1, autoDensity: true,
    });
    document.body.appendChild(this.app.canvas);

    this.sessions = new Map();
    this.order = [];
    this.cfg = { window: 1e6 };
    this.system = { light: false, accent: "#0078D4" };
    this.view = "focus";
    this.follow = true; // focus follows the newest session until the user picks a tree
    this.resumeFollow = false;
    this.focusPath = null;
    this.g = 0.06;
    this.gTween = null;
    this.phase = "idle";
    this.phaseAt = 0;
    this.caption = null;
    this.pendingRestore = null;
    this.preview = false;
    this.foundApp = true;
    this.hovering = false;
    this.first = true;

    this.focus = new FocusView(this.app, this);
    this.grove = new GroveView(this.app, this);
    this.current = this.focus;
    this.app.stage.addChild(this.focus);

    this.bindInput();
    const guard = (fn) => (x) => { // errors in IPC callbacks surface in the preload world without a stack
      try {
        fn(x);
      } catch (e) {
        console.error(e.stack || e);
      }
    };
    api.onState(guard((s) => this.onState(s)));
    api.onCommand(guard((c) => this.onCommand(c)));
    api.ready();
    // draw only when something changed: replace Pixi's every-frame render with one that checks
    this.needsRender = true;
    this.renderedAt = 0;
    this.app.ticker.remove(this.app.render, this.app);
    this.app.ticker.add((t) => this.tick(t.deltaMS));
    this.app.ticker.add(() => {
      if (!this.needsRender) return;
      this.needsRender = false;
      this.renderedAt = performance.now();
      this.app.render();
    }, null, UPDATE_PRIORITY.LOW);
    api.onPause?.((paused) => (paused ? this.app.ticker.stop() : (this.invalidate(), this.app.ticker.start())));
    this.watchResolution();
    setInterval(() => this.step(), 500);
  }

  // --- data ---
  onState(st) {
    this.cfg = st.cfg;
    this.system = st.system;
    this.order = st.order;
    this.sessions = new Map(st.sessions.map((s) => [s.path, s]));
    this.newest = st.newest;
    const pinned = this.cfg.pinned && this.sessions.has(this.cfg.pinned) ? this.cfg.pinned : null;
    if (this.phase === "idle" && (this.follow || !this.focusPath)) {
      this.setFocus(pinned || (this.sessions.has(this.newest) ? this.newest : this.order[0]) || null);
    }
    for (const e of st.events) this.onEvent(e);
    if (this.first) {
      this.first = false;
      this.g = this.focusSession()?.g ?? 0.06;
      if (this.order.length > 1) this.view = "grove";
      this.swap(this.view === "grove" ? this.grove : this.focus);
    }
    if (this.view === "grove" && this.order.length <= 1) this.showFocus();
    this.focus.zen = this.grove.zen = !!this.cfg.zen;
    this.relayout();
  }

  onEvent(e) {
    if (e.kind === "compacted") {
      if (e.path === this.focusPath) this.startPrune(Math.max(this.g, e.from), e.to);
      else if (this.phase === "idle" && this.view === "grove") { // show the compaction on that session's own card
        this.setFocus(e.path);
        this.g = Math.max(e.from, e.to);
        this.showFocus();
        this.startPrune(this.g, e.to);
      }
    } else if (e.kind === "restored" && e.path === this.focusPath) {
      this.pendingRestore = e.msg || "";
    } else if (e.kind === "precompact") {
      this.setFocus(e.path);
      this.resumeFollow = this.follow;
      this.follow = false; // stay on this tree until the animation finishes
      if (this.view !== "focus") this.showFocus();
      this.setPhase("compacting");
    }
  }

  onCommand({ cmd, value }) {
    this.invalidate();
    if (cmd === "view") value === "grove" ? this.showGrove() : this.showFocus();
    else if (cmd === "compact") this.onCompact();
    else if (cmd === "preview") this.runPreview();
    else if (cmd === "rescanned") {
      this.caption = { text: `Found ${value} active ${value === 1 ? "session" : "sessions"}.`, color: "muted",
        until: Date.now() / 1000 + 6 };
      this.relayout();
    }
  }

  focusSession() {
    return this.sessions.get(this.focusPath) || null;
  }

  setFocus(path) {
    if (path === this.focusPath) return;
    this.focusPath = path;
    this.g = this.focusSession()?.g ?? 0.06;
    this.gTween = null;
    this.focus.scene.setPile([]);
    this.caption = null;
    api.setFocus(path);
  }

  widgetTheme() {
    return resolveTheme(this.cfg.theme || "Moss", this.system);
  }

  themeFor(s) {
    const per = s?.name && (this.cfg.project_themes || {})[s.name.toLowerCase()];
    return resolveTheme(per || this.cfg.theme || "Moss", this.system);
  }

  focusTheme() {
    return this.themeFor(this.focusSession());
  }

  // --- views ---
  swap(view) {
    if (this.current !== view) {
      this.app.stage.removeChild(this.current);
      this.app.stage.addChild(view);
      this.current = view;
    }
    this.relayout();
    view.enter?.();
  }

  invalidate() {
    this.needsRender = true;
  }

  // Moved to a monitor with different scaling: render at its resolution and re-bake what was baked.
  watchResolution() {
    const dpr = window.devicePixelRatio || 1;
    matchMedia(`(resolution: ${dpr}dppx)`).addEventListener("change", () => {
      this.onResolution();
      this.watchResolution();
    }, { once: true });
  }

  onResolution() {
    const r = window.devicePixelRatio || 1;
    this.app.renderer.resize(this.size?.w || 300, this.size?.h || 420, r);
    for (const scene of [this.focus.scene, ...[...this.grove.cards.values()].map((c) => c.scene)]) scene.resize(scene.w);
    this.focus.panelKey = this.grove.panelKey = null;
    this.relayout();
  }

  relayout(invalidate = true) {
    if (invalidate) this.invalidate();
    const { w, h } = this.current.layout();
    const panel = (this.current === this.grove ? this.widgetTheme() : this.focusTheme()).colors.panel;
    if (panel !== this.panelColor) { // what shows for a moment while the window resizes
      this.panelColor = panel;
      this.app.renderer.background.color = panel;
      api.setBackground(panel);
    }
    if (w !== this.size?.w || h !== this.size?.h) {
      this.size = { w, h };
      this.app.renderer.resize(w, h);
      api.resize(w, h);
    }
  }

  async openFocus(path, card) {
    this.follow = false; // stay on the tree you opened
    if (card && this.view === "grove") await this.grove.zoomInto(path);
    this.setFocus(path);
    this.showFocus();
  }

  showFocus() {
    if (this.view === "focus" && this.current === this.focus) return;
    this.view = "focus";
    this.grove.scroll = this.grove.target; // the carousel settles while hidden
    this.grove.vel = 0;
    this.swap(this.focus);
  }

  showGrove() {
    if (this.order.length <= 1) return;
    this.view = "grove";
    this.follow = true;
    this.grove.reveal(this.focusPath);
    this.swap(this.grove);
  }

  // --- compaction: idle -> armed (Compact clicked) -> compacting (PreCompact hook) -> pruned -> watering ---
  setPhase(phase) {
    this.phase = phase;
    this.phaseAt = Date.now() / 1000;
    if (phase !== "idle") this.caption = null;
    this.relayout();
  }

  async onCompact() {
    if (this.phase === "armed") return this.setPhase("idle");
    if (this.phase !== "idle") return;
    this.setPhase("armed");
    this.foundApp = await api.compact();
    this.relayout();
  }

  startPrune(frm, to) {
    this.focus.scene.prune(frm, to, 100 + (this.focusSession()?.compactions || 0));
    this.gTween = { from: frm, to, t0: performance.now() + 200, dur: 900 };
    this.setPhase("pruned");
  }

  water(msg) {
    this.setPhase("watering");
    this.pendingRestore = null;
    this.focus.scene.water(Math.max(this.focusSession()?.g ?? 0, BASELINE) + 0.15);
    const text = (msg || "").replace("↻ restored:", "").trim() || "state restored";
    setTimeout(() => {
      this.setPhase("idle");
      this.preview = false;
      if (this.resumeFollow) {
        this.follow = true;
        this.resumeFollow = false;
      }
      this.caption = { text: "Restored: " + text, color: "ok", until: Date.now() / 1000 + 12 };
      this.relayout();
    }, 3400);
  }

  // Plays the whole compact -> prune -> rehydrate sequence without touching the session.
  runPreview() {
    if (this.phase !== "idle") return;
    if (this.view !== "focus") this.showFocus();
    this.preview = true;
    const frm = Math.max(this.g, 0.9), to = this.g;
    this.g = frm;
    this.setPhase("compacting");
    setTimeout(() => {
      this.focus.scene.prune(frm, to, 7);
      this.gTween = { from: frm, to, t0: performance.now() + 200, dur: 900 };
      this.setPhase("pruned");
      this.pendingRestore = "preview · nothing was compacted";
    }, 4500);
  }

  // Twice a second: phase timeouts, and settle the tree on the session's real size.
  step() {
    const now = Date.now() / 1000, s = this.focusSession();
    if (this.phase === "pruned" && !this.gTween && (this.pendingRestore != null || now - this.phaseAt > 8)) {
      this.water(this.pendingRestore);
    }
    if (this.phase === "armed" && now - this.phaseAt > 180) {
      this.setPhase("idle");
      this.caption = { text: "No compaction seen. Click Compact to try again.", color: "muted", until: now + 8 };
    }
    if (this.phase === "compacting" && now - this.phaseAt > 600) {
      this.setPhase("idle");
      if (this.resumeFollow) { this.follow = true; this.resumeFollow = false; }
    }
    if (this.phase === "idle" && !this.gTween && !this.preview && s && Math.abs(s.g - this.g) > 0.002) {
      this.gTween = { from: this.g, to: s.g, t0: performance.now(), dur: 1200 }; // grow smoothly to the new size
    }
    this.relayout(false); // text that ticks over (timers, "idle 3m") shows on the next safety redraw
  }

  // --- ambience ---
  working() {
    const s = this.focusSession();
    return !!s && Date.now() / 1000 - s.mtime < 8;
  }

  sleeping() {
    const s = this.focusSession();
    return !!s && Date.now() / 1000 - s.mtime > 1800;
  }

  // The clock's tint over the scene: dawn, day, dusk, night; deeper when the session sleeps.
  sky() {
    if (this.sleeping()) return { color: 0x0a0e24, alpha: 0.4 };
    const d = new Date(), h = d.getHours() + d.getMinutes() / 60;
    if (h >= 5 && h < 8) return { color: 0xffa06e, alpha: 0.12 * (1 - Math.abs(h - 6.5) / 1.5) };
    if (h >= 8 && h < 17) return { color: 0xffffff, alpha: 0 };
    if (h >= 17 && h < 19) return { color: 0xff8246, alpha: (0.1 * (h - 17)) / 2 };
    if (h >= 19 && h < 21) {
      const t = (h - 19) / 2;
      return { color: mix(0xff8246, 0x192350, t), alpha: lerp(0.1, 0.22, t) };
    }
    return { color: 0x192350, alpha: 0.22 };
  }

  night() {
    const h = new Date().getHours();
    return this.sleeping() || h >= 21 || h < 5;
  }

  tick(dt) {
    // full frame rate while something moves on purpose; ambient sway is smooth enough at 30
    const lively = stepTweens(dt) || this.gTween || this.phase !== "idle" || this.dragging
      || (this.current === this.grove && (this.grove.drag || Math.abs(this.grove.vel) > 0.001
        || Math.abs(this.grove.target - this.grove.scroll) > 0.001))
      || (this.current === this.focus && this.focus.scene.particles.length > 0);
    const motion = (this.current === this.grove ? this.grove : this.focus).motion;
    // 60 fps for things you're doing, 30 for sway and compaction, 15 for ambience, and when nothing moves
    // just 4 ticks a second to notice changes, drawing only when something did (or once a second)
    this.app.ticker.maxFPS = window.__fpsCap ?? (lively ? 0 : motion >= 2 ? 30 : motion === 1 ? 15 : 4);
    if (lively || motion > 0 || performance.now() - this.renderedAt > 1000) this.invalidate();
    if (window.__probe && performance.now() - (this.probeAt || 0) > 2000) {
      this.probeAt = performance.now();
      console.log(`fps ${this.app.ticker.FPS.toFixed(0)} max ${this.app.ticker.maxFPS} lively ${!!lively} motion ${motion} `
        + `view ${this.view} hover ${this.hovering}`);
    }
    if (this.gTween) {
      const { from, to, t0, dur } = this.gTween;
      const t = Math.min(1, Math.max(0, (performance.now() - t0) / dur));
      this.g = lerp(from, to, 1 - (1 - t) ** 3);
      if (t >= 1) {
        this.gTween = null;
        if (!this.preview) this.g = this.focusSession()?.g ?? to;
      }
    }
    const ambient = this.cfg.ambient !== false;
    const ctx = { dt, ambient, working: this.working(), sleeping: this.sleeping(), night: this.night(), sky: this.sky(),
      hovering: this.hovering };
    if (this.current === this.grove) {
      this.grove.update({ ...ctx, working: false, sleeping: false });
    } else this.focus.update(ctx);
  }

  // --- input: drag the window from anywhere that isn't a control; right-click for the menu ---
  bindInput() {
    const stage = this.app.stage;
    stage.eventMode = "static";
    stage.hitArea = this.app.screen;
    stage.on("pointerdown", (e) => {
      if (e.button !== 0) return;
      let t = e.target;
      while (t && t !== stage) {
        if (t.isUi || t === this.grove.viewport) return;
        t = t.parent;
      }
      this.dragging = true;
      api.dragStart();
    });
    const end = () => {
      if (this.dragging) {
        this.dragging = false;
        api.dragEnd();
      }
    };
    window.addEventListener("pointerup", end);
    window.addEventListener("blur", end);
    window.addEventListener("contextmenu", (e) => {
      e.preventDefault();
      const s = this.focusSession();
      api.menu({ view: this.view, count: this.order.length, phase: this.phase, focusPath: this.focusPath,
        focusName: s?.cwd ? s.name : null });
    });
    window.addEventListener("dblclick", () => api.toggleZen());
    document.addEventListener("mouseenter", () => { this.hovering = true; this.relayout(); });
    document.addEventListener("mouseleave", () => { this.hovering = false; this.grove.hover = null; this.relayout(); });
  }
}

window.addEventListener("unhandledrejection", (e) => console.error(e.reason?.stack || e.reason));
window.addEventListener("error", (e) => console.error(e.error?.stack || e.message));
// Dev aid: create and destroy n scenes, and report GPU textures before and after (should match).
window.__leakTest = async (n = 40) => {
  const { Diorama, CROPS } = await import("./diorama.js");
  const { treeFor } = await import("./tree.js");
  const c = window.__bonsai, r = c.app.renderer;
  const frames = (k) => new Promise((res) => { let i = 0; const f = () => (++i >= k ? res() : requestAnimationFrame(f)); f(); });
  const count = () => r.texture.managedTextures.filter(Boolean).length; // removed entries leave null slots
  await frames(10);
  const before = count();
  const beforeSet = new Set(r.texture.managedTextures);
  for (let i = 0; i < n; i++) {
    const d = new Diorama(c.app, { width: 124, crop: CROPS.grove, theme: c.widgetTheme(), tree: treeFor(`leak${i}.jsonl`) });
    d.g = 0.5;
    c.app.stage.addChild(d);
    for (let k = 0; k < 3; k++) {
      d.update({ dt: 200, ambient: false, working: false, sleeping: false, night: false, sky: null });
      await frames(1);
    }
    d.destroy({ children: true });
    await frames(3);
  }
  await frames(10);
  const after = r.texture.managedTextures.filter((t) => !beforeSet.has(t));
  const kinds = {};
  for (const t of after) {
    const k = `${t.constructor.name}:${t.label || ""}:${t.resource?.constructor?.name || "-"}:${Math.round(t.width)}x${Math.round(t.height)}`;
    kinds[k] = (kinds[k] || 0) + 1;
  }
  return { before, after: count(), n, kinds };
};
window.__bonsai = new Controller();
window.__bonsai.init();
