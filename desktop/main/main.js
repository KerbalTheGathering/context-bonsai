// Context Bonsai (desktop): Electron main process. Polls Claude Code transcripts, tracks which sessions
// are open, notices compactions and restores, and feeds a PixiJS renderer in a frameless, transparent
// window. Launching it again while it runs closes it, like the Tk widget.
const { app, BrowserWindow, Menu, clipboard, ipcMain, nativeTheme, powerMonitor, screen, systemPreferences } = require("electron");
const fs = require("fs");
const os = require("os");
const path = require("path");
const { execFile } = require("child_process");
const { Session, allTranscripts, openTranscripts, norm } = require("./data");
const { fitInside } = require("./place");
const { readFile, saveKeys } = require("./config");
const { setupDev } = require("./dev");
const { THEMES, THEME_NAMES } = require("../shared/themes");
const STYLE_LABELS = { diorama: "Diorama", glass: "Glass", ink: "Ink" };

// Theme menu items grouped by art style, with the virtual themes first.
function themeItems(checked, pick, labelFor = (n) => n) {
  const items = [];
  for (const n of ["Auto", "Seasons"]) items.push({ label: labelFor(n), type: "radio", checked: checked(n), click: () => pick(n) });
  for (const style of Object.keys(STYLE_LABELS)) {
    const names = THEME_NAMES.filter((n) => THEMES[n]?.style === style);
    if (!names.length) continue;
    items.push({ type: "separator" }, { label: STYLE_LABELS[style], enabled: false });
    for (const n of names) items.push({ label: labelFor(n), type: "radio", checked: checked(n), click: () => pick(n) });
  }
  return items;
}

const WIDGET_DIR = path.join(os.homedir(), ".claude", "widget"); // shared with the Tk widget and the PreCompact hook
const CONFIG = path.join(WIDGET_DIR, "bonsai.json");
const SIGNAL = path.join(WIDGET_DIR, "signal.json");
const DEFAULTS = { window: 1_000_000, topmost: true, pinned: null, theme: "Moss", ambient: true, zen: false,
  project_themes: {} };
const GROVE_MINUTES = 30; // sessions active within this window get a tree, as do sessions that are open
const GROVE_MAX = 12;
const LIVE_SECONDS = 15; // how often to re-read the open-session registry
const POLL_MS = 2000;
const DEV = process.argv.includes("--dev");

let win = null;
let cfg = loadConfig();
let configSeen = mtime(CONFIG);
const sessions = new Map(); // transcript path -> Session
let order = []; // grove order, oldest tree first so trees don't jump around
let focusPath = null; // the renderer's focused session: gets git status and stays in the list
let live = new Set(), liveAt = 0;
let newest = null;
let signalSeen = mtime(SIGNAL);
let drag = null;


function loadConfig() {
  const c = { ...DEFAULTS, ...readFile(CONFIG) };
  if (process.env.BONSAI_THEME) { // dev aid: preview a theme everywhere without saving it
    c.theme = process.env.BONSAI_THEME;
    c.project_themes = {};
  }
  if (process.env.BONSAI_CFG) Object.assign(c, JSON.parse(process.env.BONSAI_CFG)); // dev aid: unsaved overrides
  return c;
}

// Write just these keys, keeping whatever else is in the file: the Tk widget shares it, so writing our
// whole (possibly stale) copy would undo its changes.
function saveConfig(...keys) {
  try {
    saveKeys(CONFIG, cfg, keys);
    configSeen = mtime(CONFIG);
  } catch {}
}

// Pick up settings another app (the Tk widget) changed in the shared file.
function reloadConfig() {
  const m = mtime(CONFIG);
  if (m === configSeen) return false;
  configSeen = m;
  const next = loadConfig();
  if (JSON.stringify(next) === JSON.stringify(cfg)) return false;
  cfg = next;
  win?.setAlwaysOnTop(!!cfg.topmost);
  return true;
}

function mtime(p) {
  try {
    return fs.statSync(p).mtimeMs;
  } catch {
    return 0;
  }
}

function system() {
  let accent = "#0078D4";
  try {
    accent = "#" + systemPreferences.getAccentColor().slice(0, 6).toUpperCase();
  } catch {}
  return { light: !nativeTheme.shouldUseDarkColors, accent };
}

// --- sessions ---
function activePaths() {
  const now = Date.now() / 1000;
  const all = allTranscripts();
  newest = all[0]?.path || null;
  if (now - liveAt > LIVE_SECONDS) {
    liveAt = now;
    live = openTranscripts(all);
  }
  const active = all.filter((t) => now - t.mtime < GROVE_MINUTES * 60 || live.has(norm(t.path))).map((t) => t.path);
  return (active.length ? active : all.slice(0, 1).map((t) => t.path)).slice(0, GROVE_MAX);
}

