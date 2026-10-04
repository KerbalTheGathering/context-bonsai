// The focus card: one session up close. Identity, the living tree with its readout, the shelf as a
// meter, status with the Compact button, then context-over-time and grouped stats.
import { Container, Graphics } from "pixi.js";
import { CROPS, Diorama } from "./diorama.js";
import { fmtAgo, fmtDur, fmtK, fmtTok, nowSec, plural } from "./format.js";
import { clamp, stageFor, treeFor } from "./tree.js";
import { styleOf, vgrad } from "./styles.js";
import { Button, C, DISPLAY, MONO, Runs, ease, fit, label, recolor, tween } from "./ui.js";

const PHASE_TEXT = {
  armed: ["Ready to prune", "warn"],
  compacting: ["Pruning", "warn"],
  pruned: ["Regrowing", "ok"],
  watering: ["Regrowing", "ok"],
};

export const FOCUS_W = 300;

export class FocusView extends Container {
  constructor(app, ctrl) {
    super();
    this.app = app;
    this.ctrl = ctrl;
    this.W = FOCUS_W;
    this.pad = 16;
    this.zen = false;
    this.reveal = 0;

    this.panelFx = new Container(); // whatever the style puts behind the card (an aurora, paper)
    this.panel = new Graphics();
    this.addChild(this.panelFx, this.panel);

    this.back = new Button("‹ 1", { onTap: () => ctrl.showGrove(), size: 12, padX: 9, h: 22 });
    this.title = label("", 15, 0xffffff, { weight: "600", family: DISPLAY });
    this.liveDot = new Graphics();
    this.liveHalo = new Graphics().circle(0, 0, 6.5).fill(0xffffff);
    this.idle = label("", 11.5, 0xffffff);
    this.meta = label("", 11.5, 0xffffff);
    this.branchIcon = new Graphics();
    this.metaB = label("", 11.5, 0xffffff);
    this.header = new Container();
    this.header.addChild(this.back, this.title, this.liveHalo, this.liveDot, this.idle, this.meta, this.branchIcon, this.metaB);

    this.scene = new Diorama(app, { width: this.W, crop: CROPS.focus, theme: ctrl.focusTheme(), tree: treeFor("") });
    this.pct = label("", 40, 0xffffff, { weight: "300", family: DISPLAY });
    this.tok = label("", 11.5, 0xffffff);
    this.meter = new Graphics();
    this.meterGlow = new Graphics();
    this.sceneBox = new Container();
    this.sceneBox.addChild(this.scene, this.meter, this.meterGlow, this.pct, this.tok);

    this.dot = new Graphics();
    this.stage_ = label("", 12.5, 0xffffff, { weight: "600" });
    this.advice = label("", 12.5, 0xffffff);
    this.compact = new Button("Compact", { onTap: () => ctrl.onCompact(), size: 12 });
    this.jobs = new Container();
    this.jobsBg = new Graphics();
    this.jobsTxt = label("", 11, 0xffffff);
    this.jobs.addChild(this.jobsBg, this.jobsTxt);
    this.status = new Container();
    this.status.addChild(this.dot, this.stage_, this.advice, this.compact, this.jobs);

    this.lines = new Graphics();
    this.spark = new Graphics();
    this.sparkRuns = new Runs(12);
    this.noReplies = label("No replies yet", 12.5, 0xffffff);
    this.rows = [0, 1, 2].map(() => {
      const row = new Container();
      row.cap = label("", 9.5, 0xffffff, { weight: "600", family: MONO });
      row.runs = new Runs(12);
      row.addChild(row.cap, row.runs);
      return row;
    });
    this.lower = new Container();
    this.lower.addChild(this.lines, this.spark, this.sparkRuns, this.noReplies, ...this.rows);

    this.zenTag = new Container();
    this.zenTagBg = new Graphics();
    this.zenTagTxt = label("", 11.5, 0xffffff);
    this.zenTag.addChild(this.zenTagBg, this.zenTagTxt);

    this.addChild(this.header, this.sceneBox, this.status, this.lower, this.zenTag);
    this.h = 400;
  }

