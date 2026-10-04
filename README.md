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

A small always-on-top card for your Claude Code sessions.

**The grove:** when more than one session is open (Claude Code lists open sessions in `~/.claude/sessions`) or has been active in the last 30 minutes, the card shows one small bonsai per session (up to 12), four at a time in a carousel: page with the ‹ › arrows in the header, the dots underneath, or the mouse wheel. Trees are labeled with each session's sidebar title and project. The fullest session is the tallest tree. Click a tree to open its full card; click **‹ N** in the card's header to go back. When any session starts compacting, the card switches to that session so the animation plays on its own tree.

**A session's card:**

- **The tree** fills out as context grows. Leaves go from calm to alarming colors near the limit and start falling above 90%. Compacting prunes it back and adds a tally mark to the pot.
- **The readout** shows context % and tokens, a "compact soon" mark at 85%, and the stage with a short tip.
- **The stats** show the git branch, uncommitted files, running background jobs and the compaction count.
- **Layout:** the session's sidebar title with project · branch · uncommitted files; the tree edge to edge with the % and tokens on the wall and the shelf edge as the meter; one status line with a round ✂ compact button; an amber badge only while a background job runs; a chart of context per call with peak · avg · total tokens; then three icon rows: context (cache hit rate, compactions, API calls), work (tool calls, errors, files edited) and time (session length, time since your last prompt, prompts).
- **A tree per session:** each session grows its own shape (lean, trunk, spread, mirroring are seeded from its log name), and the tree grows smoothly as context is added.
- **Zen mode:** just the bonsai, no text (a row of trees when several sessions are active). Hover for a small % tag; compaction animations still play. Double-click or right-click → Zen mode to switch.
- **Ambient animation** (right-click → Ambient animation to turn off): a breeze rustles the leaves and motes drift while Claude is working; the tree is still while it waits on you, with an occasional leaf letting go; after 30 idle minutes the scene goes to night with a moon and fireflies. The wall's light follows your clock (dawn, day, dusk, night). Costs about 1–2% of total CPU while Claude works, less otherwise.
- **Compaction:** shears work along the canopy edge, leaves burst off, then a watering can tips in and pours before new buds open.
- **Themes:** Auto (follows Windows light/dark mode and your accent color), Seasons (changes with the date), Moss, Paper, Sakura, Midnight, Sumi-e, Canyon, Clay, Neon and Pixel. Right-click → *Theme for <project>* gives a project its own theme, so the grove can mix them.
- **Compact button:** copies `/compact` and brings the Claude app to the front, so you paste it with Ctrl+V and Enter. The widget then animates the compaction: shears snip the canopy while it runs, leaves burst off when it finishes, and rain and new buds play when the rehydrate hook restores state.

Controls: drag to move (the card stays anchored at its bottom-right corner when it changes size). Right-click for Keep on top, Pin this session, Theme, View (Focus or Grove), Zen mode, Rescan sessions (looks for open sessions again and re-reads every transcript's stats), Compact, Preview compact animation, and Quit. Opening the shortcut (or `bonsai_widget.pyw`) again while it runs closes it.

Requirements: Python 3 with Tk and Pillow (`pip install pillow`). It assumes a 1M-token context window; change `window` in `~/.claude/widget/bonsai.json` if yours differs.

## Context Bonsai desktop (Electron + PixiJS)

`desktop/` is a rewrite of the widget's grove and focus views as a GPU-rendered PixiJS app in Electron. The Tk widget stays as is; run one or the other (they share `~/.claude/widget/bonsai.json` for theme, pin and project themes).

- **Living trees:** the same seeded tree per session as the Tk widget, but every leaf is its own sprite moving in a gusty wind while that session works. A cast shadow, a pool of light and light shafts by day; motes while working, fireflies at night. Still trees are baked to a texture so an idle grove costs little.
- **Grove carousel:** drag or flick it (it carries on with momentum and settles on a tree), scroll the wheel, or use the arrows and page dots. Cards lift on hover; clicking one zooms into its focus card.
- **Focus card:** the readout, shelf meter, status and Compact button as before, a sparkline that draws itself in, and the same compaction choreography (shears, falling leaves, watering can, buds).
- **Three art styles**, picked by the theme (right-click → Theme lists them grouped):
  - *Diorama* (Moss, Paper, Sakura, Midnight, Canyon, Clay, Neon, Pixel): the lit bonsai on a wooden stand with a cast shadow.
  - *Glass* (Aurora, Frost): frosted panes over a slowly drifting aurora, a glass pot on a lit horizon, foliage as glowing orbs with glowing wood, neon meters.
  - *Ink* (Sumi-e, Night Ink): washi paper with far mountains in a pale wash, a brush-stroke trunk with ink bleeding into the paper, ink-dab foliage that darkens where it overlaps, a red seal, calmer wind and slower falling leaves.
- **Themes are data** (`desktop/shared/themes.js`: a palette, leaf color stops and a `style`); styles are sets of hooks in `desktop/src/styles.js` for the backdrop, wood, leaves, panel, dividers and meter. The Tk widget doesn't know the glass and ink themes and shows Moss for them.

Run it from `desktop/` with `npm install` then `npm start` (`npm run dev` opens dev tools), or `.\install.ps1 -Desktop` to build it and point the **Context Bonsai** Start menu shortcut at it (the Tk widget moves to **Context Bonsai (classic)**). Opening the shortcut again closes it. Dev aids: `BONSAI_SHOTS=<dir> npx electron .` walks the views and the compaction preview and saves a screenshot at each step; add `BONSAI_THEME=<name>` to preview a theme without saving it.

## Install

```powershell
.\install.ps1
```

This copies the files into `~/.claude` and creates the **Context Bonsai** Start menu shortcut. It does not edit your settings. Merge `settings.example.json` into `~/.claude/settings.json` yourself, replacing `YOU` with your Windows user name. The hooks take effect in sessions started after the change.

## Conventions

- Put standing per-project instructions in `<project>/.claude/brief.md`. The rehydrate hook re-injects it after every compaction, so it never has to be pasted again.
