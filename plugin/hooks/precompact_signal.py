#!/usr/bin/env python
"""PreCompact hook: tell the Context Bonsai widgets that a compaction has started.

Writes ~/.claude/widget/signal.json (BONSAI_DATA_DIR overrides the folder), which both widgets watch."""
import json
import os
import sys
import time

DATA = os.environ.get("BONSAI_DATA_DIR") or os.path.join(os.path.expanduser("~"), ".claude", "widget")
SIGNAL = os.path.join(DATA, "signal.json")

try:
    d = json.loads(sys.stdin.read().lstrip("﻿") or "{}")
    os.makedirs(DATA, exist_ok=True)
    tmp = SIGNAL + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump({"event": "precompact", "transcript": d.get("transcript_path"), "session": d.get("session_id"),
                   "trigger": d.get("trigger"), "at": time.time()}, fh)
    os.replace(tmp, SIGNAL)
except Exception:
    pass  # never block a compaction
