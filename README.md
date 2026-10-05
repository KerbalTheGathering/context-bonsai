# Context Bonsai

A living bonsai for each of your Claude Code sessions, on Windows. The tree fills out as a session's context grows, its leaves turn and fall near the limit, and compacting prunes it back. It comes as a **Claude Code plugin** (hooks, a status line and commands) plus a **desktop widget**.

None of it makes model calls. It reads the session logs in `~/.claude/projects` and git on your machine, so it costs no usage.

## Install

Clone the repo, then either ask Claude Code, in the clone, to "install Context Bonsai from this repo", or run it yourself:

```powershell
.\scripts\install.ps1          # shows the plan, asks before changing anything
.\scripts\install.ps1 -Plan    # just show the plan
.\scripts\install.ps1 -Uninstall
```

It needs Python 3 with Pillow (`pip install pillow`), Node.js, and the `claude` CLI on your PATH. What it does:

1. **Installs the plugin.** It adds the clone as a local plugin marketplace and installs the `context-bonsai` plugin for your user. The plugin provides the two hooks below and the commands. Running the script again updates the plugin from the clone; restart Claude Code to load an update.
2. **Updates `~/.claude/settings.json`,** after backing it up and only with your OK:
   - It removes old hand-installed entries for these hooks, which would otherwise fire twice.
   - It points the status line at the clone. Plugins can't provide a status line, and if you already use a status line of your own, it's left alone.
3. **Builds the desktop app** and installs a standalone copy in `%LOCALAPPDATA%\Programs\ContextBonsai`, so the widget keeps working if the clone moves. It's Electron's runtime (about 300 MB) plus the app.
4. **Creates Start menu shortcuts:** **Context Bonsai** (the desktop app) and **Context Bonsai (classic)** (the Tk widget). It also records the clone's location in `~/.claude/widget/install.json` for the commands.

Hooks take effect in sessions started afterwards.

## The plugin (`plugin/`)

| Part | What it does |
|---|---|
| SessionStart hook (`compact`) | After a compaction, adds git state, still-running background jobs and the project's `.claude/brief.md` to Claude's context, and shows a `↻ restored: …` line. |
| PreCompact hook | Tells the widgets a compaction has started, so they animate it on that session's tree. |
| Status line (`plugin/statusline/`) | Bonsai stage emoji, context %, 5-hour and 7-day limits, git branch. Terminal only; the desktop app has no status line display. |
| `/context-bonsai:widget` | Opens the desktop widget, or closes it if it's open (`classic` for the Tk widget). |
| `/context-bonsai:snapshot` | Writes a one-off HTML page of this session's bonsai and opens it. |
| `/context-bonsai:setup` | Runs the installer from your clone: shows the plan, asks, applies. `uninstall` reverses it. |

## The desktop widget (`desktop/`)

An always-on-top card, rendered on the GPU with PixiJS in Electron.

**The grove** shows a tree for every session that's open (from `~/.claude/sessions`) or was active in the last 30 minutes, up to 12. You see four at a time in a carousel:
- **Browsing:** drag or flick it (it carries on with momentum), scroll the wheel, or use the arrows, the page dots or ←/→.
- **Labels:** each card shows the session's sidebar title and project.
- **Order:** right-click → Grove order sorts by first seen, fullest, or most recent.
- **Opening:** click a tree (or press Enter) to zoom into its card; **‹ N** or Esc goes back.
- **Compaction:** when any session starts compacting, the card switches to it so the animation plays on its own tree.

**A session's card:**

- **The tree** grows its own shape per session, seeded from its log name. Every leaf moves in a gusty wind while Claude works. While it waits on you, the tree is still, with an occasional leaf letting go.
- **The readout and meter** show context % and tokens on the wall, with the shelf edge as the meter (a mark at 85% means compact soon). The status line below shows the stage and a short tip, plus a **Compact** button that copies `/compact` and brings the Claude app forward.
- **Background jobs** get an amber chip while they run, showing each job's latest output line and its age.
- **Stats:**
  - a sparkline of context per call, with peak, average and total tokens;
  - context: cache hit rate, compactions, API calls;
  - work: tool calls, errors, files edited;
  - time: session length, time since your last prompt, prompts.
