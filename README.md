# Claude Code mods

Personal mods for Claude Code on Windows: a hook that restores working state after compaction, a terminal status line, and **Context Bonsai**, a desktop widget that draws the active session's context use as a bonsai tree.

None of these make model calls. They read the session logs in `~/.claude/projects` and git on your machine, so they cost no usage.

## What's here

| Folder | What it is | Where it works |
|---|---|---|
| `hooks/rehydrate.py` | SessionStart hook (matcher `compact`). After a compaction it adds git state, still-running background jobs and the project's `.claude/brief.md` to Claude's context, and shows a `↻ restored: …` line. | Desktop app and terminal |
| `statusline/statusline.py` | Status line: bonsai stage emoji, context %, 5-hour and 7-day limits, git branch. | Terminal only (the desktop app runs Claude Code without a terminal display) |
| `widget/` | Context Bonsai desktop widget, its PreCompact signal hook and icon. | Windows desktop |
| `bonsai-page/` | Prototype for a `/bonsai` command: writes a one-off HTML snapshot of a session's bonsai. | Any browser |
| `mockup/` | The original interactive mockup of the bonsai. | Any browser |
| `tools/make_icon.py` | Rebuilds `widget/bonsai.ico` from the widget's own drawing code. | — |

## Context Bonsai widget

A small always-on-top card that follows the most recently active Claude Code session:

- **The tree** fills out as context grows. Leaves go from calm to alarming colors near the limit and start falling above 90%. Compacting prunes it back and adds a tally mark to the pot.
- **The readout** shows context % and tokens, a "compact soon" mark at 85%, and the stage with a short tip.
- **The stats** show the git branch, uncommitted files, running background jobs and the compaction count.
- **Themes:** Moss, Paper, Sakura, Midnight, Sumi-e (right-click → Theme).
- **Compact button:** copies `/compact` and brings the Claude app to the front, so you paste it with Ctrl+V and Enter. The widget then animates the compaction: shears snip the canopy while it runs, leaves burst off when it finishes, and rain and new buds play when the rehydrate hook restores state.

Controls: drag to move. Right-click for Keep on top, Pin this session, Theme, Preview compact animation, and Quit. Opening the shortcut (or `bonsai_widget.pyw`) again while it runs closes it.

Requirements: Python 3 with Tk and Pillow (`pip install pillow`). It assumes a 1M-token context window; change `window` in `~/.claude/widget/bonsai.json` if yours differs.

## Install

```powershell
.\install.ps1
```

This copies the files into `~/.claude` and creates the **Context Bonsai** Start menu shortcut. It does not edit your settings. Merge `settings.example.json` into `~/.claude/settings.json` yourself, replacing `YOU` with your Windows user name. The hooks take effect in sessions started after the change.

## Conventions

- Put standing per-project instructions in `<project>/.claude/brief.md`. The rehydrate hook re-injects it after every compaction, so it never has to be pasted again.
