// Session data: a Node port of the Tk widget's Stats/Session readers. Reads transcripts in
// ~/.claude/projects incrementally (only what was appended), the open-session registry in
// ~/.claude/sessions, git state and background jobs. No model calls, no usage.
const fs = require("fs");
const os = require("os");
const path = require("path");
const { execFile } = require("child_process");

const HOME = os.homedir();
const PROJECTS = path.join(HOME, ".claude", "projects");
const SESSIONS = path.join(HOME, ".claude", "sessions");
const BASELINE = 0.14;
const EDIT_TOOLS = new Set(["Edit", "Write", "MultiEdit", "NotebookEdit"]);

const norm = (p) => path.normalize(p || "").toLowerCase();

function listDir(dir) {
  try {
    return fs.readdirSync(dir, { withFileTypes: true });
  } catch {
    return [];
  }
}

// Every transcript with its mtime, newest first.
function allTranscripts() {
  const out = [];
  for (const d of listDir(PROJECTS)) {
    if (!d.isDirectory()) continue;
    const dir = path.join(PROJECTS, d.name);
    for (const f of listDir(dir)) {
      if (!f.isFile() || !f.name.endsWith(".jsonl")) continue;
      const p = path.join(dir, f.name);
      try {
        out.push({ path: p, mtime: fs.statSync(p).mtimeMs / 1000 });
      } catch {}
    }
  }
  return out.sort((a, b) => b.mtime - a.mtime);
}

function alive(pid) {
  try {
    process.kill(pid, 0);
    return true;
  } catch (e) {
    return e.code === "EPERM"; // exists, just not ours to signal
  }
}

// Transcripts of the Claude Code sessions open right now, from ~/.claude/sessions/<pid>.json.
function openTranscripts(all) {
  const byId = new Map(all.map((t) => [path.basename(t.path, ".jsonl").toLowerCase(), t.path]));
  const found = new Set();
  for (const f of listDir(SESSIONS)) {
    if (!f.name.endsWith(".json")) continue;
    try {
      const d = JSON.parse(fs.readFileSync(path.join(SESSIONS, f.name), "utf8"));
      if (!d.sessionId || !d.pid || !alive(d.pid)) continue;
      const p = byId.get(String(d.sessionId).toLowerCase());
      if (p) found.add(norm(p));
    } catch {}
  }
  return found;
}

function parseTs(ts) {
  const t = Date.parse(ts);
  return Number.isNaN(t) ? null : t / 1000;
}

function cleanTitle(t) {
  if (!t) return null;
  const keep = [...t].filter((ch) => {
    const c = ch.codePointAt(0);
    return c < 0x2190 || (c >= 0x2e80 && c < 0x1f000);
  }).join("");
  return keep.split(/\s+/).filter(Boolean).join(" ") || null;
}

class Stats {
  constructor() {
    this.usage = new Map(); // message id -> usage (a message's content blocks share one id)
    this.toolIds = new Set();
    this.tools = 0;
    this.byTool = {};
    this.errors = 0;
    this.files = new Set();
    this.prompts = 0;
    this.lastPrompt = null;
    this.subagents = 0;
    this.started = null;
  }

  add(d) {
    const ts = parseTs(d.timestamp);
    if (ts && this.started == null) this.started = ts;
    const m = d.message || {};
    const content = m.content;
    if (d.type === "assistant") {
      if (m.id && m.usage) this.usage.set(m.id, m.usage);
      for (const c of Array.isArray(content) ? content : []) {
        if (!c || c.type !== "tool_use" || this.toolIds.has(c.id)) continue;
        this.toolIds.add(c.id);
        const name = c.name || "?";
        this.tools++;
        this.byTool[name] = (this.byTool[name] || 0) + 1;
        if (name === "Agent" || name === "Task") this.subagents++;
        const inp = c.input || {};
        const fp = inp.file_path || inp.notebook_path;
        if (fp && EDIT_TOOLS.has(name)) this.files.add(norm(fp));
      }
    } else if (d.type === "user" && !d.isMeta && !d.isCompactSummary) {
      let texts;
      if (typeof content === "string") texts = [content];
      else {
        const blocks = (content || []).filter((c) => c && typeof c === "object");
        this.errors += blocks.filter((c) => c.type === "tool_result" && c.is_error).length;
        if (blocks.some((c) => c.type === "tool_result")) return;
        texts = blocks.filter((c) => c.type === "text").map((c) => c.text || "");
      }
      // a real prompt has some text that isn't a command echo, caveat or system note
      if (texts.some((t) => t.trim() && !t.trimStart().startsWith("<"))) {
        this.prompts++;
        this.lastPrompt = ts || this.lastPrompt;
      }
    }
  }

