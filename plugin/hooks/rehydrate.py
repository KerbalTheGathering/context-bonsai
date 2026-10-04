#!/usr/bin/env python
"""SessionStart(compact) hook: re-inject working state after compaction.

Adds git state, background jobs still running, and the project's pinned
brief (.claude/brief.md) to Claude's context, and prints a one-line status.
"""
import glob
import json
import os
import re
import subprocess
import sys
import tempfile
import time

BRIEF_MAX_CHARS = 12000
DIRTY_LIST_MAX = 12
TAIL_BYTES = 4096
ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
BG_LAUNCH = re.compile(r'"run_in_background"\s*:\s*true')
TASK_ID = re.compile(r"<task-id>([^<]+)</task-id>")


def git(cwd, *args):
    try:
        r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return r.stdout if r.returncode == 0 else None


def git_state(cwd):
    top = (git(cwd, "rev-parse", "--show-toplevel") or "").strip()
    if not top:
        return None
    dirty = [l for l in (git(top, "status", "--porcelain") or "").splitlines() if l.strip()]
    ahead = git(top, "rev-list", "--count", "@{u}..HEAD")
    return {
        "top": os.path.normpath(top),
        "branch": (git(top, "branch", "--show-current") or "").strip() or "(detached)",
        "head": (git(top, "log", "-1", "--format=%h %s") or "").strip() or "(no commits)",
        "dirty": dirty,
        "ahead": int(ahead) if ahead and ahead.strip().isdigit() else None,
    }


def running_jobs(transcript):
    """Background Bash/PowerShell commands launched with no completion seen yet."""
    launched, finished, desc = {}, set(), {}
    try:
        fh = open(transcript, encoding="utf-8", errors="replace")
    except OSError:
        return []
    with fh:
        for line in fh:
            # Completions arrive as queue-operation/attachment entries, so match the raw line.
            if "<task-notification>" in line:
                for block in line.split("<task-notification>")[1:]:
                    if "<status>" in block:
                        finished.update(TASK_ID.findall(block))
                continue
            if BG_LAUNCH.search(line):
                d = json.loads(line)
                for c in (d.get("message") or {}).get("content") or []:
                    if isinstance(c, dict) and c.get("type") == "tool_use":
                        inp = c.get("input") or {}
                        desc[c.get("id")] = inp.get("description") or (inp.get("command") or "")[:80]
            elif '"backgroundTaskId"' in line:
                d = json.loads(line)
                r = d.get("toolUseResult")
                if isinstance(r, dict) and r.get("backgroundTaskId"):
                    tuid = next((c.get("tool_use_id") for c in (d.get("message") or {}).get("content") or []
                                 if isinstance(c, dict) and c.get("type") == "tool_result"), None)
                    launched[r["backgroundTaskId"]] = tuid
            elif '"TaskStop"' in line:
                d = json.loads(line)
                for c in (d.get("message") or {}).get("content") or []:
                    if isinstance(c, dict) and c.get("name") == "TaskStop":
                        inp = c.get("input") or {}
                        finished.add(inp.get("task_id") or inp.get("shell_id"))

    proj = os.path.basename(os.path.dirname(transcript))
    jobs = []
    for tid, tuid in launched.items():
        if tid in finished:
            continue
        out = next(iter(glob.glob(os.path.join(tempfile.gettempdir(), "claude", proj, "*", "tasks", tid + ".output"))), None)
        last, age = "", None
        if out:
            age = time.time() - os.path.getmtime(out)
            with open(out, "rb") as f:
                f.seek(max(0, os.path.getsize(out) - TAIL_BYTES))
                tail = ANSI.sub("", f.read().decode("utf-8", "replace"))
            lines = [l.strip() for l in re.split(r"[\r\n]+", tail) if l.strip()]
            last = lines[-1][:160] if lines else ""
        jobs.append({"id": tid, "desc": desc.get(tuid, ""), "out": out, "last": last, "age": age})
    return jobs


def fmt_age(sec):
    if sec is None:
        return "no output file"
    if sec < 90:
        return f"{int(sec)}s ago"
    if sec < 5400:
        return f"{int(sec // 60)}m ago"
    return f"{sec / 3600:.1f}h ago"


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        data = json.loads(sys.stdin.read().lstrip("﻿") or "{}")
    except ValueError:
        data = {}
    cwd = data.get("cwd") or os.getcwd()
    g = git_state(cwd)
    jobs = running_jobs(data["transcript_path"]) if data.get("transcript_path") else []
    brief_path = os.path.join(g["top"] if g else cwd, ".claude", "brief.md")
    brief = None
    if os.path.isfile(brief_path):
        with open(brief_path, encoding="utf-8", errors="replace") as f:
            brief = f.read().strip()

    ctx = ["<post-compact-state>",
           "Re-injected by the rehydrate hook after compaction. Where this disagrees with the summary, trust this."]
    status = []
    if g:
        ctx += ["", f"## Git ({g['top']})", f"Branch {g['branch']}, HEAD {g['head']}"]
        if g["dirty"]:
            ctx.append(f"Uncommitted: {len(g['dirty'])} path(s)")
            ctx += ["  " + l for l in g["dirty"][:DIRTY_LIST_MAX]]
            if len(g["dirty"]) > DIRTY_LIST_MAX:
                ctx.append(f"  ... and {len(g['dirty']) - DIRTY_LIST_MAX} more")
        else:
            ctx.append("Working tree clean")
        ctx.append("No upstream configured" if g["ahead"] is None else f"Unpushed commits: {g['ahead']}")
        status += [f"{g['branch']}@{g['head'].split()[0]}", f"{len(g['dirty'])} changed",
                   "no upstream" if g["ahead"] is None else f"{g['ahead']} unpushed"]
    else:
        status.append("no git repo")

    if jobs:
        ctx += ["", "## Background jobs still running (launched this session, no completion seen)"]
        for j in jobs:
            ctx.append(f"- {j['id']}: {j['desc'] or '(no description)'} | last output {fmt_age(j['age'])}: {j['last'] or '(empty)'}")
            if j["out"]:
                ctx.append(f"  output file: {j['out']}")
    status.append(f"{len(jobs)} job{'s' if len(jobs) != 1 else ''} running")

    if brief:
        if len(brief) > BRIEF_MAX_CHARS:
            brief = brief[:BRIEF_MAX_CHARS] + f"\n[... truncated; read {brief_path} for the rest]"
        ctx += ["", f"## Project brief ({brief_path}): standing directive, follow it", brief]
        status.append("brief.md")
    ctx.append("</post-compact-state>")

    print(json.dumps({
        "systemMessage": "↻ restored: " + " · ".join(status),
        "hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": "\n".join(ctx)},
    }, ensure_ascii=True))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # never break session start
        print(json.dumps({"systemMessage": f"rehydrate hook error: {e}"}))