function refresh() {
  reloadConfig();
  const events = [];
  let paths = activePaths();
  const pinned = cfg.pinned && fs.existsSync(cfg.pinned) ? cfg.pinned : null;
  if (pinned && !paths.some((p) => norm(p) === norm(pinned))) paths = [pinned, ...paths.slice(0, GROVE_MAX - 1)];
  if (focusPath && !paths.includes(focusPath) && fs.existsSync(focusPath)) paths.push(focusPath); // keep the tree you opened
  for (const p of paths) {
    let s = sessions.get(p);
    if (!s) {
      s = new Session(p);
      s.onChange = () => push();
      s.refresh({ git: p === focusPath, window: cfg.window });
      s.seenCc = s.compactions;
      s.seenRestores = s.restores;
      sessions.set(p, s);
      continue;
    }
    const before = s.g;
    s.refresh({ git: p === focusPath, window: cfg.window });
    if (s.compactions > s.seenCc) {
      s.seenCc = s.compactions;
      events.push({ kind: "compacted", path: p, from: before, to: s.g });
    }
    if (s.restores > s.seenRestores) {
      s.seenRestores = s.restores;
      events.push({ kind: "restored", path: p, msg: s.restoredMsg || "" });
    }
  }
  for (const p of [...sessions.keys()]) if (!paths.includes(p)) sessions.delete(p);
  order = [...order.filter((p) => paths.includes(p)), ...paths.filter((p) => !order.includes(p))];

  // the PreCompact hook writes signal.json the moment a compaction starts
  const sm = mtime(SIGNAL);
  if (sm > signalSeen) {
    signalSeen = sm;
    try {
      const sig = JSON.parse(fs.readFileSync(SIGNAL, "utf8"));
      const p = sig.transcript || "";
      let found = [...sessions.keys()].find((k) => norm(k) === norm(p));
      if (!found && fs.existsSync(p)) {
        const s = new Session(p);
        s.onChange = () => push();
        s.refresh({ window: cfg.window });
        s.seenCc = s.compactions;
        s.seenRestores = s.restores;
        sessions.set(p, s);
        order.push(p);
        found = p;
      }
      if (found && !(pinned && norm(found) !== norm(pinned))) events.push({ kind: "precompact", path: found });
    } catch {}
  }
  push(events);
}

function push(events = []) {
  if (!win || win.isDestroyed()) return;
  win.webContents.send("state", {
    sessions: order.map((p) => sessions.get(p)?.snapshot()).filter(Boolean),
    order, newest, live: [...live], cfg, system: system(), events,
  });
}

function rescan() {
  liveAt = 0;
  sessions.clear();
  order = [];
  refresh();
}

// --- window ---
function anchor() {
  const d = cfg.desktop || {};
  if (d.right != null && d.bottom != null) return [d.right, d.bottom];
  const wa = screen.getPrimaryDisplay().workArea;
  return [wa.x + wa.width - 24, wa.y + wa.height - 24];
}

// Where a w x h card goes: bottom-right corner at the anchor, but always wholly inside the work area of
// the display nearest to it, so a removed or rearranged monitor can't strand it off-screen.
function placement(w, h) {
  return fitInside(anchor(), w, h, screen.getAllDisplays().map((d) => d.workArea));
}

function replace() {
  if (!win || drag) return;
  const [w, h] = win.getSize();
  win.setBounds(placement(w, h));
}

function createWindow() {
  win = new BrowserWindow({
    // Opaque with Windows 11's own rounded corners and shadow: a transparent window would be composited on the
    // CPU every frame.
    width: 300, height: 420, show: false, frame: false, transparent: false, roundedCorners: true, hasShadow: true,
    resizable: false, maximizable: false, fullscreenable: false, skipTaskbar: true, alwaysOnTop: !!cfg.topmost,
    title: "Context Bonsai", backgroundColor: "#1A201F", icon: path.join(__dirname, "..", "..", "widget", "bonsai.ico"),
    webPreferences: { preload: path.join(__dirname, "preload.js"), contextIsolation: true, nodeIntegration: false },
  });
  win.loadFile(path.join(__dirname, "..", "index.html"));
  if (DEV) win.webContents.openDevTools({ mode: "detach" });
  win.on("closed", () => app.quit());
}

ipcMain.on("ready", () => refresh());

// The card keeps its bottom-right corner fixed, so switching views grows it up and to the left.
ipcMain.on("resize", (_, w, h) => {
  if (!win || drag) return;
  win.setBounds(placement(Math.ceil(w), Math.ceil(h)));
  if (!win.isVisible()) win.showInactive();
});

ipcMain.on("drag-start", () => {
  if (!win || drag) return;
  const c = screen.getCursorScreenPoint();
  const [x, y] = win.getPosition();
  const [w, h] = win.getSize();
  drag = { dx: c.x - x, dy: c.y - y, w, h };
  drag.timer = setInterval(() => {
    const p = screen.getCursorScreenPoint();
    win.setBounds({ x: p.x - drag.dx, y: p.y - drag.dy, width: drag.w, height: drag.h });
  }, 8);
});

