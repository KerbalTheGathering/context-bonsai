const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("fs");
const os = require("os");
const path = require("path");
const { readFile, saveKeys } = require("../main/config.js");

const tmp = () => path.join(fs.mkdtempSync(path.join(os.tmpdir(), "bonsai-cfg-")), "bonsai.json");

test("saving one key keeps settings another app changed", () => {
  const file = tmp();
  fs.writeFileSync(file, JSON.stringify({ theme: "Moss", right: 100, bottom: 200 }));
  const mine = readFile(file);
  fs.writeFileSync(file, JSON.stringify({ theme: "Sakura", right: 300, bottom: 400 })); // the Tk widget saves
  mine.zen = true;
  saveKeys(file, mine, ["zen"]);
  assert.deepEqual(readFile(file), { theme: "Sakura", right: 300, bottom: 400, zen: true });
});

test("a missing or broken file reads as empty and is created on save", () => {
  const file = tmp();
  assert.deepEqual(readFile(file), {});
  fs.writeFileSync(file, "{ not json");
  assert.deepEqual(readFile(file), {});
  saveKeys(file, { theme: "Aurora" }, ["theme"]);
  assert.deepEqual(readFile(file), { theme: "Aurora" });
  assert.equal(fs.existsSync(file + ".tmp"), false);
});
