---
description: Set up or update Context Bonsai from your clone (desktop app, shortcuts, status line, old settings cleanup)
argument-hint: "[uninstall]"
allowed-tools: Read, Bash(powershell:*)
---

Set up Context Bonsai on this Windows machine, or remove it if the argument is `uninstall` (arguments: "$ARGUMENTS").

1. Read `~/.claude/widget/install.json`. Its `repo` field is the user's clone of the context-bonsai repository. If the file is missing, ask the user where they cloned the repo, and use that path.
2. Run the installer in plan mode first, so nothing changes yet:
   `powershell -NoProfile -ExecutionPolicy Bypass -File "<repo>/scripts/install.ps1" -Plan`
   (add `-Uninstall` when uninstalling). It prints what it would do, including the exact changes to `~/.claude/settings.json`.
3. Show the user that plan in plain words, especially any settings changes, and ask them to confirm. Don't run the next step without a clear yes.
4. Run it for real with the same flags plus `-Yes`, and report what it printed: what was installed, where the settings backup went, and anything that failed.
5. Remind the user that hook changes take effect in sessions started afterwards, and that Claude Code needs a restart to load a plugin update.
