---
description: Open the Context Bonsai desktop widget, or close it if it's already open
argument-hint: "[classic]"
allowed-tools: Read, Bash(powershell:*)
---

Toggle the Context Bonsai widget (arguments: "$ARGUMENTS").

1. Read `~/.claude/widget/install.json`. If it's missing, tell the user to run `/context-bonsai:setup` first, and stop.
2. Use its `launch` entry (or `classic` when the argument is `classic`, for the original Tk widget). Each has a `file` and `args`.
3. Start it detached, without waiting:
   `powershell -NoProfile -Command "Start-Process -FilePath '<file>' -ArgumentList '<args>'"`
4. Say in one line that the widget opens near the bottom-right of the screen, and that running this again closes it.