  // Animate the card in: the scene settles, then the rows rise in one after another.
  enter() {
    const parts = [this.header, this.sceneBox, this.status, this.lower];
    parts.forEach((p, i) => {
      p.alpha = 0;
      p.y += 10;
      tween(p, { alpha: 1, y: p.y - 10 }, 380, { delay: 60 + i * 70 });
    });
    this.sceneBox.scale.set(0.96);
    this.sceneBox.pivot.set(0, 0);
    tween(this.sceneBox.scale, { x: 1, y: 1 }, 520, { fn: ease.out });
    this.reveal = 0;
    tween(this, { reveal: 1 }, 1100, { delay: 350, fn: ease.inOut });
  }

  // Lay out for the current data; returns the card size.
  layout() {
    const s = this.ctrl.focusSession(), theme = this.ctrl.focusTheme(), col = C(theme);
    const W = this.W, pad = this.pad, S = styleOf(theme);
    this.theme = theme;
    this.S = S;
    for (const t of [this.title, this.pct]) if (t.style.fontFamily !== S.display) t.style.fontFamily = S.display;
    this.scene.setTheme(theme);
    this.scene.setTree(treeFor(s?.id || ""));
    this.scene.cc = s?.compactions || 0;

    if (this.zen) {
      if (this.scene.crop !== CROPS.zen) {
        this.scene.crop = CROPS.zen;
        this.scene.resize(this.W - 12);
      }
      this.header.visible = this.status.visible = this.lower.visible = false;
      this.pct.visible = this.tok.visible = this.meter.visible = false;
      this.sceneBox.position.set(6, 6);
      this.h = this.scene.h + 12;
      this.drawPanel(col, this.h);
      this.zenTag.visible = this.ctrl.hovering;
      return { w: W, h: this.h };
    }
    if (this.scene.crop !== CROPS.focus) {
      this.scene.crop = CROPS.focus;
      this.scene.resize(this.W);
    }
    this.zenTag.visible = false;
    this.header.visible = this.status.visible = this.lower.visible = true;
    this.pct.visible = this.tok.visible = this.meter.visible = true;

    // identity: back to the grove, session title, live dot; then project · branch · changes
    const n = this.ctrl.order.length;
    let x = pad;
    this.back.visible = n > 1;
    if (n > 1) {
      this.back.setText(`‹ ${n}`);
      this.back.style({ fg: col.muted, accent: col.muted, panel: col.panel });
      this.back.position.set(pad + this.back.w / 2 - 2, pad + 9);
      this.back.draw();
      x = pad + this.back.w + 6;
    }
    const ago = s?.mtime ? nowSec() - s.mtime : 9e9;
    this.live = ago < 60;
    const idle = this.live ? "" : fmtAgo(ago).replace("idle ", "");
    recolor(this.idle, col.muted);
    fit(this.idle, idle);
    this.idle.position.set(W - pad - 10 - (idle ? this.idle.width + 6 : 0), pad + 1);
    recolor(this.title, col.ink);
    fit(this.title, s?.title || (s?.cwd ? s.name : "No session"), this.idle.x - x - 8);
    this.title.position.set(x, pad - 2);
    this.liveDot.position.set(W - pad - 3.5, pad + 9);
    this.liveHalo.position.copyFrom(this.liveDot.position);
    this.liveDot.clear().circle(0, 0, 3.5).fill(this.live ? col.ok : col.muted);
    this.liveHalo.tint = col.ok;
    this.liveHalo.visible = this.live;
    // project, then a drawn branch icon with the branch and its changes
    const proj = s?.cwd && s.title && s.title !== s.name ? s.name : "";
    const branch = s?.git?.[0];
    recolor(this.meta, col.muted);
    fit(this.meta, proj + (proj && branch ? "  ·  " : ""), W - pad * 2);
    this.meta.position.set(pad, pad + 21);
    this.branchIcon.visible = this.metaB.visible = !!branch;
    if (branch) {
      const bx = pad + this.meta.width + 1, by = pad + 24;
      this.branchIcon.clear().moveTo(bx + 2.5, by + 1.5).lineTo(bx + 2.5, by + 10.5)
        .moveTo(bx + 8.5, by + 3.5).bezierCurveTo(bx + 8.5, by + 7, bx + 2.5, by + 6, bx + 2.5, by + 9)
        .stroke({ width: 1.2, color: col.muted, cap: "round" })
        .circle(bx + 2.5, by + 1.5, 1.6).circle(bx + 8.5, by + 2.5, 1.6).circle(bx + 2.5, by + 10.5, 1.6).fill(col.muted);
      recolor(this.metaB, col.muted);
      fit(this.metaB, `${branch}  ·  ${s.git[1] ? `${s.git[1]} changed` : "clean"}`, W - pad - (bx + 14));
      this.metaB.position.set(bx + 14, pad + 21);
    }

    // the scene, with the readout on the wall
    const ty = 54;
    this.sceneBox.position.set(0, ty);
    this.scene.position.set(0, 0);
    recolor(this.pct, col.ink);
    this.pct.style.stroke = { color: col.wall, width: 5, join: "round" };
    this.pct.position.set(pad, 0);
    recolor(this.tok, col.muted);
    this.tok.style.stroke = { color: col.wall, width: 4, join: "round" };
    const tok = !s ? "" : s.afterCompact ? "compacted, waiting for a reply"
      : s.tokens != null ? `${fmtTok(s.tokens)} of ${fmtK(this.ctrl.cfg.window || 1e6)}` : "";
    fit(this.tok, tok);
    let y = ty + this.scene.h + 12;

    // status: stage (or compaction progress) and the compact button
    const ctrl = this.ctrl, now = nowSec();
    let [lbl, state, advice] = stageFor(ctrl.g);
    if (PHASE_TEXT[ctrl.phase]) [lbl, state] = PHASE_TEXT[ctrl.phase];
    let text = advice, tcol = "muted";
    if (ctrl.phase === "armed") {
      text = ctrl.foundApp ? "copied: Ctrl+V, Enter in Claude" : "copied /compact: paste it in Claude";
      tcol = "warn";
    } else if (ctrl.phase === "compacting") {
      const exp = s?.lastDuration;
      text = `${Math.floor(now - ctrl.phaseAt)}s` + (exp ? ` of ~${Math.round(exp)}s` : "");
    } else if (ctrl.phase === "pruned" || ctrl.phase === "watering") {
      text = "restoring state…";
    } else if (ctrl.caption && now < ctrl.caption.until) {
      text = ctrl.caption.text;
      tcol = ctrl.caption.color;
    }
    this.stateColor = col[state];
    this.status.position.set(0, y);
    this.statusY = y;
    this.dot.clear().circle(pad + 4, 10, 4).fill(col[state]);
    recolor(this.stage_, col.ink);
    fit(this.stage_, lbl);
    this.stage_.position.set(pad + 14, 1);
    const showBtn = ctrl.phase === "idle" || ctrl.phase === "armed";
    this.compact.visible = showBtn;
    this.compact.setText(ctrl.phase === "armed" ? "Cancel" : "Compact");
    this.compact.kind = state === "crit" && ctrl.phase === "idle" ? "solid" : "outline";
    this.compact.style({ fg: col.ink, accent: col[state === "ok" ? "muted" : state], panel: col.panel });
    this.compact.position.set(W - pad - this.compact.w / 2, 10);
    this.compact.draw();
    const bx0 = showBtn ? W - pad - this.compact.w - 8 : W - pad;
    recolor(this.advice, col[tcol]);
    fit(this.advice, "  ·  " + text, bx0 - (this.stage_.x + this.stage_.width));
    this.advice.position.set(this.stage_.x + this.stage_.width, 1);
    y += 32;
    this.jobs.visible = !!s?.jobs?.length;
    if (this.jobs.visible) { // only while something is running
      const nj = s.jobs.length, desc = s.jobs[0].desc || "";
      recolor(this.jobsTxt, col.warn);
      fit(this.jobsTxt, `◷  ${nj} ${plural(nj, "job")} running` + (desc ? ` · ${desc}` : ""), W - pad * 2 - 20);
      this.jobsTxt.position.set(10, 2);
      this.jobsBg.clear().roundRect(0, 0, this.jobsTxt.width + 20, 20, 10).fill({ color: col.warn, alpha: 0.08 })
        .stroke({ width: 1, color: col.warn, alpha: 0.7 });
      this.jobs.position.set(pad, 30);
      y += 28;
    }

    // tokens: context per call over the session, then peak / avg / total
    this.lower.position.set(0, y);
    const st = s?.stats;
    this.lines.clear();
    S.divider(this.lines, pad, 0, W - pad * 2, col, 1);
    let ly = 12;
    this.sparkY = ly;
    const hasSeries = st && st.series.length >= 2;
    this.noReplies.visible = !hasSeries;
    this.spark.visible = this.sparkRuns.visible = hasSeries;
    if (hasSeries) {
      ly += 42;
      this.sparkRuns.set([[fmtTok(st.peak), "n"], [" peak · ", "u"], [fmtTok(st.avg), "n"], [" avg · ", "u"],
        [fmtTok(st.total), "n"], [" total", "u"]], col, W - pad * 2);
      this.sparkRuns.position.set(pad, ly);
    } else {
      recolor(this.noReplies, col.muted);
      this.noReplies.position.set(pad, ly);
    }
    ly += 26;
    S.divider(this.lines, pad, ly, W - pad * 2, col, 2);
    ly += 12;

    // grouped stats: context, work, time
    const sep = " · ";
    const cache = st?.cache ?? null;
    const cstyle = cache == null || cache >= 0.8 ? "n" : cache >= 0.5 ? "warn" : "crit";
    const calls = st?.tools || 0, errors = st?.errors || 0, files = st?.files || 0, cc = s?.compactions || 0;
    const timeRow = [];
    if (st?.started && s?.mtime) timeRow.push([fmtDur(s.mtime - st.started), "n"], [sep, "u"]);
    if (st?.lastPrompt) {
      const since = now - st.lastPrompt;
      timeRow.push(...(since < 60 ? [["just now", "n"]] : [["asked ", "u"], [fmtDur(since), "n"], [" ago", "u"]]), [sep, "u"]);
    }
    timeRow.push([String(st?.prompts || 0), "n"], [" " + plural(st?.prompts || 0, "prompt"), "u"]);
    const rows = [
      ["CONTEXT", [[cache == null ? "–" : `${Math.round(cache * 100)}%`, cstyle], [" cache" + sep, "u"],
        [String(cc), "n"], [" " + plural(cc, "compact") + sep, "u"], [String(st?.calls || 0), "n"],
        [" " + plural(st?.calls || 0, "call"), "u"]]],
      ["WORK", [[String(calls), "n"], [" " + plural(calls, "tool") + sep, "u"],
        [String(errors), calls && errors / calls > 0.1 ? "warn" : "n"], [" " + plural(errors, "error") + sep, "u"],
        [String(files), "n"], [" " + plural(files, "file"), "u"]]],
      ["TIME", timeRow],
    ];
    rows.forEach(([cap, parts], i) => {
      const row = this.rows[i];
      recolor(row.cap, col.muted);
      fit(row.cap, cap);
      row.cap.position.set(pad, 3);
      row.runs.set(parts, col, W - pad * 2 - 62);
      row.runs.position.set(pad + 62, 0);
      row.position.set(0, ly);
      ly += 22;
    });
    this.h = Math.round(y + ly + pad - 6);
    // one tile behind the status and stats, for styles that draw sections as panes
    this.drawPanel(col, this.h, [{ x: 8, y: this.statusY - 8, w: W - 16, h: this.h - this.statusY }]);
    return { w: W, h: this.h };
  }