- **Compaction:** shears work along the canopy, leaves fall into a pile, then a watering can pours and new buds open.
- **Time of day:** the wall's light follows your clock, and at night (or after 30 idle minutes) a moon rises and fireflies come out.

**Three art styles,** chosen by theme:

- *Diorama* (Moss, Paper, Sakura, Midnight, Canyon, Clay, Neon, Pixel): a lit bonsai on a wooden stand, with a cast shadow.
- *Glass* (Aurora, Frost): frosted panes over a drifting aurora, a glass pot on a lit horizon, glowing foliage, neon meters.
- *Ink* (Sumi-e, Night Ink): washi paper with mountains in a pale wash, a brush-stroke trunk with ink bleeding into the paper, ink-dab foliage, a red seal.

Plus Auto (follows Windows light/dark mode and accent color) and Seasons (changes with the date). Right-click → *Theme for <project>* gives one project its own theme.

**Controls:**
- Drag to move. The card stays anchored at its bottom-right corner, and is always kept on a screen.
- Double-click or Z toggles zen mode (just the trees).
- Right-click for Start with Windows, Keep on top, Pin this session, Theme, View, Grove order, Zen mode, Ambient animation, Rescan sessions, Compact, Preview compact animation, and Quit.
- Opening the shortcut again closes it, once it has been showing for a few seconds (a second click while it starts up just keeps it open).

**CPU:** it draws only when something changes. Idle, it measured 0.5–3% of one CPU core.

It assumes a 1M-token context window; change `window` in `~/.claude/widget/bonsai.json` if yours differs. Settings there are shared with the classic widget.

**The classic widget** (`widget/bonsai_widget.pyw`) is the original Tk version, with the same data and settings and the diorama themes. It's kept as **Context Bonsai (classic)**.

## Repository layout

| Path | What it is |
|---|---|
| `.claude-plugin/marketplace.json` | Makes the clone a plugin marketplace listing `plugin/`. |
| `plugin/` | The Claude Code plugin: manifest, hooks, status line, commands. |
| `desktop/` | The Electron + PixiJS widget. |
| `widget/` | The classic Tk widget and the shared icon. |
| `scripts/` | The installer, the settings migration it uses, and the app packager. |
| `bonsai-page/` | The HTML snapshot page behind `/context-bonsai:snapshot`. |
| `tests/`, `desktop/test/` | Python and Node test suites, run by CI. |
| `tools/` | Dev helpers: the tree parity fixture and the icon builder. |
| `mockup/` | The original interactive mockup. |

## Development

- **Tests:** `python -m unittest discover tests`, and `npm test` in `desktop/`.
- **Running the app:** `npm start` in `desktop/` (`npm run dev` opens dev tools).
- **Plugin edits:** bump `version` in `plugin/.claude-plugin/plugin.json` and the marketplace entry, then rerun the installer to update the installed copy (Claude Code runs plugins from its own cached copy, not from the clone). `claude plugin validate --strict plugin` checks the manifest.
- **Dev aids** (environment variables, documented in `desktop/main/dev.js`): `BONSAI_SHOTS` (screenshot walk-through), `BONSAI_THEME` / `BONSAI_CFG` (unsaved setting overrides), `BONSAI_HOUR` (pin the clock), `BONSAI_LEAK`, `BONSAI_DPI`, `BONSAI_KEYS` (self-checks), and `desktop/tools/measure-cpu.ps1`.

## Conventions

- Put standing per-project instructions in `<project>/.claude/brief.md`. The rehydrate hook re-injects it after every compaction, so it never has to be pasted again.
