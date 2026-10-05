---
description: Write a one-off HTML snapshot of this session's bonsai and open it
allowed-tools: Read, Bash(python:*), Bash(powershell:*)
---

Make a Context Bonsai snapshot page for the current session.

1. Read `~/.claude/widget/install.json`. If it's missing, tell the user to run `/context-bonsai:setup` first, and stop.
2. Run `python "<repo>/bonsai-page/snapshot.py"`. With no arguments it uses the most recently active session, which is this one. It prints the path of the HTML file it wrote.
3. Open that file: `powershell -NoProfile -Command "Start-Process '<path>'"`, and tell the user where it is.