  drawPanel(col, h, tiles = []) {
    const theme = this.theme || this.ctrl.focusTheme();
    const key = `${theme.key}|${h}|${JSON.stringify(tiles)}`;
    if (key === this.panelKey) return;
    this.panelKey = key;
    styleOf(theme).panel(this, { W: this.W, h, col, theme, tiles }); // Windows rounds the window's corners
  }

  // Per frame: the tree, the readout, the meter on the shelf, the sparkline drawing itself in.
  update(ctx) {
    const s = this.ctrl.focusSession(), col = C(this.theme || this.ctrl.focusTheme());
    const g = this.ctrl.g;
    this.scene.g = g;
    this.scene.phase = this.ctrl.phase;
    this.scene.update(ctx);
    const now = performance.now() / 1000;
    (this.S || styleOf(this.ctrl.focusTheme())).animatePanel(this, now);

    if (this.zen) {
      if (this.zenTag.visible) {
        fit(this.zenTagTxt, `${Math.round(g * 100)}%` + (PHASE_TEXT[this.ctrl.phase] ? ` · ${PHASE_TEXT[this.ctrl.phase][0].toLowerCase()}` : ""));
        recolor(this.zenTagTxt, col.ink);
        this.zenTagTxt.position.set(9, 3);
        this.zenTagBg.clear().roundRect(0, 0, this.zenTagTxt.width + 18, 22, 11).fill({ color: col.panel, alpha: 0.85 })
          .stroke({ width: 1, color: col.line });
        this.zenTag.position.set(14, 14);
      }
      return;
    }

    fit(this.pct, `${Math.round(g * 100)}%`);
    this.tok.position.set(this.pad + this.pct.width + 8, 22);

    // live dot breathes (a transform, not a redraw)
    const pulse = 0.5 + 0.5 * Math.sin(now * 2.6);
    this.liveHalo.scale.set((3.5 + pulse * 3) / 6.5);
    this.liveHalo.alpha = 0.25 * (1 - pulse);

    // the shelf edge doubles as the meter; a shimmer slides along it while compacting
    const W = this.W, k = this.scene.k, shelf = (452 - this.scene.crop[1]) * k, mh = 4;
    const color = this.stateColor ?? col.ok;
    const compacting = this.ctrl.phase === "compacting";
    const S = this.S || styleOf(this.ctrl.focusTheme());
    const mkey = compacting ? `c${Math.round(now * 60)}` : `${Math.round(g * 1000)}|${color}|${shelf}|${col.line}|${this.theme?.key}`;
    if (mkey !== this.mkey) {
      this.mkey = mkey;
      S.meter(this, { W, y: shelf, mh, g, color, col, compacting, now });
    }
    if (!compacting) this.meterGlow.alpha = (S.glowAlpha ?? 0.18) + 0.12 * pulse;

    // context per call, drawn in over the first second
    const st = s?.stats;
    if (this.spark.visible && st) this.drawSpark(st.series, col, color);
  }

