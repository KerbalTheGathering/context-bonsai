// The renderer's only window onto the main process.
const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("bonsai", {
  onState: (cb) => ipcRenderer.on("state", (_, s) => cb(s)),
  onCommand: (cb) => ipcRenderer.on("command", (_, c) => cb(c)),
  ready: () => ipcRenderer.send("ready"),
  resize: (w, h) => ipcRenderer.send("resize", w, h),
  dragStart: () => ipcRenderer.send("drag-start"),
  dragEnd: () => ipcRenderer.send("drag-end"),
  menu: (info) => ipcRenderer.send("menu", info),
  compact: () => ipcRenderer.invoke("compact"),
  setFocus: (p) => ipcRenderer.send("focus", p),
  setBackground: (color) => ipcRenderer.send("background", color),
  toggleZen: () => ipcRenderer.send("toggle-zen"),
});
