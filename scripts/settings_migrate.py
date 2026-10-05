#!/usr/bin/env python
"""Move ~/.claude/settings.json from the old hand-installed Context Bonsai setup to the plugin.

The plugin now provides the SessionStart (compact) and PreCompact hooks, so the old entries that ran copies
in ~/.claude must go, or the hooks would fire twice. Plugins can't provide a status line, so it's pointed at
the clone's script. Nothing else in the file is touched.

Usage:
  settings_migrate.py plan    --repo <clone> [--settings <file>]   print the changes as JSON, write nothing
  settings_migrate.py apply   --repo <clone> [--settings <file>]   back up the file, then write the changes
  add --uninstall to plan or apply removing the status line this installed (hooks are the plugin's to remove)
"""
import argparse
import copy
import json
import os
import shutil
import sys
import time

LEGACY_HOOKS = ("rehydrate.py", "precompact_signal.py")
STATUSLINE = "statusline.py"


def default_settings():
    return os.path.join(os.path.expanduser("~"), ".claude", "settings.json")


def statusline_command(repo):
    path = os.path.join(repo, "plugin", "statusline", "statusline.py").replace("\\", "/")
    return f'python "{path}"'


def ours(command, name):
    """Does a command run one of our scripts? Matched by file name, wherever the copy lives."""
    c = (command or "").replace("\\", "/")
    return f"/{name}" in c or c.endswith(name) or f"{name}\"" in c


def plan(settings, repo, uninstall=False):
    """Returns (new settings, list of human-readable changes)."""
    new, changes = copy.deepcopy(settings), []
    if not uninstall:
        hooks = new.get("hooks") or {}
        for event in list(hooks):
            groups = []
            for group in hooks[event] or []:
                kept = []
                for h in group.get("hooks") or []:
                    if h.get("type") == "command" and any(ours(h.get("command"), n) for n in LEGACY_HOOKS):
                        changes.append(f"remove the old {event} hook ({h.get('command')}): the plugin runs it now")
                    else:
                        kept.append(h)
                if kept:
                    groups.append({**group, "hooks": kept})
            if groups:
                hooks[event] = groups
            else:
                del hooks[event]
        if "hooks" in new and not new["hooks"]:
            del new["hooks"]
    status = new.get("statusLine")
    want = statusline_command(repo)
    if uninstall:
        if status and ours(status.get("command"), STATUSLINE):
            del new["statusLine"]
            changes.append(f"remove the status line ({status.get('command')})")
    elif not status:
        new["statusLine"] = {"type": "command", "command": want}
        changes.append(f"add the bonsai status line ({want})")
    elif ours(status.get("command"), STATUSLINE):
        if status.get("command") != want:
            new["statusLine"] = {**status, "type": "command", "command": want}
            changes.append(f"point the status line at the clone ({status.get('command')} -> {want})")
    else:
        changes.append(f"keep your own status line ({status.get('command')}); the bonsai one is not installed")
    return new, changes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["plan", "apply"])
    ap.add_argument("--repo", required=True)
    ap.add_argument("--settings", default=default_settings())
    ap.add_argument("--uninstall", action="store_true")
    a = ap.parse_args()
    try:
        with open(a.settings, encoding="utf-8-sig") as f:
            settings = json.load(f)
    except FileNotFoundError:
        settings = {}
    new, changes = plan(settings, os.path.abspath(a.repo), a.uninstall)
    result = {"settings": a.settings, "changes": changes, "backup": None, "written": False}
    if a.action == "apply" and new != settings:
        if os.path.exists(a.settings):
            result["backup"] = f"{a.settings}.bak-{time.strftime('%Y%m%d-%H%M%S')}"
            shutil.copy2(a.settings, result["backup"])
        os.makedirs(os.path.dirname(a.settings), exist_ok=True)
        tmp = a.settings + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(new, f, indent=2, ensure_ascii=False)
            f.write("\n")
        os.replace(tmp, a.settings)
        result["written"] = True
    sys.stdout.write(json.dumps(result, indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
