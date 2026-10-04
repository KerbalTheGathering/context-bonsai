// Themes are data: a palette, leaf color stops, and a `style` that picks how the scene is drawn.
// Palettes match the Tk widget's so a session looks the same in both. Leaf stops run from
// "plenty of room" to "compact now": [context fill, hue, saturation %, lightness %].
//
// `style` is the hook for whole looks beyond color. "diorama" is the living bonsai scene;
// styles live in src/styles.js: "glass" (frosted panes over an aurora) and "ink" (sumi-e on washi).

const THEMES = {
  Moss: {
    style: "diorama",
    colors: {
      panel: "#1A201F", wall: "#151A19", wall2: "#1D2422", ink: "#E3E7E0", muted: "#9AA39B",
      line: "#2F3835", pot: "#4E8990", potDark: "#33616A", potHi: "#78AEB4", wood: "#7A5A40",
      woodDark: "#59402D", soil: "#2A221C", moss: "#5E7A40", bark: "#7A6552", barkHi: "#9C8469",
      ok: "#8DBA6E", warn: "#E0A94A", crit: "#E7795A", glow: "#FFE7B0",
    },
    stops: [[0, 102, 46, 53], [0.5, 118, 42, 44], [0.7, 128, 38, 38], [0.8, 52, 68, 52],
      [0.9, 26, 72, 51], [1.0, 8, 64, 45]],
  },
  Paper: {
    style: "diorama",
    colors: {
      panel: "#EEF0E9", wall: "#E6E8E1", wall2: "#D6DACF", ink: "#1E2420", muted: "#5B645D",
      line: "#C3C9BD", pot: "#3C6A70", potDark: "#2A4D52", potHi: "#5E8F94", wood: "#6B4A33",
      woodDark: "#4C3423", soil: "#3A2E25", moss: "#6E8A4C", bark: "#4A3A2E", barkHi: "#6D5643",
      ok: "#4F7A3A", warn: "#A8701A", crit: "#B0472B", glow: "#FFF4D6",
    },
    stops: [[0, 102, 46, 46], [0.5, 118, 42, 37], [0.7, 128, 38, 31], [0.8, 52, 68, 45],
      [0.9, 26, 72, 44], [1.0, 8, 64, 38]],
  },
  Sakura: {
    style: "diorama",
    colors: {
      panel: "#221923", wall: "#1E1620", wall2: "#2A1E2B", ink: "#F3E6EC", muted: "#B39CAA",
      line: "#3D2D3D", pot: "#33466A", potDark: "#22304C", potHi: "#6680B0", wood: "#5A3B3A",
      woodDark: "#3E2726", soil: "#2A1E1E", moss: "#5F6E45", bark: "#5E444B", barkHi: "#80616A",
      ok: "#F2A7C3", warn: "#F07FA8", crit: "#E8506F", glow: "#FFD6E6",
    },
    stops: [[0, 340, 75, 90], [0.5, 336, 72, 83], [0.7, 332, 74, 75], [0.8, 330, 76, 66],
      [0.9, 342, 78, 56], [1.0, 350, 76, 48]],
  },
  Midnight: {
    style: "diorama",
    colors: {
      panel: "#0F172A", wall: "#0B1222", wall2: "#141E33", ink: "#E2E8F5", muted: "#8C9AB5",
      line: "#24304A", pot: "#3B4A6B", potDark: "#283552", potHi: "#6F86B8", wood: "#3A3F55",
      woodDark: "#262B3D", soil: "#151A26", moss: "#2F5A5A", bark: "#58637D", barkHi: "#7D8AA6",
      ok: "#5EE0C8", warn: "#F5C062", crit: "#FF6B7A", glow: "#9FE8FF",
    },
    stops: [[0, 166, 72, 58], [0.5, 174, 66, 50], [0.7, 188, 60, 46], [0.8, 42, 85, 60],
      [0.9, 20, 90, 60], [1.0, 355, 85, 62]],
  },
  // --- ink style: sumi-e on washi paper ---
  "Sumi-e": {
    style: "ink",
    colors: {
      panel: "#F4EEE1", wall: "#F1EADB", wall2: "#E6DCC6", ink: "#1C1A17", muted: "#6E675C",
      line: "#D3C8B1", pot: "#3A3835", potDark: "#22211F", potHi: "#6B6862", wood: "#8B7355",
      woodDark: "#6A5640", soil: "#2E2A25", moss: "#7D8463", bark: "#24221F", barkHi: "#4A4640",
      ok: "#3F4A3A", warn: "#9A6A2E", crit: "#B8322A", glow: "#FFF1D0", seal: "#B8322A",
    },
    stops: [[0, 95, 14, 42], [0.5, 100, 10, 30], [0.7, 110, 8, 22], [0.8, 28, 32, 30],
      [0.9, 10, 62, 40], [1.0, 4, 72, 42]],
  },
  "Night Ink": { // pale ink on charcoal paper
    style: "ink",
    colors: {
      panel: "#1E1C1A", wall: "#23211E", wall2: "#1B1A18", ink: "#ECE6DA", muted: "#9B9486",
      line: "#3A3732", pot: "#D8D0C0", potDark: "#8C857A", potHi: "#F4EEE1", wood: "#6A5640",
      woodDark: "#4A3C2E", soil: "#3A3732", moss: "#8C947A", bark: "#E4DCCD", barkHi: "#FFFFFF",
      ok: "#C9D4B8", warn: "#E0A94A", crit: "#E2553F", glow: "#FFF1D0", seal: "#C8402F",
    },
    stops: [[0, 60, 10, 80], [0.5, 70, 8, 70], [0.7, 80, 6, 60], [0.8, 30, 34, 62],
      [0.9, 14, 62, 58], [1.0, 6, 72, 55]],
  },
  // --- glass style: frosted panes over an aurora, glowing foliage ---
  Aurora: {
    style: "glass",
    colors: {
      panel: "#0E1024", wall: "#090B1A", wall2: "#141938", ink: "#EEF2FF", muted: "#9AA3C7",
      line: "#2A3160", pot: "#7FDBFF", potDark: "#2B3A7A", potHi: "#C9F2FF", wood: "#3A3F7A",
      woodDark: "#262B55", soil: "#1A1F45", moss: "#3BE3B5", bark: "#B9B2F0", barkHi: "#FFFFFF",
      ok: "#5CF2C2", warn: "#FFC85C", crit: "#FF5C9A", glow: "#8FB0FF",
      aurora: ["#4F7BFF", "#A64CFF", "#2FD6A8"],
    },
    stops: [[0, 160, 90, 60], [0.5, 188, 92, 62], [0.7, 228, 88, 70], [0.8, 282, 88, 70],
      [0.9, 318, 92, 66], [1.0, 342, 96, 64]],
  },
  Frost: {
    style: "glass",
    colors: {
      panel: "#F2F6FC", wall: "#E9F0FA", wall2: "#D6E3F4", ink: "#14203A", muted: "#5A6884",
      line: "#C3D0E2", pot: "#9CC2EE", potDark: "#4A6E9E", potHi: "#FFFFFF", wood: "#8EA2C4",
      woodDark: "#6F84A8", soil: "#7E93B8", moss: "#5FC9A6", bark: "#5E6F98", barkHi: "#FFFFFF",
      ok: "#16926E", warn: "#C77F12", crit: "#D23C6A", glow: "#FFFFFF",
      aurora: ["#8EC5FF", "#D7B0FF", "#9AF0D4"],
    },
    stops: [[0, 162, 62, 46], [0.5, 190, 66, 46], [0.7, 222, 64, 54], [0.8, 276, 60, 58],
      [0.9, 322, 66, 54], [1.0, 344, 72, 52]],
  },
  Canyon: {
    style: "diorama",
    colors: {
      panel: "#2A1D18", wall: "#2E1F19", wall2: "#3B2820", ink: "#F1E4D8", muted: "#B39A88",
      line: "#4A3429", pot: "#B5603A", potDark: "#8A4528", potHi: "#D88A63", wood: "#6E4E3A",
      woodDark: "#4E3628", soil: "#2B1C15", moss: "#6F7A4A", bark: "#8A6A55", barkHi: "#A88468",
      ok: "#A3B86C", warn: "#E2A04A", crit: "#E06A4A", glow: "#FFC98A",
    },
    stops: [[0, 100, 30, 46], [0.5, 92, 22, 52], [0.7, 70, 22, 56], [0.8, 38, 52, 52],
      [0.9, 22, 64, 48], [1.0, 10, 68, 44]],
  },
  Clay: {
    style: "diorama",
    colors: {
      panel: "#F5EFE6", wall: "#F2EADF", wall2: "#E7DCCB", ink: "#2B2420", muted: "#7A6D62",
      line: "#DCCFBD", pot: "#C96442", potDark: "#9E4A30", potHi: "#E08A6C", wood: "#8B6B4E",
      woodDark: "#6B5038", soil: "#3B2E25", moss: "#7E8A55", bark: "#5C4636", barkHi: "#7D6250",
      ok: "#5E7D3A", warn: "#B7791F", crit: "#B5452E", glow: "#FFE6C4",
    },
    stops: [[0, 82, 34, 42], [0.5, 88, 30, 35], [0.7, 96, 26, 30], [0.8, 40, 58, 44],
      [0.9, 22, 66, 44], [1.0, 12, 68, 40]],
  },
  Neon: {
    style: "diorama",
    colors: {
      panel: "#140E24", wall: "#120B22", wall2: "#1E1336", ink: "#F2E9FF", muted: "#A08BC8",
      line: "#2E2350", pot: "#2B1F55", potDark: "#1C143A", potHi: "#7B5CFF", wood: "#2A2245",
      woodDark: "#1B1630", soil: "#120D1F", moss: "#3B2A6B", bark: "#6B5B9A", barkHi: "#8F7FD0",
      ok: "#4DF0FF", warn: "#FFD84D", crit: "#FF4D8D", glow: "#B98CFF",
    },
    stops: [[0, 186, 95, 60], [0.5, 205, 90, 62], [0.7, 268, 88, 68], [0.8, 305, 90, 64],
      [0.9, 332, 95, 62], [1.0, 350, 95, 60]],
  },
  Pixel: {
    style: "diorama",
    pixel: true, // drawn at low resolution and scaled up without smoothing
    colors: {
      panel: "#1A201F", wall: "#151A19", wall2: "#1D2422", ink: "#E3E7E0", muted: "#9AA39B",
      line: "#2F3835", pot: "#4E8990", potDark: "#33616A", potHi: "#78AEB4", wood: "#7A5A40",
      woodDark: "#59402D", soil: "#2A221C", moss: "#5E7A40", bark: "#7A6552", barkHi: "#9C8469",
      ok: "#8DBA6E", warn: "#E0A94A", crit: "#E7795A", glow: "#FFE7B0",
    },
    stops: [[0, 104, 52, 52], [0.5, 120, 48, 42], [0.7, 130, 44, 36], [0.8, 52, 74, 52],
      [0.9, 26, 78, 50], [1.0, 8, 70, 46]],
  },
};

