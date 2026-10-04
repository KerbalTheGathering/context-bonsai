"""The Tk widget's shared-settings save: only the keys it changed are written, so the desktop app's
changes survive. Loads the widget's module-level code (no window). Needs Pillow."""
import json
import os
import shutil
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WIDGET = os.path.join(ROOT, "widget", "bonsai_widget.pyw")


def load_widget():
    src = open(WIDGET, encoding="utf-8").read()  # main() only runs as __main__
    ns = {"__file__": WIDGET, "__name__": "bonsai_widget"}
    exec(compile(src, WIDGET, "exec"), ns)
    return ns


class SaveConfigTest(unittest.TestCase):
    def setUp(self):
        self.w = load_widget()
        self.tmp = tempfile.mkdtemp(prefix="bonsai-cfg-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.w["CONFIG"] = os.path.join(self.tmp, "bonsai.json")
        # save_config reads CONFIG from its module globals, which is this namespace
        self.save = self.w["save_config"]

    def read(self):
        with open(self.w["CONFIG"], encoding="utf-8") as f:
            return json.load(f)

    def test_keeps_other_apps_settings(self):
        with open(self.w["CONFIG"], "w", encoding="utf-8") as f:
            json.dump({"theme": "Aurora", "desktop": {"right": 1, "bottom": 2}, "zen": False}, f)
        stale = {"theme": "Moss", "zen": True, "topmost": True}
        self.save(stale, "zen")
        self.assertEqual(self.read(), {"theme": "Aurora", "desktop": {"right": 1, "bottom": 2}, "zen": True})

    def test_drop_and_create(self):
        self.save({"right": 5, "bottom": 6, "x": 1}, "right", "bottom", drop=("x", "y"))
        self.assertEqual(self.read(), {"right": 5, "bottom": 6})
        self.assertFalse(os.path.exists(self.w["CONFIG"] + ".tmp"))


if __name__ == "__main__":
    unittest.main()
