// UI building blocks drawn in Pixi: text, pills, buttons, text runs, plus a small tween engine.
import { Container, Graphics, Text } from "pixi.js";
import { clamp, hex } from "./tree.js";

export const FONT = ["Segoe UI Variable Text", "Segoe UI", "system-ui", "sans-serif"];
export const DISPLAY = ["Segoe UI Variable Display", "Segoe UI", "system-ui", "sans-serif"];
export const MONO = ["Cascadia Mono", "Consolas", "monospace"];

export function label(text, size, color, { weight = "400", family = FONT, alpha = 1 } = {}) {
  const t = new Text({ text, style: { fontFamily: family, fontSize: size, fill: color, fontWeight: weight } });
  t.alpha = alpha;
  return t;
}

// Set text, trimming with an ellipsis to fit maxw. Only re-measures when the input changes.
export function fit(t, text, maxw = Infinity) {
  const key = `${text}|${Math.round(maxw)}`;
  if (t._fitKey === key) return;
  t._fitKey = key;
  t.text = text;
  if (t.width <= maxw) return;
  let lo = 0, hi = text.length;
  while (lo < hi) {
    const mid = (lo + hi + 1) >> 1;
    t.text = text.slice(0, mid).trimEnd() + "…";
    if (t.width <= maxw) lo = mid;
    else hi = mid - 1;
  }
  t.text = text.slice(0, lo).trimEnd() + "…";
}

export function recolor(t, color) {
  if (t.style.fill !== color) t.style.fill = color;
}

// --- tweens ---
const tweens = new Set();
export const ease = {
  out: (t) => 1 - (1 - t) ** 3,
  inOut: (t) => (t < 0.5 ? 4 * t * t * t : 1 - (-2 * t + 2) ** 3 / 2),
  back: (t) => 1 + 2.2 * (t - 1) ** 3 + 1.2 * (t - 1) ** 2,
};

// tween(obj, { alpha: 1, "scale.x": 1.2 }, 300, { delay, ease })
export function tween(obj, to, ms, { delay = 0, fn = ease.out } = {}) {
  return new Promise((resolve) => {
    const keys = Object.keys(to);
    const get = (k) => k.split(".").reduce((o, p) => o[p], obj);
    const set = (k, v) => {
      const parts = k.split(".");
      const last = parts.pop();
      parts.reduce((o, p) => o[p], obj)[last] = v;
    };
    const tw = { obj, t: -delay, ms, from: null, keys, to, fn, get, set, resolve };
    for (const other of tweens) {
      if (other.obj === obj) other.keys = other.keys.filter((k) => !keys.includes(k)); // newest wins
    }
    tweens.add(tw);
  });
}

export function stepTweens(dt) {
  for (const tw of tweens) {
    tw.t += dt;
    if (tw.t < 0) continue;
    if (!tw.from) tw.from = Object.fromEntries(tw.keys.map((k) => [k, tw.get(k)]));
    const p = clamp(tw.t / tw.ms, 0, 1), e = tw.fn(p);
    if (tw.obj.destroyed) {
      tweens.delete(tw);
      continue;
    }
    for (const k of tw.keys) tw.set(k, tw.from[k] + (tw.to[k] - tw.from[k]) * e);
    if (p >= 1) {
      tweens.delete(tw);
      tw.resolve();
    }
  }
  return tweens.size > 0;
}

// A rounded button with hover and press states.
export class Button extends Container {
  constructor(text, { onTap, size = 12, padX = 12, h = 26, kind = "outline" } = {}) {
    super();
    this.kind = kind;
    this.bg = new Graphics();
    this.txt = label(text, size, 0xffffff, { weight: "600" });
    this.txt.anchor.set(0.5);
    this.addChild(this.bg, this.txt);
    this.padX = padX;
    this.h = h;
    this.hover = 0;
    this.eventMode = "static";
    this.cursor = "pointer";
    this.isUi = true;
    this.on("pointerover", () => tween(this, { hover: 1 }, 140));
    this.on("pointerout", () => tween(this, { hover: 0 }, 200));
    this.on("pointerdown", (e) => { e.stopPropagation(); tween(this.scale, { x: 0.96, y: 0.96 }, 80); });
    this.on("pointerup", () => tween(this.scale, { x: 1, y: 1 }, 160, { fn: ease.back }));
    this.on("pointerupoutside", () => tween(this.scale, { x: 1, y: 1 }, 160));
    this.on("pointertap", (e) => { e.stopPropagation(); onTap?.(); });
    this.colors = { fg: 0xffffff, accent: 0x888888, panel: 0 };
  }

  setText(text) {
    if (this.txt.text !== text) this.txt.text = text;
  }

  get w() {
    return Math.round(this.txt.width + this.padX * 2);
  }

  style(colors) {
    this.colors = colors;
  }

  draw() {
    const { fg, accent, panel } = this.colors, w = this.w, h = this.h;
    this.bg.clear();
    if (this.kind === "solid") {
      this.bg.roundRect(-w / 2, -h / 2, w, h, h / 2).fill({ color: accent, alpha: 0.85 + 0.15 * this.hover });
      recolor(this.txt, panel);
    } else {
      this.bg.roundRect(-w / 2, -h / 2, w, h, h / 2).fill({ color: accent, alpha: 0.1 + 0.16 * this.hover })
        .stroke({ width: 1, color: accent, alpha: 0.55 + 0.45 * this.hover });
      recolor(this.txt, fg);
    }
    this.hitArea = { contains: (x, y) => Math.abs(x) <= w / 2 && Math.abs(y) <= h / 2 };
  }
}

// Left-to-right text runs: numbers bold in ink (or warn/crit), words muted. parts: [[text, style], ...]
export class Runs extends Container {
  constructor(size = 12) {
    super();
    this.size = size;
    this.key = null;
  }

  set(parts, colors, maxw = Infinity) {
    const key = JSON.stringify(parts) + colors.ink + colors.muted;
    if (key === this.key) return;
    this.key = key;
    this.removeChildren().forEach((c) => c.destroy());
    let x = 0;
    for (const [text, style] of parts) {
      const color = style === "u" ? colors.muted : style === "n" ? colors.ink : colors[style];
      const t = label(text, this.size, color, { weight: style === "u" ? "400" : "600" });
      t.x = x;
      x += t.width;
      if (x > maxw) {
        t.destroy();
        break;
      }
      this.addChild(t);
    }
  }
}

export const C = (theme) => Object.fromEntries(Object.entries(theme.colors)
  .filter(([, v]) => typeof v === "string").map(([k, v]) => [k, hex(v)]));

export { vgrad } from "./styles.js";
