#!/usr/bin/env python
"""Writes desktop/test/fixtures/trees.json: the Tk widget's tree generator output for a few seeds,
so the desktop app's JS port can be checked against it (desktop/test/tree.test.js).

Run from the repo root after changing either generator: python tools/tree_fixture.py
"""
import json
import os
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
WIDGET = os.path.join(ROOT, "widget", "bonsai_widget.pyw")
OUT = os.path.join(ROOT, "desktop", "test", "fixtures", "trees.json")
IDS = ["", "8c489de5-ecab-40cd-8450-6a66d0ef7193.jsonl", "abc.jsonl", "00000000-0000-0000-0000-000000000000.jsonl"]
GROWTH = [0.1, 0.45, 0.8, 1.0]


def load_widget():
    """The widget's module-level code up to the window class: tree, colors, no Tk window."""
    src = open(WIDGET, encoding="utf-8").read().split("\nclass Widget")[0]
    ns = {"__file__": WIDGET, "__name__": "bonsai_widget"}
    exec(compile(src, WIDGET, "exec"), ns)
    return ns


def main():
    w = load_widget()
    out = {"stops": w["THEMES"]["Moss"]["stops"], "trees": []}
    w["set_theme"]("Moss")
    for tid in IDS:
        tree = w["build_tree"](zlib.crc32(tid.encode()), vary=True) if tid else w["build_tree"]()
        entry = {
            "id": tid, "crc": zlib.crc32(tid.encode()),
            "segs": [[s["x1"], s["y1"], s["x2"], s["y2"], s["w1"], s["birth"]] for s in tree["segs"]],
            "pads": [[p["x"], p["y"], p["size"], p["birth"]] for p in tree["pads"]],
            "shoots": [[s["x"], s["y"], s["a"], s["len"], s["birth"]] for s in tree["shoots"]],
            "leaves": {},
        }
        for g in GROWTH:
            entry["leaves"][str(g)] = [[x, y] for x, y, *_ in w["each_leaf"](g, tree)]
        out["trees"].append(entry)
    out["colors"] = [[g, list(w["leaf_color"](g)[:3])] for g in (0, 0.3, 0.55, 0.75, 0.85, 0.95, 1.0)]
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, separators=(",", ":"))
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
