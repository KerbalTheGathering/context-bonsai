"""The settings migration: removes only the old hand-installed hooks, sets or repoints our status line,
keeps everything else, backs up before writing."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "scripts", "settings_migrate.py")
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import settings_migrate as sm  # noqa: E402

REPO = "D:/src/context-bonsai"
OLD = {
    "model": "opus",
    "permissions": {"allow": ["Bash(git status)"]},
    "hooks": {
        "SessionStart": [
            {"matcher": "compact", "hooks": [
                {"type": "command", "command": 'python "C:/Users/x/.claude/hooks/rehydrate.py"', "timeout": 30}]},
            {"matcher": "startup", "hooks": [{"type": "command", "command": "echo hi"}]},
        ],
        "PreCompact": [{"hooks": [
            {"type": "command", "command": 'python "C:/Users/x/.claude/widget/precompact_signal.py"', "timeout": 5},
            {"type": "command", "command": "other-tool --precompact"}]}],
    },
    "statusLine": {"type": "command", "command": 'python "C:/Users/x/.claude/statusline.py"', "padding": 1},
}


class PlanTest(unittest.TestCase):
    def test_migrates_old_setup_and_keeps_the_rest(self):
        new, changes = sm.plan(OLD, REPO)
        self.assertEqual(new["model"], "opus")
        self.assertEqual(new["permissions"], OLD["permissions"])
        self.assertEqual(new["hooks"]["SessionStart"], [OLD["hooks"]["SessionStart"][1]], "other hooks kept")
        self.assertEqual(new["hooks"]["PreCompact"][0]["hooks"], [{"type": "command", "command": "other-tool --precompact"}])
        self.assertEqual(new["statusLine"], {"type": "command", "padding": 1,
                                             "command": 'python "D:/src/context-bonsai/plugin/statusline/statusline.py"'})
        self.assertEqual(len(changes), 3)
        self.assertEqual(OLD["hooks"]["SessionStart"][0]["hooks"][0]["timeout"], 30, "input not mutated")

    def test_drops_emptied_hook_events(self):
        s = {"hooks": {"PreCompact": [{"hooks": [{"type": "command", "command": "python C:\\x\\precompact_signal.py"}]}]}}
        new, _ = sm.plan(s, REPO)
        self.assertNotIn("hooks", new)

    def test_adds_status_line_when_missing_and_leaves_a_foreign_one(self):
        new, changes = sm.plan({}, REPO)
        self.assertIn("statusline.py", new["statusLine"]["command"])
        mine = {"statusLine": {"type": "command", "command": "starship statusline"}}
        new, changes = sm.plan(mine, REPO)
        self.assertEqual(new, mine)
        self.assertIn("keep your own status line", changes[0])

    def test_already_migrated_is_a_no_op(self):
        once, _ = sm.plan(OLD, REPO)
        twice, changes = sm.plan(once, REPO)
        self.assertEqual(twice, once)
        self.assertEqual(changes, [])

    def test_uninstall_removes_only_our_status_line(self):
        migrated, _ = sm.plan(OLD, REPO)
        new, changes = sm.plan(migrated, REPO, uninstall=True)
        self.assertNotIn("statusLine", new)
        self.assertEqual(new["hooks"], migrated["hooks"])
        self.assertEqual(len(changes), 1)


class CliTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="bonsai-settings-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.file = os.path.join(self.tmp, "settings.json")
        with open(self.file, "w", encoding="utf-8") as f:
            json.dump(OLD, f)

    def run_cli(self, *args):
        r = subprocess.run([sys.executable, SCRIPT, *args, "--repo", REPO, "--settings", self.file],
                           capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def test_plan_writes_nothing(self):
        out = self.run_cli("plan")
        self.assertEqual(len(out["changes"]), 3)
        self.assertFalse(out["written"])
        with open(self.file, encoding="utf-8") as f:
            self.assertEqual(json.load(f), OLD)

    def test_apply_backs_up_then_writes(self):
        out = self.run_cli("apply")
        self.assertTrue(out["written"])
        with open(out["backup"], encoding="utf-8") as f:
            self.assertEqual(json.load(f), OLD)
        with open(self.file, encoding="utf-8") as f:
            self.assertEqual(json.load(f), sm.plan(OLD, REPO)[0])
        again = self.run_cli("apply")
        self.assertFalse(again["written"], "nothing left to change, so no second backup")


if __name__ == "__main__":
    unittest.main()