  drawSpark(series, col, color) {
    const pad = this.pad, x0 = pad, w = this.W - pad * 2, h = 34, y0 = this.sparkY;
    const win = Math.max(...series) * 1.12 || 1; // the session's own shape, not the whole window
    const n = series.length, shown = Math.max(2, Math.ceil(n * this.reveal));
    const key = `${n}|${shown}|${color}|${series[n - 1]}`;
    if (this.sparkKey === key) return;
    this.sparkKey = key;
    const pt = (i) => [x0 + (i / (n - 1)) * w, y0 + h - (series[i] / win) * h];
    const sp = this.spark.clear();
    const pts = [];
    for (let i = 0; i < shown; i++) pts.push(...pt(i));
    const area = vgrad(color, col.panel);
    sp.poly([x0, y0 + h, ...pts, pts[pts.length - 2], y0 + h]).fill({ fill: area, alpha: 0.28 });
    sp.moveTo(pts[0], pts[1]);
    for (let i = 2; i < pts.length; i += 2) sp.lineTo(pts[i], pts[i + 1]);
    sp.stroke({ width: 1.6, color, join: "round", cap: "round" });
    const lx = pts[pts.length - 2], ly = pts[pts.length - 1];
    sp.circle(lx, ly, 5).fill({ color, alpha: 0.25 }).circle(lx, ly, 2.5).fill(color);
  }
}
