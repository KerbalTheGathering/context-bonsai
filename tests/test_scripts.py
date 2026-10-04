"""End-to-end tests for the hook and status line scripts: each runs as a subprocess with JSON on stdin,
the way Claude Code calls it. Run from the repo root: python -m unittest discover tests"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REHYDRATE = os.path.join(ROOT, "hooks", "rehydrate.py")
STATUSLINE = os.path.join(ROOT, "statusline", "statusline.py")
PRECOMPACT = os.path.join(ROOT, "widget", "precompact_signal.py")
sys.path.insert(0, os.path.join(ROOT, "hooks"))
import rehydrate  # noqa: E402


def run(script, payload, env=None):
    data = payload if isinstance(payload, (bytes, str)) else json.dumps(payload)
    r = subprocess.run([sys.executable, script], input=data if isinstance(data, bytes) else data.encode("utf-8"),
                       capture_output=True, timeout=30, env={**os.environ, **(env or {})})
    return r.returncode, r.stdout.decode("utf-8", "replace")


def git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True,
                   env={**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
                        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com"})


def jsonl(path, lines):
    with open(path, "w", encoding="utf-8") as f:
        for l in lines:
            f.write(json.dumps(l) + "\n")


class RehydrateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="bonsai-test-")
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def test_git_state_brief_and_status_line(self):
        repo = os.path.join(self.tmp, "proj")
        os.makedirs(os.path.join(repo, ".claude"))
        git(repo, "init", "-q", "-b", "main")
        with open(os.path.join(repo, "a.txt"), "w") as f:
            f.write("a")
        git(repo, "add", ".")
        git(repo, "commit", "-q", "-m", "first")
        with open(os.path.join(repo, "b.txt"), "w") as f:
            f.write("b")  # uncommitted, as is the untracked .claude/brief.md below
        with open(os.path.join(repo, ".claude", "brief.md"), "w", encoding="utf-8") as f:
            f.write("Always run the tests.")
        code, out = run(REHYDRATE, {"cwd": repo})
        self.assertEqual(code, 0)
        d = json.loads(out)
        self.assertTrue(d["systemMessage"].startswith("↻ restored: main@"))
        self.assertIn("2 changed", d["systemMessage"])
        self.assertIn("brief.md", d["systemMessage"])
        ctx = d["hookSpecificOutput"]["additionalContext"]
        self.assertEqual(d["hookSpecificOutput"]["hookEventName"], "SessionStart")
        self.assertIn("Always run the tests.", ctx)
        self.assertIn("Branch main", ctx)
        self.assertIn("No upstream configured", ctx)

    def test_outside_git_and_bad_input(self):
        code, out = run(REHYDRATE, {"cwd": self.tmp})
        self.assertEqual(code, 0)
        self.assertIn("no git repo", json.loads(out)["systemMessage"])
        code, out = run(REHYDRATE, b"not json")
        self.assertEqual(code, 0, "a broken payload must never break session start")
        json.loads(out)

    def test_running_jobs(self):
        t = os.path.join(self.tmp, "t.jsonl")
        launch = lambda tu, desc: {"type": "assistant", "message": {"content": [
            {"type": "tool_use", "id": tu, "name": "Bash", "input": {"command": "x", "description": desc,
                                                                      "run_in_background": True}}]}}
        started = lambda tu, tid: {"type": "user", "toolUseResult": {"backgroundTaskId": tid},
                                   "message": {"content": [{"type": "tool_result", "tool_use_id": tu}]}}
        jsonl(t, [launch("tu1", "dev server"), started("tu1", "bg1"),
                  launch("tu2", "watcher"), started("tu2", "bg2"),
                  {"type": "queue-operation",
                   "content": "<task-notification><task-id>bg2</task-id><status>completed</status></task-notification>"}])
        jobs = rehydrate.running_jobs(t)
        self.assertEqual([(j["id"], j["desc"]) for j in jobs], [("bg1", "dev server")])

    def test_fmt_age(self):
        self.assertEqual(rehydrate.fmt_age(None), "no output file")
        self.assertEqual(rehydrate.fmt_age(30), "30s ago")
        self.assertEqual(rehydrate.fmt_age(600), "10m ago")
        self.assertEqual(rehydrate.fmt_age(7200), "2.0h ago")


class StatusLineTest(unittest.TestCase):
    def test_context_and_limits(self):
        code, out = run(STATUSLINE, {"context_window": {"used_percentage": 72.4},
                                     "rate_limits": {"five_hour": {"used_percentage": 10},
                                                     "seven_day": {"used_percentage": 90}}})
        self.assertEqual(code, 0)
        self.assertIn("72%", out)
        self.assertIn("\U0001F333", out)  # tree stage at 72%
        self.assertIn("5h \x1b[32m10%", out)
        self.assertIn("7d \x1b[31m90%", out)

    def test_empty_input(self):
        code, out = run(STATUSLINE, b"")
        self.assertEqual(code, 0)
        self.assertIn("ctx –", out)


class PreCompactTest(unittest.TestCase):
    def test_writes_signal(self):
        tmp = tempfile.mkdtemp(prefix="bonsai-test-")
        self.addCleanup(shutil.rmtree, tmp, True)
        script = shutil.copy(PRECOMPACT, tmp)  # the signal lands next to the script
        code, _ = run(script, {"transcript_path": "C:/x/t.jsonl", "session_id": "s1", "trigger": "manual"})
        self.assertEqual(code, 0)
        with open(os.path.join(tmp, "signal.json"), encoding="utf-8") as f:
            sig = json.load(f)
        self.assertEqual(sig["event"], "precompact")
        self.assertEqual(sig["transcript"], "C:/x/t.jsonl")
        self.assertEqual(sig["trigger"], "manual")


if __name__ == "__main__":
    unittest.main()