  totals() {
    let inp = 0, cread = 0, cwrite = 0, out = 0, peak = 0;
    const series = [];
    for (const u of this.usage.values()) {
      const i = u.input_tokens || 0, r = u.cache_read_input_tokens || 0, w = u.cache_creation_input_tokens || 0;
      inp += i; cread += r; cwrite += w;
      out += u.output_tokens || 0;
      peak = Math.max(peak, i + r + w);
      series.push(i + r + w);
    }
    const total = inp + cread + cwrite;
    return {
      cache: total ? cread / total : null, out, peak, calls: this.usage.size, series,
      avg: series.length ? total / series.length : 0, total: total + out,
    };
  }
}

class Session {
  constructor(file) {
    this.path = file;
    this.offset = 0;
    this.partial = Buffer.alloc(0);
    this.title = null;
    this.stats = new Stats();
    this.compactions = 0;
    this.lastPre = null;
    this.lastDuration = null;
    this.restores = 0;
    this.restoredMsg = null;
    this.cwd = null;
    this.tokens = null;
    this.afterCompact = false;
    this.mtime = 0;
    this.jobs = [];
    this.launched = new Map(); // background task id -> launching tool_use id
    this.finished = new Set();
    this.jobDesc = new Map(); // tool_use id -> description
    this.git = [null, null];
    this.gitAt = 0;
    this.gitBusy = false;
  }

  get name() {
    return this.cwd ? path.basename(path.normalize(this.cwd)) : "session";
  }

  get g() {
    if (this.afterCompact || this.tokens == null) return this.afterCompact ? BASELINE : 0.06;
    return Math.min(1, Math.max(0, this.tokens / this.window));
  }

  // Returns true when the data changed.
  refresh({ git = true, window = 1_000_000 } = {}) {
    this.window = window;
    let st;
    try {
      st = fs.statSync(this.path);
    } catch {
      return false;
    }
    const mtime = st.mtimeMs / 1000;
    let changed = mtime !== this.mtime;
    if (changed) {
      this.mtime = mtime;
      const rewritten = st.size < this.offset;
      if (rewritten) this.reset(mtime);
      this.scanNew(st.size);
      this.readTokens(st.size);
      if (rewritten && this.seenCc !== undefined) { // what was already shown isn't news
        this.seenCc = this.compactions;
        this.seenRestores = this.restores;
      }
      this.jobs = [...this.launched].filter(([tid]) => !this.finished.has(tid))
        .map(([tid, tuid]) => ({ id: tid, desc: this.jobDesc.get(tuid) || "" }));
    }
    if (git && this.cwd && !this.gitBusy && Date.now() / 1000 - this.gitAt > 10) {
      this.gitAt = Date.now() / 1000;
      this.gitBusy = true;
      gitState(this.cwd).then((g) => {
        this.gitBusy = false;
        if (g[0] !== this.git[0] || g[1] !== this.git[1]) {
          this.git = g;
          this.onChange?.();
        }
      });
    }
    return changed;
  }

  // The file was rewritten (it shrank): start over, keeping who's listening.
  reset(mtime) {
    const keep = { onChange: this.onChange, seenCc: this.seenCc, seenRestores: this.seenRestores, window: this.window };
    Object.assign(this, new Session(this.path), keep, { mtime });
  }

  // Count compactions, gather stats and the cwd, reading only what was appended since last time.
  scanNew(size) {
    if (size <= this.offset) return;
    let chunk;
    try {
      const fd = fs.openSync(this.path, "r");
      chunk = Buffer.alloc(size - this.offset);
      fs.readSync(fd, chunk, 0, chunk.length, this.offset);
      fs.closeSync(fd);
    } catch {
      return;
    }
    const end = chunk.lastIndexOf(0x0a);
    if (end < 0) return;
    this.offset += end + 1;
    for (const raw of chunk.subarray(0, end).toString("utf8").split("\n")) this.line(raw);
  }

  line(raw) {
    const has = (s) => raw.includes(s);
    let d;
    const parse = () => {
      if (d === undefined) {
        try {
          d = JSON.parse(raw);
        } catch {
          d = null;
        }
      }
      return d;
    };
    if (has('"compact_boundary"')) {
      this.compactions++;
      const meta = parse()?.compactMetadata || {};
      this.lastPre = meta.preTokens ?? null;
      this.lastDuration = (meta.durationMs || 0) / 1000 || null;
    }
    if ((has('"type":"assistant"') || has('"type":"user"')) && parse() && !d.isSidechain) this.stats.add(d);
    if (has('"custom-title"') && parse()) this.title = cleanTitle(d.customTitle);
    if (has('"hook_system_message"') && has("restored:") && parse()) {
      this.restoredMsg = d.attachment?.content ?? null;
      this.restores++;
    }
    if (has('"cwd"') && parse()) this.cwd = d.cwd || this.cwd;
    this.jobLine(raw, parse);
  }

