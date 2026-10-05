// Builders for synthetic transcript lines, shaped like Claude Code's session logs.
const fs = require("fs");
const os = require("os");
const path = require("path");

let n = 0;
const ts = () => new Date(Date.UTC(2026, 9, 1, 12, 0, n++)).toISOString();

const line = {
  prompt: (text, extra = {}) => ({ type: "user", timestamp: ts(), cwd: "C:\\work\\demo",
    message: { role: "user", content: text }, ...extra }),
  assistant: (id, usage, content = [{ type: "text", text: "ok" }], extra = {}) => ({ type: "assistant", timestamp: ts(),
    message: { id, role: "assistant", content, usage }, ...extra }),
  toolUse: (id, name, input) => ({ type: "tool_use", id, name, input }),
  toolResult: (toolUseId, isError = false, extra = {}) => ({ type: "user", timestamp: ts(),
    message: { role: "user", content: [{ type: "tool_result", tool_use_id: toolUseId, is_error: isError, content: "out" }] },
    ...extra }),
  compact: (preTokens, durationMs) => ({ type: "system", subtype: "compact_boundary", timestamp: ts(),
    compactMetadata: { trigger: "manual", preTokens, durationMs } }),
  title: (customTitle) => ({ type: "custom-title", customTitle }),
  restored: (content) => ({ type: "attachment", timestamp: ts(),
    attachment: { type: "hook_system_message", content } }),
  notification: (taskId) => ({ type: "queue-operation", timestamp: ts(),
    content: `<task-notification><task-id>${taskId}</task-id><status>completed</status></task-notification>` }),
};

const usage = (input, cacheRead = 0, cacheWrite = 0, output = 10) => ({
  input_tokens: input, cache_read_input_tokens: cacheRead, cache_creation_input_tokens: cacheWrite, output_tokens: output,
});

function tmpTranscript(lines) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "bonsai-test-"));
  const file = path.join(dir, "11111111-2222-3333-4444-555555555555.jsonl");
  write(file, lines);
  return file;
}

function write(file, lines, flag = "w") {
  fs.writeFileSync(file, lines.map((l) => JSON.stringify(l) + "\n").join(""), { flag });
}

module.exports = { line, usage, tmpTranscript, write };
