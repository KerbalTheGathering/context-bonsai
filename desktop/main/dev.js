// Dev aids, switched on by environment variables. None of them save settings.
//   BONSAI_SHOTS=<dir>  walk the views and the compaction preview, saving a PNG per step, then quit
//   BONSAI_PROBE=<dir>  log the renderer's console (with a frame-rate line every 2s) to <dir>/console.log
//   BONSAI_LEAK=<file>  create and destroy 40 scenes, write GPU texture counts before/after, then quit
//   BONSAI_DPI=<file>   zoom to 150% (a stand-in for a higher-DPI monitor), write the renderer's resolution, quit
//   BONSAI_FPS=<n>      pin the frame rate (to measure what a frame rate costs)
//   BONSAI_HOUR=<h>     pin the clock's hour (e.g. 23 for a night scene)
// (BONSAI_THEME and BONSAI_CFG, unsaved setting overrides, are read where the config loads.)
const fs = require("fs");
const path = require("path");

const wait = (ms) => new Promise((r) => setTimeout(r, ms));

function setupDev(app, win, { command, setZen }) {
  const env = process.env;
  const js = (code) => win.webContents.executeJavaScript(code);
  const loaded = new Promise((r) => win.webContents.once("did-finish-load", r));
  const run = (fn, out) => loaded.then(() => wait(4000)).then(fn).catch((e) => {
    fs.writeFileSync(out, String(e.stack || e));
  }).finally(() => app.quit());

  const logDir = env.BONSAI_SHOTS || env.BONSAI_PROBE;
  if (logDir) {
    const log = path.join(logDir, "console.log");
    fs.writeFileSync(log, "");
    win.webContents.on("console-message", (e) => fs.appendFileSync(log, `[${e.level}] ${e.message}\n`));
    win.webContents.on("did-finish-load", () => js("window.__probe = 1"));
  }
  if (env.BONSAI_FPS) win.webContents.on("did-finish-load", () => js(`window.__fpsCap = ${+env.BONSAI_FPS}`));
  if (env.BONSAI_HOUR) win.webContents.on("did-finish-load", () => js(`window.__hour = ${+env.BONSAI_HOUR}`));

  if (env.BONSAI_SHOTS) {
    const dir = env.BONSAI_SHOTS;
    const snap = async (name) => fs.writeFileSync(path.join(dir, name + ".png"), (await win.webContents.capturePage()).toPNG());
    run(async () => {
      await wait(1000);
      await snap("1-start");
      command("view", "grove");
      await wait(1500);
      await snap("2-grove");
      js("window.__bonsai?.grove.page(1)");
      await wait(250);
      await snap("3-grove-sliding");
      await wait(1200);
      await snap("4-grove-page2");
      command("view", "focus");
      await wait(1800);
      await snap("5-focus");
      command("preview");
      await wait(3000);
      await snap("6-compacting");
      await wait(2300);
      await snap("7-pruned");
      await wait(2600);
      await snap("8-watering");
      await wait(4000);
      await snap("9-restored");
      setZen(true);
      await wait(1200);
      await snap("10-zen-focus");
      command("view", "grove");
      await wait(1500);
      await snap("11-zen-grove");
      setZen(false);
    }, path.join(dir, "error.txt"));
  }

  if (env.BONSAI_LEAK) {
    run(async () => {
      const r = await js("window.__leakTest(40).catch((e) => ({ error: String(e.stack || e) }))");
      fs.writeFileSync(env.BONSAI_LEAK, JSON.stringify(r));
    }, env.BONSAI_LEAK);
  }

  if (env.BONSAI_DPI) {
    run(async () => {
      const read = () => js("({ dpr: devicePixelRatio, resolution: window.__bonsai.app.renderer.resolution })");
      const before = await read();
      win.webContents.setZoomFactor(1.5);
      await wait(1500);
      const after = await read();
      win.webContents.setZoomFactor(1);
      await wait(1500);
      const back = await read();
      fs.writeFileSync(env.BONSAI_DPI, JSON.stringify({ before, after, back }));
    }, env.BONSAI_DPI);
  }
}

module.exports = { setupDev };
