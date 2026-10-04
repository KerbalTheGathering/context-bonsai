// The transcript reader: tokens, stats, compactions, restores, titles, jobs, incremental reads.
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("fs");
const { Session } = require("../main/data.js");
const { line, usage, tmpTranscript, write } = require("./fixtures.js");

const WINDOW = { window: 1_000_000, git: false };

function basicSession() {
  return [
    line.title("Fix the 🌳 widget  layout"),
    line.prompt("hello there"),
    line.assistant("m1", usage(1000, 50_000, 2_000), [
      { type: "text", text: "on it" },
      line.toolUse("t1", "Edit", { file_path: "C:\\work\\demo\\a.js" }),
    ]),
    line.toolResult("t1"),
    line.assistant("m2", usage(500, 60_000, 0), [line.toolUse("t2", "Bash", { command: "npm test" })]),
    line.toolResult("t2", true),
    line.assistant("m3", usage(200, 70_000, 1_000), [line.toolUse("t3", "Agent", { prompt: "look" })]),
    line.toolResult("t3"),
    line.prompt("<command-name>/clear</command-name>"), // a command echo is not a prompt
    line.prompt("and another real one"),
  ];
}

test("reads tokens, title, cwd and stats", () => {
  const s = new Session(tmpTranscript(basicSession()));
  assert.equal(s.refresh(WINDOW), true);
  assert.equal(s.tokens, 200 + 70_000 + 1_000);
  assert.ok(Math.abs(s.g - 0.0712) < 1e-9);
  assert.equal(s.title, "Fix the widget layout", "emoji and doubled spaces dropped");
  assert.equal(s.cwd, "C:\\work\\demo");
  assert.equal(s.name, "demo");
  const st = s.snapshot().stats;
  assert.equal(st.prompts, 2);
  assert.equal(st.tools, 3);
  assert.equal(st.errors, 1);
  assert.equal(st.files, 1);
  assert.equal(st.subagents, 1);
  assert.equal(st.calls, 3);
  assert.deepEqual(st.series, [53_000, 60_500, 71_200]);
  assert.equal(st.peak, 71_200);
});

test("unchanged file reports no change", () => {
  const s = new Session(tmpTranscript(basicSession()));
  s.refresh(WINDOW);
  assert.equal(s.refresh(WINDOW), false);
});

test("reads only what was appended", () => {
  const file = tmpTranscript(basicSession());
  const s = new Session(file);
  s.refresh(WINDOW);
  const offset = s.offset;
  write(file, [line.prompt("more"), line.assistant("m4", usage(100, 90_000))], "a");
  fs.utimesSync(file, new Date(), new Date(Date.now() + 5000));
  assert.equal(s.refresh(WINDOW), true);
  assert.ok(s.offset > offset);
  assert.equal(s.tokens, 90_100);
  assert.equal(s.snapshot().stats.prompts, 3);
});

test("counts compactions and resets context until the next reply", () => {
  const file = tmpTranscript([...basicSession(), line.compact(71_200, 42_000)]);
  const s = new Session(file);
  s.refresh(WINDOW);
  assert.equal(s.compactions, 1);
  assert.equal(s.lastDuration, 42);
  assert.equal(s.afterCompact, true);
  assert.equal(s.tokens, null);
  assert.equal(s.g, 0.14, "baseline growth right after a compaction");
  write(file, [line.assistant("m5", usage(300, 20_000))], "a");
  fs.utimesSync(file, new Date(), new Date(Date.now() + 5000));
  s.refresh(WINDOW);
  assert.equal(s.afterCompact, false);
  assert.equal(s.tokens, 20_300);
});

test("ignores sidechain (subagent) usage for the context size", () => {
  const s = new Session(tmpTranscript([
    line.assistant("m1", usage(100, 10_000)),
    line.assistant("side", usage(5, 999_000), undefined, { isSidechain: true }),
  ]));
  s.refresh(WINDOW);
  assert.equal(s.tokens, 10_100);
  assert.equal(s.snapshot().stats.calls, 1);
});

test("counts restores from the rehydrate hook", () => {
  const s = new Session(tmpTranscript([line.restored("↻ restored: main@abc · 0 changed")]));
  s.refresh(WINDOW);
  assert.equal(s.restores, 1);
  assert.match(s.restoredMsg, /restored:/);
});

test("tracks background jobs until they finish or are stopped", () => {
  const launch = (id, desc) => line.assistant(`m-${id}`, usage(10, 0),
    [line.toolUse(id, "Bash", { command: "npm run dev", description: desc, run_in_background: true })]);
  const started = (toolId, taskId) => ({ ...line.toolResult(toolId), toolUseResult: { backgroundTaskId: taskId } });
  const file = tmpTranscript([
    launch("tu1", "dev server"), started("tu1", "bg1"),
    launch("tu2", "watcher"), started("tu2", "bg2"),
    launch("tu3", "tests"), started("tu3", "bg3"),
    line.notification("bg2"),
    line.assistant("m-stop", usage(10, 0), [line.toolUse("ts", "TaskStop", { task_id: "bg3" })]),
  ]);
  const s = new Session(file);
  s.refresh(WINDOW);
  assert.deepEqual(s.jobs, [{ id: "bg1", desc: "dev server" }]);
});

test("a rewritten (shorter) transcript is re-read from the start without firing stale events", { todo: "fixed in fix/correctness" }, () => {
  const file = tmpTranscript([...basicSession(), line.compact(1, 1)]);
  const s = new Session(file);
  s.refresh(WINDOW);
  s.seenCc = s.compactions;
  s.onChange = () => {};
  write(file, [line.prompt("fresh"), line.assistant("x", usage(10, 1_000))]);
  fs.utimesSync(file, new Date(), new Date(Date.now() + 5000));
  s.refresh(WINDOW);
  assert.equal(s.tokens, 1_010);
  assert.equal(s.compactions, 0);
  assert.equal(s.seenCc, 0, "seen count re-baselined");
  assert.equal(typeof s.onChange, "function", "change callback kept");
});