ipcMain.on("drag-end", () => {
  if (!drag) return;
  clearInterval(drag.timer);
  drag = null;
  const [x, y] = win.getPosition();
  const [w, h] = win.getSize();
  cfg.desktop = { right: x + w, bottom: y + h };
  saveConfig("desktop");
  replace(); // dropped partly off-screen: pull it back in
});

ipcMain.on("background", (_, color) => win?.setBackgroundColor(color));

ipcMain.on("focus", (_, p) => {
  if (p === focusPath) return;
  focusPath = p;
  const s = sessions.get(p);
  if (s) {
    s.gitAt = 0; // fetch branch/changes for the card now
    s.refresh({ git: true, window: cfg.window });
  }
});

// Copy /compact and bring the Claude desktop app forward, so it's one paste away.
ipcMain.handle("compact", () => {
  clipboard.writeText("/compact");
  return new Promise((resolve) => {
    execFile("powershell", ["-NoProfile", "-Command", "(New-Object -ComObject WScript.Shell).AppActivate('Claude')"],
      { windowsHide: true, timeout: 4000 }, (err, out) => resolve(!err && /True/i.test(out || "")));
  });
});

const command = (cmd, value) => win?.webContents.send("command", { cmd, value });

ipcMain.on("menu", (_, info) => {
  const set = (k, v) => { cfg[k] = v; saveConfig(k); push(); };
  const themeLabel = (n) => ({ Auto: "Auto (follows Windows)", Seasons: "Seasons (changes with the date)" })[n] || n;
  const themes = themeItems((n) => cfg.theme === n, (n) => set("theme", n), themeLabel);
  const template = [
    { label: "Keep on top", type: "checkbox", checked: !!cfg.topmost,
      click: (m) => { set("topmost", m.checked); win.setAlwaysOnTop(m.checked); } },
    { label: "Pin this session", type: "checkbox", checked: !!info.focusPath && cfg.pinned === info.focusPath,
      enabled: !!info.focusPath, click: (m) => set("pinned", m.checked ? info.focusPath : null) },
    { label: "Theme", submenu: themes },
  ];
  if (info.focusName) { // a theme just for this session's project
    const key = info.focusName.toLowerCase();
    const per = cfg.project_themes || {};
    const pick = (n) => {
      const next = { ...per };
      if (n) next[key] = n;
      else delete next[key];
      set("project_themes", next);
    };
    template.push({ label: `Theme for ${info.focusName.length > 28 ? info.focusName.slice(0, 27) + "…" : info.focusName}`,
      submenu: [{ label: "Same as the widget", type: "radio", checked: !per[key], click: () => pick(null) },
        { type: "separator" },
        ...themeItems((n) => per[key] === n, pick)] });
  }
  template.push(
    { label: "View", submenu: [
      { label: "Focus (one session)", type: "radio", checked: info.view === "focus", click: () => command("view", "focus") },
      { label: info.count > 1 ? "Grove (every active session)" : "Grove (only one session active)", type: "radio",
        checked: info.view === "grove", enabled: info.count > 1, click: () => command("view", "grove") },
    ] },
    { label: "Zen mode", type: "checkbox", checked: !!cfg.zen, click: (m) => set("zen", m.checked) },
    { label: "Ambient animation", type: "checkbox", checked: cfg.ambient !== false, click: (m) => set("ambient", m.checked) },
    { label: "Rescan sessions", click: () => { rescan(); command("rescanned", order.length); } },
  );
  if (info.view === "focus" && (info.phase === "idle" || info.phase === "armed")) {
    template.push({ label: info.phase === "armed" ? "Cancel compact" : "Compact", click: () => command("compact") });
  }
  template.push({ type: "separator" }, { label: "Preview compact animation", click: () => command("preview") });
  if (DEV) template.push({ label: "Developer tools", click: () => win.webContents.openDevTools({ mode: "detach" }) });
  template.push({ label: "Quit", click: () => app.quit() });
  Menu.buildFromTemplate(template).popup({ window: win });
});

ipcMain.on("toggle-zen", () => {
  cfg.zen = !cfg.zen;
  saveConfig("zen");
  push();
});

if (!app.requestSingleInstanceLock()) {
  app.quit(); // already running: launching again toggles it off
} else {
  app.on("second-instance", () => app.quit());
  app.whenReady().then(() => {
    createWindow();
    setupDev(app, win, { command, setZen: (on) => { cfg.zen = on; push(); } });
    setInterval(refresh, POLL_MS);
    nativeTheme.on("updated", () => push());
    for (const e of ["display-added", "display-removed", "display-metrics-changed"]) screen.on(e, replace);
    // nothing to see on a locked screen: stop drawing until it unlocks
    powerMonitor.on("lock-screen", () => win?.webContents.send("pause", true));
    powerMonitor.on("unlock-screen", () => win?.webContents.send("pause", false));
    systemPreferences.on?.("accent-color-changed", () => push());
  });
  app.on("window-all-closed", () => app.quit());
}
