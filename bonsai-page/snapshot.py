#!/usr/bin/env python
"""Write a Context Bonsai snapshot page for a Claude Code session and print its path.

Usage: snapshot.py [transcript.jsonl] [out.html]
With no transcript, uses the most recently active session.
"""
import importlib.util
import json
import os
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
WIDGET = os.path.join(os.path.dirname(HERE), "widget", "bonsai_widget.pyw")  # the clone's widget, for its readers


def load_widget():
    spec = importlib.util.spec_from_file_location("bonsai_widget", WIDGET)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    bw = load_widget()
    cfg = bw.load_config()
    if len(sys.argv) > 1 and sys.argv[1]:
        cfg["pinned"] = sys.argv[1]
    s = bw.Session(cfg)
    s.refresh()
    if not s.path:
        sys.exit("no Claude Code session found")
    branch, changed = s.git
    data = {
        "project": os.path.basename(os.path.normpath(s.cwd)) if s.cwd else None,
        "at": time.strftime("%H:%M"),
        "tokens": s.tokens, "window": cfg["window"], "after_compact": s.after_compact,
        "compactions": s.compactions, "last_pre": s.last_pre,
        "branch": branch, "changed": changed,
        "jobs": [{"id": j["id"], "desc": j["desc"], "last": j["last"]} for j in s.jobs],
    }
    with open(os.path.join(HERE, "template.html"), encoding="utf-8") as fh:
        page = fh.read().replace("/*DATA*/{}", json.dumps(data).replace("</", "<\\/"))
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(tempfile.gettempdir(), "context-bonsai.html")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(page)
    print(out)


if __name__ == "__main__":
    main()
