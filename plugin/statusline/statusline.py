#!/usr/bin/env python
"""Status line: bonsai stage, context use, usage limits, git branch."""
import json
import subprocess
import sys

GREEN, AMBER, RED, DIM, RESET = "\x1b[32m", "\x1b[33m", "\x1b[31m", "\x1b[2m", "\x1b[0m"


def stage(pct):
    if pct < 35: return "\U0001F331", GREEN    # seedling
    if pct < 66: return "\U0001F33F", GREEN    # herb
    if pct < 80: return "\U0001F333", AMBER    # tree
    if pct < 92: return "\U0001F342", AMBER    # fallen leaf
    return "\U0001F341", RED                   # maple leaf


def color_for(pct):
    return GREEN if pct < 60 else AMBER if pct < 85 else RED


def branch(cwd):
    try:
        r = subprocess.run(["git", "branch", "--show-current"], cwd=cwd, capture_output=True,
                           text=True, timeout=1)
        return r.stdout.strip() if r.returncode == 0 else ""
    except (OSError, subprocess.TimeoutExpired):
        return ""


def log(raw):
    import os, time
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "statusline.log")
    with open(path, "a", encoding="utf-8") as f:
        f.write(f"{time.strftime('%H:%M:%S')} argv={sys.argv[1:]} bytes={len(raw)} head={raw[:160]!r}\n")


def main():
    raw = sys.stdin.read()
    if "--log" in sys.argv:
        log(raw)
    try:
        d = json.loads(raw.lstrip("﻿") or "{}")
    except ValueError:
        d = {}
    cw = d.get("context_window") or {}
    pct = cw.get("used_percentage")
    parts = []
    if pct is None:
        parts.append("\U0001F331 ctx –")
    else:
        icon, col = stage(pct)
        parts.append(f"{icon} {col}{pct:.0f}%{RESET} ctx")
    limits = d.get("rate_limits") or {}
    for key, label in (("five_hour", "5h"), ("seven_day", "7d")):
        p = (limits.get(key) or {}).get("used_percentage")
        if p is not None:
            parts.append(f"{label} {color_for(p)}{p:.0f}%{RESET}")
    cwd = (d.get("workspace") or {}).get("current_dir") or d.get("cwd")
    b = branch(cwd) if cwd else ""
    if b:
        parts.append(f"{DIM}⎇ {b}{RESET}")
    sys.stdout.buffer.write((f" {DIM}·{RESET} ".join(parts) + "\n").encode("utf-8"))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.stdout.buffer.write(b"statusline error\n")
