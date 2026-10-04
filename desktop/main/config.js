// The settings file shared with the Tk widget (~/.claude/widget/bonsai.json).
const fs = require("fs");
const path = require("path");

function readFile(file) {
  try {
    return JSON.parse(fs.readFileSync(file, "utf8"));
  } catch {
    return {};
  }
}

// Write just these keys, keeping whatever else is in the file: the other app may have changed other
// settings since we loaded ours, and writing our whole copy would undo them. Atomic via rename.
function saveKeys(file, cfg, keys) {
  const disk = readFile(file);
  for (const k of keys) disk[k] = cfg[k];
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file + ".tmp", JSON.stringify(disk, null, 2));
  fs.renameSync(file + ".tmp", file);
}

module.exports = { readFile, saveKeys };
