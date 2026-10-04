# Context Bonsai

Windows-first. A Claude Code plugin (`plugin/`) plus an Electron + PixiJS desktop widget (`desktop/`) and the classic Tk widget (`widget/`). See README.md for the full layout.

## Installing it for the user

When the user asks to install, update or remove Context Bonsai from this clone:

1. Run `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/install.ps1 -Plan` (add `-Uninstall` to remove). It changes nothing and prints the plan, including the exact edits to `~/.claude/settings.json`.
2. Show the user the plan in plain words, especially the settings edits, and ask them to confirm. Never skip this: the script edits their global Claude Code settings.
3. On a clear yes, run it again with `-Yes` (plus `-Uninstall` if removing), and report what it printed, including where the settings backup went.
4. Tell them hook changes apply to sessions started afterwards, and that a running Claude Code needs a restart to load a plugin update.

## Working on it

- Tests: `python -m unittest discover tests`, and `npm test` in `desktop/`. CI runs both on Windows.
- Plugin changes take effect only after bumping `version` in `plugin/.claude-plugin/plugin.json` and in `.claude-plugin/marketplace.json`, then rerunning the installer. Claude Code runs plugins from its cached copy, not from the clone.
- Shared data lives in `~/.claude/widget` (`bonsai.json` settings, `signal.json`, `install.json`), not in the clone.
- After changing either tree generator, regenerate the parity fixture: `python tools/tree_fixture.py`.