  // Background Bash/PowerShell commands launched with no completion seen yet (port of rehydrate.running_jobs),
  // tracked line by line as the transcript grows.
  jobLine(raw, parse) {
    if (raw.includes("<task-notification>")) { // completions arrive as queue-operation/attachment entries
      for (const block of raw.split("<task-notification>").slice(1)) {
        if (block.includes("<status>")) for (const m of block.matchAll(TASK_ID)) this.finished.add(m[1]);
      }
      return;
    }
    const d = BG_LAUNCH.test(raw) || raw.includes('"backgroundTaskId"') || raw.includes('"TaskStop"') ? parse() : null;
    if (!d) return;
    const content = Array.isArray(d.message?.content) ? d.message.content : [];
    if (BG_LAUNCH.test(raw)) {
      for (const c of content) {
        if (c?.type === "tool_use") this.jobDesc.set(c.id, c.input?.description || (c.input?.command || "").slice(0, 80));
      }
    } else if (raw.includes('"backgroundTaskId"')) {
      const r = d.toolUseResult;
      if (r && typeof r === "object" && r.backgroundTaskId) {
        this.launched.set(r.backgroundTaskId, content.find((c) => c?.type === "tool_result")?.tool_use_id);
      }
    } else {
      for (const c of content) if (c?.name === "TaskStop") this.finished.add(c.input?.task_id || c.input?.shell_id);
    }
  }

  // Newest context size. Image tool results can be hundreds of KB, so widen the tail if needed.
  readTokens(size) {
    for (const span of [600_000, 6_000_000, Infinity]) {
      let text;
      try {
        const start = Math.max(0, size - span);
        const fd = fs.openSync(this.path, "r");
        const buf = Buffer.alloc(size - start);
        fs.readSync(fd, buf, 0, buf.length, start);
        fs.closeSync(fd);
        text = buf.toString("utf8");
      } catch {
        return;
      }
      if (this.tokensFrom(text.split("\n")) || span >= size) return;
    }
  }

  tokensFrom(lines) {
    this.afterCompact = false;
    for (let i = lines.length - 1; i >= 0; i--) {
      const line = lines[i];
      if (line.includes('"compact_boundary"')) {
        this.afterCompact = true; // no reply since the compact yet
        this.tokens = null;
        return true;
      }
      if (!line.includes('"usage"') || line.includes('"isSidechain":true')) continue;
      let u;
      try {
        u = JSON.parse(line).message?.usage;
      } catch {
        continue;
      }
      if (u) {
        this.tokens = (u.input_tokens || 0) + (u.cache_read_input_tokens || 0) + (u.cache_creation_input_tokens || 0);
        return true;
      }
    }
    return false;
  }

  snapshot() {
    const st = this.stats;
    return {
      path: this.path, id: path.basename(this.path), title: this.title, name: this.name, cwd: this.cwd,
      g: this.g, tokens: this.tokens, afterCompact: this.afterCompact, compactions: this.compactions,
      restores: this.restores, restoredMsg: this.restoredMsg, lastDuration: this.lastDuration,
      mtime: this.mtime, git: this.git, jobs: this.jobs.map((j) => ({ ...j, ...jobOutput(this.path, j.id) })),
      stats: {
        ...st.totals(), tools: st.tools, errors: st.errors, files: st.files.size, prompts: st.prompts,
        lastPrompt: st.lastPrompt, started: st.started, subagents: st.subagents,
      },
    };
  }
}

function gitState(cwd) {
  const run = (args) => new Promise((res) => {
    execFile("git", args, { cwd, timeout: 2000, windowsHide: true }, (err, out) => res(err ? null : out));
  });
  return run(["branch", "--show-current"]).then(async (br) => {
    if (br == null) return [null, null];
    const st = (await run(["status", "--porcelain"])) || "";
    return [br.trim() || "detached", st.split("\n").filter((l) => l.trim()).length];
  });
}

const ANSI = /\x1b\[[0-9;?]*[A-Za-z]/g;
const TAIL_BYTES = 4096;

// A background job's output file (where Claude Code writes it, as the rehydrate hook finds it), its last
// non-empty line and how long ago it was written.
function jobOutput(transcript, taskId) {
  const proj = path.basename(path.dirname(transcript));
  const root = path.join(os.tmpdir(), "claude", proj);
  for (const d of listDir(root)) {
    const out = path.join(root, d.name, "tasks", `${taskId}.output`);
    let st;
    try {
      st = fs.statSync(out);
    } catch {
      continue;
    }
    let tail = "";
    try {
      const fd = fs.openSync(out, "r");
      const start = Math.max(0, st.size - TAIL_BYTES);
      const buf = Buffer.alloc(st.size - start);
      fs.readSync(fd, buf, 0, buf.length, start);
      fs.closeSync(fd);
      tail = buf.toString("utf8").replace(ANSI, "");
    } catch {}
    const lines = tail.split(/[\r\n]+/).map((l) => l.trim()).filter(Boolean);
    return { out, last: (lines[lines.length - 1] || "").slice(0, 160), age: Math.max(0, Date.now() / 1000 - st.mtimeMs / 1000) }; // file times can run a hair ahead of the clock
  }
  return { out: null, last: "", age: null };
}

const BG_LAUNCH = /"run_in_background":\s*true/;
const TASK_ID = /<task-id>([^<]+)<\/task-id>/g;

module.exports = { Session, allTranscripts, openTranscripts, jobOutput, norm, PROJECTS, BASELINE };
