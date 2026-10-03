#!/usr/bin/env python
"""PreCompact hook: tell the Context Bonsai widget that a compaction has started."""
import json
import os
import sys
import time

SIGNAL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "signal.json")

try:
    d = json.loads(sys.stdin.read().lstrip("﻿") or "{}")
    tmp = SIGNAL + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump({"event": "precompact", "transcript": d.get("transcript_path"), "session": d.get("session_id"),
                   "trigger": d.get("trigger"), "at": time.time()}, fh)
    os.replace(tmp, SIGNAL)
except Exception:
    pass  # never block a compaction