// Virtual themes resolve to a real palette when applied.
const SEASONS = { 12: "Midnight", 1: "Midnight", 2: "Midnight", 3: "Sakura", 4: "Sakura", 5: "Sakura",
  6: "Moss", 7: "Moss", 8: "Moss", 9: "Canyon", 10: "Canyon", 11: "Canyon" };
const THEME_NAMES = ["Auto", "Seasons", ...Object.keys(THEMES)];

function shade(hex, factor) {
  const h = hex.replace("#", "");
  let c = [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16));
  c = c.map((v) => (factor >= 1 ? Math.round(v + (255 - v) * (factor - 1)) : Math.round(v * factor)));
  return "#" + c.map((v) => Math.min(255, Math.max(0, v)).toString(16).padStart(2, "0")).join("").toUpperCase();
}

// Windows 11 neutrals with the system accent on the pot.
function fluentTheme(light, accent) {
  const base = THEMES[light ? "Paper" : "Moss"];
  const colors = light
    ? { panel: "#F3F3F3", wall: "#FAFAFA", wall2: "#EAEAEA", ink: "#1B1B1B", muted: "#5F5F5F", line: "#D5D5D5",
      ok: "#0F7B0F", warn: "#9D5D00", crit: "#C42B1C", glow: "#FFF4D6" }
    : { panel: "#202020", wall: "#1C1C1C", wall2: "#2B2B2B", ink: "#FFFFFF", muted: "#A0A0A0", line: "#3A3A3A",
      ok: "#6CCB5F", warn: "#FCE100", crit: "#FF99A4", glow: "#FFE7B0" };
  for (const k of ["wood", "woodDark", "soil", "moss", "bark", "barkHi"]) colors[k] = base.colors[k];
  Object.assign(colors, { pot: accent, potDark: shade(accent, 0.7), potHi: shade(accent, 1.35) });
  return { style: "diorama", colors, stops: base.stops };
}

// name -> { key, style, colors, stops, pixel, light }. `system` = { light, accent } from the OS.
function resolveTheme(name, system = { light: false, accent: "#0078D4" }, date = new Date()) {
  let key, theme;
  if (name === "Auto") {
    key = `Auto-${system.light ? "light" : "dark"}-${system.accent}`;
    theme = fluentTheme(system.light, system.accent);
  } else {
    const real = name === "Seasons" ? SEASONS[date.getMonth() + 1] : name;
    key = THEMES[real] ? real : "Moss";
    theme = THEMES[key];
  }
  return { key, ...theme, light: isLight(theme.colors.panel) };
}

function isLight(hex) {
  const h = hex.replace("#", "");
  const [r, g, b] = [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16));
  return 0.299 * r + 0.587 * g + 0.114 * b > 140;
}

module.exports = { THEMES, THEME_NAMES, SEASONS, resolveTheme, shade, isLight };
