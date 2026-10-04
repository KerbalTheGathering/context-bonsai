export const fmtK = (t) => (t >= 1e6 ? `${+(t / 1e6).toPrecision(2)}M` : `${Math.round(t / 1000)}k`);
export const fmtTok = (t) => (t >= 1e6 ? `${(t / 1e6).toFixed(1)}M` : `${Math.round(t / 1000)}k`);
export const plural = (n, word) => (n === 1 ? word : `${word}s`);

export function fmtDur(sec) {
  const m = Math.floor(sec / 60);
  if (m < 1) return "<1m";
  if (m < 60) return `${m}m`;
  if (m < 48 * 60) return `${Math.floor(m / 60)}h ${m % 60}m`;
  return `${Math.floor(m / 1440)}d ${Math.floor((m % 1440) / 60)}h`;
}

export function fmtAgo(sec) {
  if (sec < 60) return "live";
  if (sec < 3600) return `idle ${Math.floor(sec / 60)}m`;
  return `idle ${Math.round(sec / 3600)}h`;
}

// How long ago a job last wrote output (as the rehydrate hook says it).
export function fmtAge(sec) {
  if (sec < 90) return `${Math.floor(sec)}s ago`;
  if (sec < 5400) return `${Math.floor(sec / 60)}m ago`;
  return `${(sec / 3600).toFixed(1)}h ago`;
}

export const nowSec = () => Date.now() / 1000;
