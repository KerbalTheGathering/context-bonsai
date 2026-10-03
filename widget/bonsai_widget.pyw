#!/usr/bin/env pythonw
"""Context Bonsai: a desktop widget that grows with the active Claude Code session's context.

Reads the newest transcript in ~/.claude/projects (no model calls, no usage).
Drag to move. Right-click for options. Launching it again while it runs closes it.
"""
import colorsys
import ctypes
import glob
import json
import math
import os
import random
import subprocess
import sys
import time
import tkinter as tk

from PIL import Image, ImageDraw, ImageFont, ImageTk

HOME = os.path.expanduser("~")
PROJECTS = os.path.join(HOME, ".claude", "projects")
HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG = os.path.join(HERE, "bonsai.json")
SIGNAL = os.path.join(HERE, "signal.json")  # written by the PreCompact hook (precompact_signal.py)
sys.path.insert(0, os.path.join(HOME, ".claude", "hooks"))
try:
    from rehydrate import running_jobs
except Exception:  # widget still works without the hook
    def running_jobs(_):
        return []

DEFAULTS = {"window": 1_000_000, "x": None, "y": None, "topmost": True, "pinned": None, "theme": "Moss"}
TITLE = "Context Bonsai"
TAU = math.pi * 2
BASELINE = 0.14
SS = 2  # supersampling for smooth edges
CROP = (30, 0, 570, 462)  # part of the 600x480 mockup scene the widget shows
GROVE_CROP = (70, 0, 530, 462)  # tighter crop for the small trees in the grove
GROVE_MINUTES = 30  # sessions active within this window get a tree
GROVE_MAX = 4
FONTS = "C:/Windows/Fonts/"

# Each theme: panel/scene colors, plus leaf color stops (context fill, hue, saturation %, lightness %)
# running from "plenty of room" to "compact now".
THEMES = {
    "Moss": {
        "colors": {
            "panel": "#1A201F", "wall": "#151A19", "wall2": "#1D2422", "ink": "#E3E7E0", "muted": "#9AA39B",
            "line": "#2F3835", "pot": "#4E8990", "potDark": "#33616A", "potHi": "#78AEB4", "wood": "#7A5A40",
            "woodDark": "#59402D", "soil": "#2A221C", "moss": "#5E7A40", "bark": "#7A6552", "barkHi": "#9C8469",
            "ok": "#8DBA6E", "warn": "#E0A94A", "crit": "#E7795A"},
        "stops": [(0, 102, 46, 53), (0.5, 118, 42, 44), (0.7, 128, 38, 38), (0.8, 52, 68, 52),
                  (0.9, 26, 72, 51), (1.0, 8, 64, 45)]},
    "Paper": {
        "colors": {
            "panel": "#EEF0E9", "wall": "#E6E8E1", "wall2": "#D6DACF", "ink": "#1E2420", "muted": "#5B645D",
            "line": "#C3C9BD", "pot": "#3C6A70", "potDark": "#2A4D52", "potHi": "#5E8F94", "wood": "#6B4A33",
            "woodDark": "#4C3423", "soil": "#3A2E25", "moss": "#6E8A4C", "bark": "#4A3A2E", "barkHi": "#6D5643",
            "ok": "#4F7A3A", "warn": "#A8701A", "crit": "#B0472B"},
        "stops": [(0, 102, 46, 46), (0.5, 118, 42, 37), (0.7, 128, 38, 31), (0.8, 52, 68, 45),
                  (0.9, 26, 72, 44), (1.0, 8, 64, 38)]},
    "Sakura": {
        "colors": {
            "panel": "#221923", "wall": "#1E1620", "wall2": "#2A1E2B", "ink": "#F3E6EC", "muted": "#B39CAA",
            "line": "#3D2D3D", "pot": "#33466A", "potDark": "#22304C", "potHi": "#6680B0", "wood": "#5A3B3A",
            "woodDark": "#3E2726", "soil": "#2A1E1E", "moss": "#5F6E45", "bark": "#5E444B", "barkHi": "#80616A",
            "ok": "#F2A7C3", "warn": "#F07FA8", "crit": "#E8506F"},
        "stops": [(0, 340, 75, 90), (0.5, 336, 72, 83), (0.7, 332, 74, 75), (0.8, 330, 76, 66),
                  (0.9, 342, 78, 56), (1.0, 350, 76, 48)]},
    "Midnight": {
        "colors": {
            "panel": "#0F172A", "wall": "#0B1222", "wall2": "#141E33", "ink": "#E2E8F5", "muted": "#8C9AB5",
            "line": "#24304A", "pot": "#3B4A6B", "potDark": "#283552", "potHi": "#6F86B8", "wood": "#3A3F55",
            "woodDark": "#262B3D", "soil": "#151A26", "moss": "#2F5A5A", "bark": "#58637D", "barkHi": "#7D8AA6",
            "ok": "#5EE0C8", "warn": "#F5C062", "crit": "#FF6B7A"},
        "stops": [(0, 166, 72, 58), (0.5, 174, 66, 50), (0.7, 188, 60, 46), (0.8, 42, 85, 60),
                  (0.9, 20, 90, 60), (1.0, 355, 85, 62)]},
    "Sumi-e": {
        "colors": {
            "panel": "#F4EEE1", "wall": "#F1EADB", "wall2": "#E6DCC6", "ink": "#1C1A17", "muted": "#6E675C",
            "line": "#D3C8B1", "pot": "#3A3835", "potDark": "#22211F", "potHi": "#6B6862", "wood": "#8B7355",
            "woodDark": "#6A5640", "soil": "#2E2A25", "moss": "#7D8463", "bark": "#24221F", "barkHi": "#4A4640",
            "ok": "#3F4A3A", "warn": "#9A6A2E", "crit": "#B8322A"},
        "stops": [(0, 95, 14, 42), (0.5, 100, 10, 30), (0.7, 110, 8, 22), (0.8, 28, 32, 30),
                  (0.9, 10, 62, 40), (1.0, 4, 72, 42)]},
}
C = {}
STOPS = []


def set_theme(name):
    global STOPS
    theme = THEMES.get(name) or THEMES["Moss"]
    C.clear()
    C.update(theme["colors"])
    STOPS = theme["stops"]


set_theme("Moss")


def clamp(v, a, b):
    return min(b, max(a, v))


def lerp(a, b, t):
    return a + (b - a) * t


def rgb(hexstr):
    h = hexstr.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def mulberry(seed):
    s = [seed & 0xFFFFFFFF]

    def imul(a, b):
        return (a * b) & 0xFFFFFFFF

    def r():
        s[0] = (s[0] + 0x6D2B79F5) & 0xFFFFFFFF
        t = s[0]
        t = imul(t ^ (t >> 15), 1 | t)
        t = (((t + imul(t ^ (t >> 7), 61 | t)) & 0xFFFFFFFF) ^ t) & 0xFFFFFFFF
        return ((t ^ (t >> 14)) & 0xFFFFFFFF) / 4294967296
    return r


# ---------- tree structure (same shape as the mockup) ----------
def build_tree(seed=11):
    r = mulberry(seed)
    segs, pads, shoots = [], [], []
    S = 1.45

    def make_pad(x, y, birth, scale):
        leaves = []
        for _ in range(30):
            ang, rad = r() * TAU, math.sqrt(r())
            leaves.append({"dx": math.cos(ang) * rad, "dy": math.sin(ang) * rad * 0.55 - 0.18,
                           "s": 0.6 + r() * 0.6, "turn": r() * 0.12, "rot": r() * TAU, "order": r()})
        return {"x": x, "y": y, "birth": birth, "leaves": leaves, "size": (17 + r() * 8) * scale * 1.35}

    def branch(x, y, a, ln, w, depth, birth):
        ex = x + math.cos(a) * ln
        ey = y + math.sin(a) * ln + (ln * 0.06 if depth == 0 else 0)
        segs.append({"x1": x, "y1": y, "x2": ex, "y2": ey, "w1": w, "w2": w * 0.68, "birth": birth, "dur": 0.045})
        end = birth + 0.045
        if depth >= 3 or ln < 13 * S:
            pads.append(make_pad(ex, ey, end, 1))
            return
        for k in range(2):
            spread = (-1 if k == 0 else 1) * (0.34 + r() * 0.3)
            na = a + spread
            if math.sin(na) > 0.2:
                na = a + spread * 0.25
            branch(ex, ey, na, ln * (0.62 + r() * 0.12), w * 0.68, depth + 1, end + 0.005 + r() * 0.025)
        pads.append(make_pad(ex, ey, end + (0.005 if depth == 0 else 0.04), 0.7 if depth == 0 else 0.85))

    x, y, w, side = 300, 398, 30, 1
    trunk_n = 6
    for i in range(trunk_n):
        ln = (46 - i * 4) * S
        a = -math.pi / 2 + (1 if i % 2 else -1) * 0.34 + (r() - 0.5) * 0.08
        nx, ny = x + math.cos(a) * ln, y + math.sin(a) * ln
        birth = i * 0.03
        segs.append({"x1": x, "y1": y, "x2": nx, "y2": ny, "w1": w, "w2": w * 0.83, "birth": birth,
                     "dur": 0.04, "trunk": True})
        if i >= 1:
            side = -side
            ba = -0.16 - r() * 0.22 if side > 0 else math.pi + 0.16 + r() * 0.22
            branch(nx, ny, ba, (66 - i * 7 + r() * 12) * S, w * 0.42, 0, birth + 0.02)
        x, y, w = nx, ny, w * 0.83
    branch(x, y, -math.pi / 2 + (r() - 0.5) * 0.4, 26 * S, w * 0.85, 1, trunk_n * 0.03 + 0.02)

    for p in pads:
        if r() < 0.5:
            a = -math.pi / 2 + (r() - 0.5) * 2.0
            ln = (28 + r() * 36) * S
            leaves = [{"t": 0.35 + r() * 0.65, "s": 0.5 + r() * 0.4, "turn": r() * 0.12,
                       "side": -1 if r() < 0.5 else 1, "rot": r() * TAU} for _ in range(5)]
            shoots.append({"x": p["x"], "y": p["y"], "a": a, "len": ln, "bend": (r() - 0.5) * 0.6,
                           "birth": 0.64 + r() * 0.26, "leaves": leaves})
    return {"segs": segs, "pads": pads, "shoots": shoots}


TREE = build_tree()


def make_pile(count, seed):
    r = mulberry(seed)
    out = []
    n = min(90, round(count))
    for _ in range(n):
        left = r() < 0.5
        x = lerp(128, 168, r() ** 0.7) if left else lerp(432, 472, 1 - r() ** 0.7)
        out.append({"x": x, "y": 437 - r() * 3 * (1 - abs((x - 300) / 300)), "rot": r() * TAU,
                    "s": 0.6 + r() * 0.5, "hue": r()})
    for _ in range(n // 3):
        out.append({"x": lerp(185, 415, r()), "y": 399 + r() * 2, "rot": r() * TAU, "s": 0.5 + r() * 0.4,
                    "hue": r()})
    return out


def leaf_color(g, alpha=255):
    g = clamp(g, 0, 1)
    i = 0
    while i < len(STOPS) - 2 and g > STOPS[i + 1][0]:
        i += 1
    a, b = STOPS[i], STOPS[i + 1]
    t = clamp((g - a[0]) / (b[0] - a[0]), 0, 1)
    dh = (b[1] - a[1] + 540) % 360 - 180  # blend hue the short way round the color wheel
    h, s, l = (a[1] + dh * t) % 360, lerp(a[2], b[2], t), lerp(a[3], b[3], t)
    rr, gg, bb = colorsys.hls_to_rgb(h / 360, l / 100, s / 100)
    return (int(rr * 255), int(gg * 255), int(bb * 255), alpha)


def lushness(g):
    return 0.6 + 0.55 * clamp(g, 0, 1) + 0.35 * clamp((g - 0.7) / 0.3, 0, 1)


def shoot_point(sh, t):
    ex, ey = sh["x"] + math.cos(sh["a"]) * sh["len"], sh["y"] + math.sin(sh["a"]) * sh["len"]
    perp = sh["a"] + math.pi / 2
    cx = (sh["x"] + ex) / 2 + math.cos(perp) * sh["len"] * sh["bend"] * 0.5
    cy = (sh["y"] + ey) / 2 + math.sin(perp) * sh["len"] * sh["bend"] * 0.5
    u = 1 - t
    return (u * u * sh["x"] + 2 * u * t * cx + t * t * ex, u * u * sh["y"] + 2 * u * t * cy + t * t * ey)


def each_leaf(g):
    """Yield (x, y, size, rot, color_g, birth) for every visible leaf at growth g."""
    lush = lushness(g)
    for p in TREE["pads"]:
        f = clamp((g - p["birth"]) / 0.12, 0, 1)
        if f <= 0:
            continue
        R = p["size"] * lush * (0.45 + 0.55 * f)
        for l in p["leaves"]:
            if l["order"] <= f:
                yield p["x"] + l["dx"] * R, p["y"] + l["dy"] * R, l["s"], l["rot"], g + l["turn"], p["birth"]
    for sh in TREE["shoots"]:
        f = clamp((g - sh["birth"]) / 0.08, 0, 1)
        if f <= 0:
            continue
        perp = sh["a"] + math.pi / 2
        for l in sh["leaves"]:
            if l["t"] <= f:
                px, py = shoot_point(sh, l["t"])
                yield (px + math.cos(perp) * 4 * l["side"], py + math.sin(perp) * 4 * l["side"], l["s"], l["rot"],
                       g + l["turn"], sh["birth"])


# ---------- scene rendering ----------
class Scene:
    def __init__(self, width, crop=None):
        self.crop = crop or CROP
        self.k = width / (self.crop[2] - self.crop[0])  # virtual units -> output pixels
        self.w = width
        self.h = round((self.crop[3] - self.crop[1]) * self.k)
        self.bg = self._background()

    def P(self, x, y):
        return ((x - self.crop[0]) * self.k * SS, (y - self.crop[1]) * self.k * SS)

    def L(self, v):
        return v * self.k * SS

    def _background(self):
        W, H = self.w * SS, self.h * SS
        img = Image.new("RGBA", (W, H))
        d = ImageDraw.Draw(img)
        a, b = rgb(C["wall"]), rgb(C["wall2"])
        shelf = self.P(0, 452)[1]
        for yy in range(H):
            t = yy / H
            d.line([(0, yy), (W, yy)], fill=tuple(int(lerp(a[i], b[i], t)) for i in range(3)))
        d.rectangle([0, shelf, W, H], fill=C["wall2"])
        d.rectangle([0, shelf, W, shelf + self.L(1.5)], fill=C["line"])
        # stand
        self.rect(d, 140, 446, 14, 10, C["woodDark"])
        self.rect(d, 446, 446, 14, 10, C["woodDark"])
        self.rect(d, 116, 438, 368, 10, C["wood"])
        self.rect(d, 116, 446, 368, 2, C["woodDark"])
        # pot
        self.rect(d, 190, 430, 22, 8, C["potDark"])
        self.rect(d, 388, 430, 22, 8, C["potDark"])
        d.polygon([self.P(172, 402), self.P(428, 402), self.P(412, 432), self.P(188, 432)], fill=C["pot"])
        self.rect(d, 166, 396, 268, 8, C["potDark"])
        self.rect(d, 180, 406, 240, 2, C["potHi"])
        self.rect(d, 176, 394, 248, 4, C["soil"])
        mr = mulberry(5)
        for _ in range(46):
            cx, cy = 180 + mr() * 240, 394 + mr() * 2
            rx, ry = 3 + mr() * 5, 1.6 + mr() * 1.4
            self.ellipse(d, cx, cy, rx, ry, C["moss"])
        return img

    def rect(self, d, x, y, w, h, fill):
        x0, y0 = self.P(x, y)
        x1, y1 = self.P(x + w, y + h)
        d.rectangle([x0, y0, x1, y1], fill=fill)

    def ellipse(self, d, cx, cy, rx, ry, fill):
        x0, y0 = self.P(cx - rx, cy - ry)
        x1, y1 = self.P(cx + rx, cy + ry)
        d.ellipse([x0, y0, x1, y1], fill=fill)

    def leaf(self, d, x, y, s, rot, fill):
        ca, sa = math.cos(rot), math.sin(rot)
        rx, ry = 4.4 * s, 2.4 * s
        pts = []
        for i in range(10):
            t = i / 10 * TAU
            ex, ey = math.cos(t) * rx, math.sin(t) * ry
            pts.append(self.P(x + ex * ca - ey * sa, y + ex * sa + ey * ca))
        d.polygon(pts, fill=fill)

    def seg(self, d, x1, y1, x2, y2, width, fill):
        a, b = self.P(x1, y1), self.P(x2, y2)
        w = max(1.0, self.L(width))
        d.line([a, b], fill=fill, width=round(w))
        r = w / 2
        for (px, py) in (a, b):  # round caps
            d.ellipse([px - r, py - r, px + r, py + r], fill=fill)

    def render(self, g, cc, pile):
        img = self.bg.copy()
        d = ImageDraw.Draw(img)
        # compaction tally marks on the pot
        n = min(cc, 12)
        for i in range(n):
            tx = 286 + (i % 6) * 6 - min(cc, 6) * 3 + 3 + (3 if i >= 6 else 0)
            ty = 424 if i >= 6 else 416
            self.seg(d, tx, ty - 5, tx, ty + 2, 1.6, C["potHi"])
        for l in pile:
            self.leaf(d, l["x"], l["y"], l["s"], l["rot"], leaf_color(0.82 + l["hue"] * 0.2, 230))
        thick = 1 + 0.08 * min(cc, 6)
        for s in TREE["segs"]:
            first = s.get("trunk") and s["birth"] == 0
            p = clamp((g - s["birth"]) / s["dur"], 0, 1)
            if p <= 0 and not first:
                continue
            pp = max(p, 0.35) if first else p
            x2, y2 = lerp(s["x1"], s["x2"], pp), lerp(s["y1"], s["y2"], pp)
            if s.get("trunk"):
                wmul = thick * (0.55 + 0.45 * clamp(g / 0.5, 0, 1))
            else:
                wmul = 0.6 + 0.4 * clamp(g / 0.6, 0, 1)
            width = max(1.2, lerp(s["w1"], s["w2"], 0.5) * wmul)
            self.seg(d, s["x1"], s["y1"], x2, y2, width, C["bark"])
            if s.get("trunk"):
                self.seg(d, s["x1"] - 3, s["y1"], x2 - 3, y2, max(1, width * 0.22), C["barkHi"])
        for sh in TREE["shoots"]:
            f = clamp((g - sh["birth"]) / 0.08, 0, 1)
            if f <= 0:
                continue
            pts = [self.P(sh["x"], sh["y"])] + [self.P(*shoot_point(sh, i / 12 * f)) for i in range(1, 13)]
            d.line(pts, fill=C["bark"], width=max(1, round(self.L(1.5))), joint="curve")
        # soft canopy shadows on their own layer
        shade = Image.new("RGBA", img.size)
        sd = ImageDraw.Draw(shade)
        lush = lushness(g)
        for p in TREE["pads"]:
            f = clamp((g - p["birth"]) / 0.12, 0, 1)
            if f > 0:
                R = p["size"] * lush * (0.45 + 0.55 * f)
                self.ellipse(sd, p["x"], p["y"] - R * 0.12, R * 1.02, R * 0.5, leaf_color(g, 56))
        img.alpha_composite(shade)
        for x, y, s, rot, gl, _ in each_leaf(g):
            self.leaf(d, x, y, s, rot, leaf_color(gl, 255))
        return img.resize((self.w, self.h), Image.LANCZOS)


# ---------- session data ----------
class Session:
    def __init__(self, cfg, path=None):
        self.cfg = cfg
        self.fixed = path  # follow this transcript only; None = pinned or newest
        self.path = None
        self.offset = 0
        self.seen_cc = None  # compaction / restore counts the window has already reacted to
        self.seen_restores = None
        self.title = None
        self.compactions = 0
        self.last_pre = None
        self.last_duration = None
        self.restores = 0
        self.restored_msg = None
        self.cwd = None
        self.tokens = None
        self.after_compact = False
        self.mtime = 0
        self.jobs = []
        self.git = (None, None)
        self.git_at = 0

    def pick(self):
        if self.fixed:
            return self.fixed if os.path.exists(self.fixed) else None
        pinned = self.cfg.get("pinned")
        if pinned and os.path.exists(pinned):
            return pinned
        files = glob.glob(os.path.join(PROJECTS, "*", "*.jsonl"))
        return max(files, key=os.path.getmtime) if files else None

    @property
    def name(self):
        return os.path.basename(os.path.normpath(self.cwd)) if self.cwd else "session"

    def refresh(self):
        """Returns True when the data changed."""
        path = self.pick()
        if not path:
            return False
        switched = path != self.path
        if switched:
            self.path, self.offset, self.compactions, self.last_pre = path, 0, 0, None
            self.last_duration, self.restores, self.restored_msg, self.title = None, 0, None, None
            self.cwd, self.tokens, self.jobs, self.git_at = None, None, [], 0
        mtime = os.path.getmtime(path)
        changed = switched or mtime != self.mtime
        if changed:
            self.mtime = mtime
            self._scan_new(path)
            self._read_tokens(path)
            try:
                self.jobs = running_jobs(path)
            except Exception:
                self.jobs = []
        if self.cwd and time.time() - self.git_at > 10:
            self.git_at = time.time()
            self.git = git_state(self.cwd)
            changed = True
        return changed

    def _scan_new(self, path):
        """Count compactions and catch the cwd, reading only what was appended since last time."""
        try:
            with open(path, "rb") as f:
                f.seek(self.offset)
                chunk = f.read()
        except OSError:
            return
        end = chunk.rfind(b"\n")
        if end < 0:
            return
        self.offset += end + 1
        for raw in chunk[:end].split(b"\n"):
            if b'"compact_boundary"' in raw:
                self.compactions += 1
                try:
                    meta = json.loads(raw).get("compactMetadata") or {}
                    self.last_pre = meta.get("preTokens")
                    self.last_duration = (meta.get("durationMs") or 0) / 1000 or None
                except ValueError:
                    pass
            if b'"custom-title"' in raw:  # the sidebar title the desktop app saves
                try:
                    self.title = clean_title(json.loads(raw).get("customTitle"))
                except ValueError:
                    pass
            if b'"hook_system_message"' in raw and "restored:".encode() in raw:
                try:
                    self.restored_msg = (json.loads(raw).get("attachment") or {}).get("content")
                    self.restores += 1
                except ValueError:
                    pass
            if b'"cwd"' in raw:
                try:
                    self.cwd = json.loads(raw).get("cwd") or self.cwd
                except ValueError:
                    pass

    def _read_tokens(self, path):
        # Image tool results are stored inline and can be hundreds of KB each, so widen the tail if needed.
        for span in (600_000, 6_000_000, None):
            try:
                with open(path, "rb") as f:
                    size = os.path.getsize(path)
                    f.seek(0 if span is None else max(0, size - span))
                    lines = f.read().decode("utf-8", "replace").splitlines()
            except OSError:
                return
            if self._tokens_from(lines) or span is None or span >= size:
                return

    def _tokens_from(self, lines):
        """Sets tokens/after_compact from the newest relevant line. Returns False if none was found."""
        self.after_compact = False
        for line in reversed(lines):
            if '"compact_boundary"' in line:
                self.after_compact = True  # no reply since the compact yet
                self.tokens = None
                return True
            if '"usage"' not in line or '"isSidechain":true' in line:
                continue
            try:
                u = (json.loads(line).get("message") or {}).get("usage") or {}
            except ValueError:
                continue
            if u:
                self.tokens = (u.get("input_tokens", 0) + u.get("cache_read_input_tokens", 0)
                               + u.get("cache_creation_input_tokens", 0))
                return True
        return False

    @property
    def g(self):
        if self.after_compact or self.tokens is None:
            return BASELINE if self.after_compact else 0.06
        return clamp(self.tokens / self.cfg["window"], 0, 1)


def clean_title(t):
    """Drop emoji and odd spacing the card's fonts can't draw."""
    if not t:
        return None
    keep = "".join(ch for ch in t if ord(ch) < 0x2190 or 0x2E80 <= ord(ch) < 0x1F000)
    return " ".join(keep.split()) or None


def git_state(cwd):
    def run(*args):
        try:
            r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, timeout=2,
                               creationflags=0x08000000)  # CREATE_NO_WINDOW
            return r.stdout if r.returncode == 0 else None
        except (OSError, subprocess.TimeoutExpired):
            return None
    br = run("branch", "--show-current")
    if br is None:
        return (None, None)
    st = run("status", "--porcelain") or ""
    return (br.strip() or "detached", len([l for l in st.splitlines() if l.strip()]))


def stage_for(g):
    if g < 0.35:
        return "New growth", "ok", "Plenty of room."
    if g < 0.66:
        return "Full canopy", "ok", "Deep in a task, still comfortable."
    if g < 0.80:
        return "Wild shoots", "warn", "Old detail is piling up. Fine for now."
    if g < 0.92:
        return "Leaves turning", "warn", "Finish this step, then compact."
    return "Dropping leaves", "crit", "Compact now. Auto-compact is close."


def fmt_k(t):
    return f"{t / 1e6:.2g}M" if t >= 1e6 else f"{round(t / 1000)}k"


def fmt_ago(sec):
    if sec < 60:
        return "live"
    if sec < 3600:
        return f"idle {int(sec // 60)}m"
    return f"idle {sec / 3600:.0f}h"


# ---------- window ----------
PHASE_TEXT = {  # chip label, chip color key
    "armed": ("Ready to prune", "warn"),
    "compacting": ("Pruning", "warn"),
    "pruned": ("Regrowing", "ok"),
    "watering": ("Regrowing", "ok"),
}


def is_light():
    r, g, b = rgb(C["panel"])
    return (0.299 * r + 0.587 * g + 0.114 * b) > 140


class Widget:
    BASE_W = 248

    def __init__(self):
        self.cfg = load_config()
        set_theme(self.cfg["theme"])
        self.root = tk.Tk()
        self.root.withdraw()
        self.f = self.root.winfo_fpixels("1i") / 96
        self.W = round(self.BASE_W * self.f)
        self.pad = round(14 * self.f)
        self.scene = Scene(self.W - 2 * self.pad)
        self.sessions = {}  # transcript path -> Session, one per tree in the grove
        self.order = []  # grove order, oldest tree first so trees don't jump around
        self.focus_path = None
        self.follow = True  # focus follows the newest session until the user picks a tree
        self.resume_follow = False
        self.view = "focus"  # "focus" = one full card, "grove" = a tree per active session
        self._empty = Session(self.cfg, path="")
        self.grove_scene = None
        self.grove_cache = {}
        self.hits = []  # clickable regions from the last draw: (rect, action, arg)
        self.hover_key = None
        self._action = None
        self.anchor = None
        self.last_size = None
        self.fonts = {
            "title": font("seguisb.ttf", 13 * self.f), "big": font("seguisb.ttf", 30 * self.f),
            "body": font("segoeui.ttf", 11 * self.f), "small": font("segoeui.ttf", 10 * self.f),
            "mono": font("CascadiaMono.ttf", 9 * self.f, "consola.ttf"),
            "button": font("seguisb.ttf", 10 * self.f), "symbol": font("seguisym.ttf", 11 * self.f),
        }
        self.g = None
        self.tween = None
        self.particles = []
        self.tree_key = None
        self.tree_img = None
        self.pile = []
        self.ambient = 0
        self.frame_img = None
        # compact flow: idle -> armed (button clicked) -> compacting (PreCompact hook) -> pruned -> watering
        self.phase = "idle"
        self.phase_at = 0
        self.found_app = True
        self.pending_restore = None
        self.caption = None  # (text, color key, until)
        self.preview = False
        self.shears = {"x": 470.0, "y": 110.0, "tx": 470.0, "ty": 110.0, "next": 0, "snip_at": None, "snap": 0}
        self.leaf_cache = (None, [])
        try:
            self.signal_seen = os.path.getmtime(SIGNAL)
        except OSError:
            self.signal_seen = 0

        r = self.root
        r.title(TITLE)
        r.overrideredirect(True)
        r.attributes("-topmost", self.cfg["topmost"])
        r.configure(bg=C["panel"])
        self.label = tk.Label(r, bd=0, padx=0, pady=0, highlightthickness=0, bg=C["panel"], cursor="fleur")
        self.label.pack()
        self.label.bind("<ButtonPress-1>", self.press)
        self.label.bind("<B1-Motion>", self.drag_move)
        self.label.bind("<ButtonRelease-1>", self.release)
        self.label.bind("<Motion>", self.motion)
        self.label.bind("<Leave>", lambda e: self.set_hover(None))
        self.label.bind("<Button-3>", self.menu)
        self.topvar = tk.BooleanVar(value=self.cfg["topmost"])
        self.pinvar = tk.BooleanVar(value=bool(self.cfg.get("pinned")))
        self.themevar = tk.StringVar(value=self.cfg["theme"] if self.cfg["theme"] in THEMES else "Moss")

        self.refresh_sessions()
        if len(self.order) > 1:
            self.view = "grove"
        self.g = self.session.g
        self.draw()
        r.deiconify()
        r.update_idletasks()
        round_corners(r)
        r.after(2000, self.poll)
        r.after(50, self.tick)

    # --- data ---
    def poll(self):
        try:
            self.step()
        finally:
            self.root.after(2000 if self.phase == "idle" else 500, self.poll)

    @property
    def session(self):
        return self.sessions.get(self.focus_path) or self._empty

    def active_paths(self):
        """Transcripts touched in the last GROVE_MINUTES, newest first (the newest overall if none)."""
        now, found = time.time(), []
        for p in glob.glob(os.path.join(PROJECTS, "*", "*.jsonl")):
            try:
                found.append((os.path.getmtime(p), p))
            except OSError:
                pass
        found.sort(reverse=True)
        recent = [p for m, p in found if now - m < GROVE_MINUTES * 60][:GROVE_MAX]
        return recent or [p for _, p in found[:1]]

    def refresh_sessions(self):
        paths = self.active_paths()
        pinned = self.cfg.get("pinned")
        if pinned and os.path.exists(pinned) and pinned not in paths:
            paths = [pinned] + paths[:GROVE_MAX - 1]
        focus = self.focus_path
        if self.phase == "idle" and (self.follow or focus is None):
            focus = pinned if pinned and os.path.exists(pinned) else (paths[0] if paths else None)
        if focus and focus not in paths:
            paths.append(focus)  # keep the tree you opened even after it goes quiet
        for p in paths:
            s = self.sessions.get(p)
            if s is None:
                s = self.sessions[p] = Session(self.cfg, p)
                s.refresh()
                s.seen_cc, s.seen_restores = s.compactions, s.restores
            else:
                s.g_before = s.g
                s.refresh()
        for p in list(self.sessions):
            if p not in paths:
                del self.sessions[p]
                self.grove_cache.pop(p, None)
        self.order = [p for p in self.order if p in paths] + [p for p in paths if p not in self.order]
        if focus != self.focus_path:
            self.set_focus(focus)

    def set_focus(self, path):
        if path == self.focus_path:
            return
        self.focus_path = path
        self.g = self.session.g
        self.particles, self.pile, self.tween, self.tree_key = [], [], None, None
        self.caption = None

    def find_session(self, path):
        want = os.path.normcase(path or "")
        return next((p for p in self.sessions if os.path.normcase(p) == want), None)

    def step(self):
        now = time.time()
        self.refresh_sessions()
        self.check_signal()
        for p, o in self.sessions.items():
            if o.compactions > (o.seen_cc or 0) and p != self.focus_path:
                if self.view == "grove" and self.phase == "idle":
                    self.set_focus(p)  # show the compaction on that session's own card
                    self.view = "focus"
                    self.g = max(getattr(o, "g_before", o.g), o.g)
                else:
                    o.seen_cc, o.seen_restores = o.compactions, o.restores
        s = self.session
        if s.compactions > (s.seen_cc or 0):
            s.seen_cc = s.compactions
            self.start_prune(max(self.g, getattr(s, "g_before", 0)), s.g)
        if s.restores > (s.seen_restores or 0):
            s.seen_restores = s.restores
            self.pending_restore = s.restored_msg or ""
        if self.view == "grove" and len(self.order) <= 1:
            self.view = "focus"
        if self.phase == "pruned" and self.tween is None and (
                self.pending_restore is not None or now - self.phase_at > 8):
            self.water(self.pending_restore)
        if self.phase == "armed" and now - self.phase_at > 180:
            self.set_phase("idle")
            self.caption = ("No compaction seen. Click Compact to try again.", "muted", now + 8)
        if self.phase == "compacting" and now - self.phase_at > 600:
            self.set_phase("idle")
            if self.resume_follow:
                self.follow, self.resume_follow = True, False
        if self.phase == "idle" and self.tween is None:
            self.g = s.g
        self.draw()

    def check_signal(self):
        try:
            mtime = os.path.getmtime(SIGNAL)
        except OSError:
            return
        if mtime <= self.signal_seen:
            return
        self.signal_seen = mtime
        try:
            with open(SIGNAL, encoding="utf-8") as fh:
                sig = json.load(fh)
        except (OSError, ValueError):
            return
        path = sig.get("transcript") or ""
        pinned = self.cfg.get("pinned")
        if pinned and os.path.normcase(path) != os.path.normcase(pinned):
            return
        found = self.find_session(path)
        if not found and os.path.exists(path):
            s = self.sessions[path] = Session(self.cfg, path)
            s.refresh()
            s.seen_cc, s.seen_restores = s.compactions, s.restores
            self.order.append(path)
            found = path
        if found:
            if found != self.focus_path:
                self.set_focus(found)
            self.resume_follow = self.follow
            self.follow = False  # stay on this tree until the animation finishes
            self.view = "focus"
            self.set_phase("compacting")

    def set_phase(self, phase):
        self.phase, self.phase_at = phase, time.time()
        if phase != "idle":
            self.caption = None

    def start_prune(self, frm, to):
        self.prune(frm, to)
        self.set_phase("pruned")

    def prune(self, frm, to):
        falling = [l for l in each_leaf(frm) if l[5] > BASELINE]
        for x, y, s, rot, gl, _ in random.sample(falling, min(130, len(falling))):
            self.spawn(x, y, s, rot, leaf_color(gl), burst=True)
        dropped = max(0.0, frm - to)
        self.pile = make_pile(dropped * 110, 100 + self.session.compactions)
        self.tween = (frm, to, time.time() + 0.2, 0.9)

    def water(self, msg):
        """Rehydrate: rain onto the soil, ripples, then new buds open across the canopy."""
        self.set_phase("watering")
        self.pending_restore = None
        for i in range(28):
            self.particles.append({"kind": "drop", "x": lerp(205, 395, random.random()), "y": 60 + random.random() * 90,
                                   "vy": 4 + random.random() * 2, "life": 1.0, "wait": i * 45 + random.random() * 80})
        leaves = list(each_leaf(min(1.0, max(self.session.g, BASELINE) + 0.15)))  # buds where growth comes next
        for i, (x, y, *_r) in enumerate(random.sample(leaves, min(26, len(leaves)))):
            self.particles.append({"kind": "bud", "x": x, "y": y, "life": 1.0, "wait": 1300 + i * 55})
        text = (msg or "").replace("↻ restored:", "").strip() or "state restored"
        self.root.after(3400, lambda: self.finish_water(text))

    def finish_water(self, text):
        self.set_phase("idle")
        self.preview = False
        if self.resume_follow:
            self.follow, self.resume_follow = True, False
        self.caption = ("Restored: " + text, "ok", time.time() + 12)

    def spawn(self, x, y, s, rot, color, burst):
        self.particles.append({
            "kind": "leaf", "x": x, "y": y, "s": s, "rot": rot, "color": color, "life": 1.0, "landed": False,
            "vx": (random.random() - 0.5) * (1.6 if burst else 0.5), "vy": -random.random() * 1.2 if burst else 0,
            "vr": (random.random() - 0.5) * 0.15, "sway": random.random() * TAU})

    # --- compact button ---
    def on_button(self):
        if self.phase == "armed":
            self.set_phase("idle")
            return
        if self.phase != "idle":
            return
        self.root.clipboard_clear()
        self.root.clipboard_append("/compact")
        self.root.update()
        self.found_app = focus_claude()
        self.set_phase("armed")

    def run_preview(self):
        """Plays the whole compact -> prune -> rehydrate sequence without touching the session."""
        if self.phase != "idle":
            return
        self.preview = True
        frm, to = max(self.g, 0.9), self.g
        self.g = frm
        self.set_phase("compacting")

        def done():
            self.prune(frm, to)
            self.set_phase("pruned")
            self.pending_restore = "preview · nothing was compacted"
        self.root.after(4500, done)

    # --- animation ---
    def leaves_at(self, g):
        key = round(g, 3)
        if self.leaf_cache[0] != key:
            self.leaf_cache = (key, list(each_leaf(g)))
        return self.leaf_cache[1]

    def tick(self):
        dt = 50
        now = time.time()
        active = self.phase in ("armed", "compacting")
        if self.tween:
            frm, to, t0, dur = self.tween
            if now >= t0:
                t = clamp((now - t0) / dur, 0, 1)
                self.g = lerp(frm, to, 1 - (1 - t) ** 3)
                if t >= 1:
                    self.tween = None
                    self.g = to if self.preview else self.session.g
            active = True
        sh = self.shears
        if self.phase == "compacting":
            if now >= sh["next"]:
                pool = self.leaves_at(self.g)
                if pool:
                    x, y, *_r = random.choice(pool)
                    sh["tx"], sh["ty"] = x + 30, y - 24  # pivot up-right so the blade tips reach the leaf
                sh["next"], sh["snip_at"] = now + 1.1, now + 0.6
            if sh["snip_at"] and now >= sh["snip_at"]:
                sh["snip_at"], sh["snap"] = None, now
                for x, y, s, rot, gl, _ in random.sample(self.leaves_at(self.g), min(3, len(self.leaves_at(self.g)))):
                    self.spawn(sh["tx"] - 30 + random.uniform(-5, 5), sh["ty"] + 24 + random.uniform(-4, 4),
                               s, rot, leaf_color(gl), burst=True)
        else:
            sh["tx"], sh["ty"] = 470, 110 + math.sin(now * 2) * 4
        sh["x"] += (sh["tx"] - sh["x"]) * 0.2
        sh["y"] += (sh["ty"] - sh["y"]) * 0.2
        if self.view == "focus" and self.phase == "idle" and self.g > 0.9 and not self.tween:
            self.ambient += dt
            if self.ambient > 600:
                self.ambient = 0
                pool = [l for l in self.leaves_at(self.g) if l[4] > 0.93]
                if pool:
                    x, y, s, rot, gl, _ = random.choice(pool)
                    self.spawn(x, y, s, rot, leaf_color(gl), burst=False)
        for p in self.particles:
            if p.get("wait", 0) > 0:
                p["wait"] -= dt
                continue
            kind = p["kind"]
            if kind == "leaf":
                if not p["landed"]:
                    p["vy"] = min(1.6, p["vy"] + 0.035 * dt / 16)
                    p["sway"] += 0.05 * dt / 16
                    p["x"] += (p["vx"] + math.sin(p["sway"]) * 0.5) * dt / 16
                    p["y"] += p["vy"] * dt / 16
                    p["rot"] += p["vr"] * dt / 16
                    floor = 437 if 116 < p["x"] < 484 else 451
                    if p["y"] >= floor:
                        p["y"], p["landed"] = floor, True
                else:
                    p["life"] -= dt / 1600
            elif kind == "drop":
                p["y"] += p["vy"] * dt / 16
                if p["y"] >= 395:
                    p["kind"], p["y"], p["life"] = "ripple", 396, 1.0
            elif kind == "ripple":
                p["life"] -= dt / 650
            elif kind == "bud":
                p["life"] -= dt / 1100
        self.particles = [p for p in self.particles if p["life"] > 0]
        if active or self.particles:
            self.draw()
        self.root.after(dt, self.tick)

    # --- drawing ---
    def tree(self):
        key = (round(self.g, 3), self.session.compactions, len(self.pile))
        if key != self.tree_key:
            self.tree_key = key
            self.tree_img = self.scene.render(self.g, self.session.compactions, self.pile)
        return self.tree_img

    def V(self, x, y):
        k = self.scene.k
        c = self.scene.crop
        return ((x - c[0]) * k, (y - c[1]) * k)

    def overlay(self, size):
        """Particles and shears, drawn on their own layer so fading pieces blend over the tree."""
        layer = Image.new("RGBA", size)
        d = ImageDraw.Draw(layer)
        k = self.scene.k
        water = (62, 143, 192) if is_light() else (124, 196, 232)
        for p in self.particles:
            if p.get("wait", 0) > 0:
                continue
            a = int(255 * clamp(p["life"], 0, 1))
            if p["kind"] == "leaf":
                ca, sa = math.cos(p["rot"]), math.sin(p["rot"])
                pts = []
                for i in range(8):
                    t = i / 8 * TAU
                    ex, ey = math.cos(t) * 4.4 * p["s"], math.sin(t) * 2.4 * p["s"]
                    pts.append(self.V(p["x"] + ex * ca - ey * sa, p["y"] + ex * sa + ey * ca))
                d.polygon(pts, fill=p["color"][:3] + (a,))
            elif p["kind"] == "drop":
                x, y = self.V(p["x"], p["y"])
                d.ellipse([x - 3 * k, y - 9 * k, x + 3 * k, y + 3 * k], fill=water + (235,))
            elif p["kind"] == "ripple":
                x, y = self.V(p["x"], p["y"])
                rx = (4 + 22 * (1 - p["life"])) * k
                d.ellipse([x - rx, y - rx * 0.3, x + rx, y + rx * 0.3], outline=water + (a,), width=max(1, round(2.2 * k)))
            elif p["kind"] == "bud":
                x, y = self.V(p["x"], p["y"])
                grow = 1 - p["life"]
                r = (3 + 8 * min(1, grow * 2.2)) * k
                col = leaf_color(0.0)[:3]
                glow = tuple(min(255, c + 60) for c in col)
                d.ellipse([x - r * 2, y - r * 2, x + r * 2, y + r * 2], fill=glow + (int(a * 0.22),))
                d.ellipse([x - r, y - r, x + r, y + r], fill=glow + (a,))
        if self.phase in ("armed", "compacting"):
            sh = self.shears
            now = time.time()
            if self.phase == "compacting":
                opening = 0.08 if now - sh["snap"] < 0.15 else 0.32 + 0.18 * math.sin(now * 9)
            else:
                opening = 0.22
            self.draw_shears(d, sh["x"], sh["y"], 2.5, opening)  # blades point down-left into the canopy
        return layer

    def draw_shears(self, d, x, y, angle, opening):
        k = self.scene.k * 2.1  # shears are drawn larger than the tree's scale so they read at widget size
        light = is_light()
        blade = (70, 78, 84) if light else (222, 228, 232)
        edge = (250, 250, 250) if light else (20, 24, 26)
        handle = rgb(C["pot"])
        px, py = self.V(x, y)
        for side in (-1, 1):
            b = angle + math.pi - side * opening * 0.7
            hx, hy = px + math.cos(b) * 11 * k, py + math.sin(b) * 11 * k
            d.line([(px, py), (hx, hy)], fill=handle, width=max(2, round(2.6 * k)))
            r = 4.8 * k
            d.ellipse([hx - r, hy - r, hx + r, hy + r], outline=handle, width=max(2, round(2.4 * k)))
        for side in (-1, 1):
            a = angle + side * opening
            tip = (px + math.cos(a) * 24 * k, py + math.sin(a) * 24 * k)
            nx, ny = -math.sin(a) * 2.8 * k, math.cos(a) * 2.8 * k
            d.polygon([(px + nx, py + ny), tip, (px - nx, py - ny)], fill=blade, outline=edge)
        d.ellipse([px - 2 * k, py - 2 * k, px + 2 * k, py + 2 * k], fill=handle, outline=edge)

    def draw(self):
        self.hits = []
        img = self.render_grove() if self.view == "grove" else self.render_focus()
        self.last_img = img
        self.frame_img = ImageTk.PhotoImage(img)
        self.label.configure(image=self.frame_img)
        if img.size != self.last_size:
            self.last_size = img.size
            self.place(*img.size)

    def place(self, w, h):
        """Keep the bottom-right corner fixed, so switching views grows the card up and to the left."""
        if self.anchor is None:
            c = self.cfg
            if c.get("right") is not None and c.get("bottom") is not None:
                self.anchor = (c["right"], c["bottom"])
            elif c.get("x") is not None and c.get("y") is not None:
                self.anchor = (c["x"] + w, c["y"] + h)  # older configs stored the top-left corner
            else:
                self.anchor = (self.root.winfo_screenwidth() - round(24 * self.f),
                               self.root.winfo_screenheight() - round(72 * self.f))
        self.root.geometry(f"+{int(self.anchor[0] - w)}+{int(self.anchor[1] - h)}")

    def render_grove(self):
        f, F, pad = self.f, self.fonts, self.pad
        now = time.time()
        paths = self.order
        n = max(1, len(paths))
        gap = 10 * f
        W = max(self.W, round(2 * pad + n * 104 * f + (n - 1) * gap))
        cell = (W - 2 * pad - (n - 1) * gap) / n
        if self.grove_scene is None or self.grove_scene.w != int(cell):
            self.grove_scene = Scene(int(cell), GROVE_CROP)
            self.grove_cache = {}
        scene = self.grove_scene
        info_h = 8 * f + 16 * f + 14 * f + 22 * f + 10 * f + 14 * f  # title, project, %, meter, status
        H = round(pad + 30 * f + scene.h + info_h + 22 * f + pad)
        img = Image.new("RGBA", (W, H), C["panel"])
        d = ImageDraw.Draw(img)
        d.rectangle([0, 0, W - 1, H - 1], outline=C["line"])
        d.text((pad, pad), "Grove", font=F["title"], fill=C["ink"])
        count = f"{len(paths)} active"
        d.text((W - pad - d.textlength(count, font=F["mono"]), pad + 4 * f), count, font=F["mono"], fill=C["muted"])
        y0 = pad + 30 * f
        for i, p in enumerate(paths):
            s = self.sessions[p]
            g = s.g
            x = pad + i * (cell + gap)
            rect = (x - 5 * f, y0 - 5 * f, x + cell + 5 * f, y0 + scene.h + info_h)
            self.hits.append((rect, "open", p))
            if self.hover_key == ("open", p):
                d.rounded_rectangle(rect, radius=8 * f, fill=C["line"])
            key = (round(g, 3), s.compactions)
            cached = self.grove_cache.get(p)
            if not cached or cached[0] != key:
                cached = self.grove_cache[p] = (key, scene.render(g, s.compactions, []))
            img.paste(cached[1], (round(x), round(y0)), cached[1])
            cx = x + cell / 2
            yy = y0 + scene.h + 8 * f
            name = ellipsize(d, s.title or s.name, F["small"], cell)
            d.text((cx - d.textlength(name, font=F["small"]) / 2, yy), name, font=F["small"], fill=C["ink"])
            yy += 16 * f
            if s.title and s.title != s.name:
                proj = ellipsize(d, s.name, F["mono"], cell)
                d.text((cx - d.textlength(proj, font=F["mono"]) / 2, yy), proj, font=F["mono"], fill=C["muted"])
            yy += 14 * f
            _, state, _ = stage_for(g)
            pct = f"{round(g * 100)}%"
            d.text((cx - d.textlength(pct, font=F["title"]) / 2, yy), pct, font=F["title"], fill=C["ink"])
            yy += 22 * f
            mh = 4 * f
            d.rounded_rectangle([x, yy, x + cell, yy + mh], radius=mh / 2, fill=C["line"] if self.hover_key != ("open", p) else C["panel"])
            d.rounded_rectangle([x, yy, x + max(mh, cell * clamp(g, 0, 1)), yy + mh], radius=mh / 2, fill=C[state])
            yy += 10 * f
            status = fmt_ago(now - s.mtime if s.mtime else 9e9)
            d.text((cx - d.textlength(status, font=F["mono"]) / 2, yy), status, font=F["mono"],
                   fill=C["ok"] if status == "live" else C["muted"])
        hint = "Click a tree to open it"
        d.text(((W - d.textlength(hint, font=F["small"])) / 2, H - pad - 14 * f), hint, font=F["small"], fill=C["muted"])
        return img

    def render_focus(self):
        s, f, F, pad = self.session, self.f, self.fonts, self.pad
        now = time.time()
        tree = self.tree().copy()
        tree.alpha_composite(self.overlay(tree.size))

        H = round(pad + 22 * f + 8 * f + tree.height + 12 * f + 40 * f + 14 * f + 34 * f + 56 * f + pad)
        img = Image.new("RGBA", (self.W, H), C["panel"])
        d = ImageDraw.Draw(img)
        d.rectangle([0, 0, self.W - 1, H - 1], outline=C["line"])
        y = pad
        proj = os.path.basename(os.path.normpath(s.cwd)) if s.cwd else "No session"
        ago = now - s.mtime if s.mtime else 9e9
        status = fmt_ago(ago)
        live = status == "live"
        sw = d.textlength(status, font=F["mono"])
        d.text((self.W - pad - sw, y + 4 * f), status, font=F["mono"], fill=C["ok"] if live else C["muted"])
        if live:
            r = 3 * f
            cx, cy = self.W - pad - sw - 8 * f, y + 10 * f
            d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=C["ok"])
        tx = pad
        if len(self.order) > 1:  # back to the grove
            back = f"‹ {len(self.order)}"
            bw_ = d.textlength(back, font=F["title"]) + 10 * f
            hovered = self.hover_key == ("grove", None)
            if hovered:
                d.rounded_rectangle([pad - 5 * f, y - 2 * f, pad + bw_ - 3 * f, y + 21 * f], radius=6 * f, fill=C["line"])
            d.text((pad, y), back, font=F["title"], fill=C["ink"] if hovered else C["muted"])
            self.hits.append(((pad - 5 * f, y - 2 * f, pad + bw_ - 3 * f, y + 21 * f), "grove", None))
            tx = pad + bw_ + 2 * f
        d.text((tx, y), ellipsize(d, proj, F["title"], self.W - tx - pad - sw - 20 * f), font=F["title"],
               fill=C["ink"])
        y += 22 * f + 8 * f
        img.paste(tree, (pad, round(y)), tree)
        y += tree.height + 12 * f

        g = self.g
        label, state, advice = stage_for(g)
        if self.phase in PHASE_TEXT:
            label, state = PHASE_TEXT[self.phase]
        col = C[state]
        pct = f"{round(g * 100)}"
        d.text((pad, y - 6 * f), pct, font=F["big"], fill=C["ink"])
        pw = d.textlength(pct, font=F["big"])
        d.text((pad + pw + 2 * f, y + 13 * f), "%  of context", font=F["body"], fill=C["muted"])
        if s.after_compact:
            tok = "compacted · waiting"
        elif s.tokens is not None:
            tok = f"{fmt_k(s.tokens)} / {fmt_k(self.cfg['window'])}"
        else:
            tok = ""
        tw = d.textlength(tok, font=F["mono"])
        d.text((self.W - pad - tw, y + 15 * f), tok, font=F["mono"], fill=C["muted"])
        y += 40 * f
        # meter: fill level, or a sliding shimmer while compacting
        mh = 6 * f
        x0, x1 = pad, self.W - pad
        d.rounded_rectangle([x0, y, x1, y + mh], radius=mh / 2, fill=C["line"])
        if self.phase == "compacting":
            span = (x1 - x0) * 0.3
            t = (now * 0.6) % 1
            a = x0 + (x1 - x0 + span) * t - span
            d.rounded_rectangle([max(x0, a), y, min(x1, a + span), y + mh], radius=mh / 2, fill=col)
        else:
            fw = max(mh, (x1 - x0) * clamp(g, 0, 1))
            d.rounded_rectangle([x0, y, x0 + fw, y + mh], radius=mh / 2, fill=col)
            tx = x0 + (x1 - x0) * 0.85
            d.rectangle([tx - f, y - 4 * f, tx + f, y + mh + 4 * f], fill=C["muted"])
        y += mh + 8 * f
        # stage chip + compact button
        cw = d.textlength(label.upper(), font=F["mono"])
        d.rounded_rectangle([pad, y, pad + cw + 22 * f, y + 18 * f], radius=9 * f, outline=col, width=max(1, round(f)))
        d.ellipse([pad + 7 * f, y + 6.5 * f, pad + 12 * f, y + 11.5 * f], fill=col)
        d.text((pad + 16 * f, y + 3 * f), label.upper(), font=F["mono"], fill=col)
        self.draw_button(d, y - 1 * f)
        y += 24 * f
        caption, ccol = advice, "muted"
        if self.phase == "armed":
            caption = ("Copied. In Claude: Ctrl+V, then Enter." if self.found_app
                       else "Copied /compact. Paste it into Claude.")
            ccol = "warn"
        elif self.phase == "compacting":
            el = int(now - self.phase_at)
            exp = s.last_duration
            caption = f"Compacting… {el}s" + (f" of ~{round(exp)}s" if exp else "")
            ccol = "ink"
        elif self.phase in ("pruned", "watering"):
            caption, ccol = "Pruned. Restoring state…", "ink"
        elif self.caption and now < self.caption[2]:
            caption, ccol = self.caption[0], self.caption[1]
        d.text((pad, y), ellipsize(d, caption, F["small"], self.W - 2 * pad), font=F["small"], fill=C[ccol])
        y += 26 * f
        # stats grid
        d.line([(pad, y), (self.W - pad, y)], fill=C["line"], width=max(1, round(f)))
        y += 8 * f
        branch, dirty = s.git
        jobs = len(s.jobs)
        stats = [
            ("BRANCH", branch or "–"), ("CHANGED", "–" if dirty is None else str(dirty)),
            ("JOBS", str(jobs) if jobs else "none"), ("COMPACTS", str(s.compactions)),
        ]
        colw = (self.W - 2 * pad) / 2
        for i, (k, v) in enumerate(stats):
            cx = pad + (i % 2) * colw
            cy = y + (i // 2) * 22 * f
            d.text((cx, cy + 2 * f), k, font=F["mono"], fill=C["muted"])
            kw = d.textlength(k, font=F["mono"]) + 6 * f
            vcol = C["warn"] if (k == "JOBS" and jobs) else C["ink"]
            d.text((cx + kw, cy - 1 * f), ellipsize(d, v, F["body"], colw - kw - 6 * f), font=F["body"], fill=vcol)
        return img

    def draw_button(self, d, y):
        f, F = self.f, self.fonts
        busy = self.phase in ("compacting", "pruned", "watering")
        text = "Cancel" if self.phase == "armed" else "Compact"
        tw = d.textlength(text, font=F["button"])
        w, h = tw + 34 * f, 20 * f
        x1 = self.W - self.pad
        x0 = x1 - w
        if not busy:
            self.hits.append(((x0, y, x1, y + h), "compact", None))
        fg = C["muted"] if busy else C["ink"]
        fill = C["line"] if (self.hover_key == ("compact", None) and not busy) else None
        d.rounded_rectangle([x0, y, x1, y + h], radius=h / 2, fill=fill, outline=C["line"] if busy else C["muted"],
                            width=max(1, round(f)))
        d.text((x0 + 10 * f, y + 1.5 * f), "✂", font=F["symbol"], fill=C["crit"] if not busy else fg)
        d.text((x0 + 26 * f, y + 2.5 * f), text, font=F["button"], fill=fg)

    # --- interaction ---
    def hit_at(self, x, y):
        for (x0, y0, x1, y1), action, arg in self.hits:
            if x0 <= x <= x1 and y0 <= y <= y1:
                return (action, arg)
        return None

    def press(self, e):
        self._action = self.hit_at(e.x, e.y)
        self._start = (e.x_root, e.y_root)
        self._dx, self._dy = e.x_root - self.root.winfo_x(), e.y_root - self.root.winfo_y()

    def drag_move(self, e):
        if self._action and abs(e.x_root - self._start[0]) + abs(e.y_root - self._start[1]) > 6:
            self._action = None  # pressed on a tree or button, then dragged: move the window instead
        if not self._action:
            self.root.geometry(f"+{e.x_root - self._dx}+{e.y_root - self._dy}")

    def release(self, e):
        action, self._action = self._action, None
        if action:
            if self.hit_at(e.x, e.y) == action:
                self.do(*action)
            return
        w, h = self.last_size
        self.anchor = (self.root.winfo_x() + w, self.root.winfo_y() + h)
        self.cfg["right"], self.cfg["bottom"] = self.anchor
        self.cfg.pop("x", None)
        self.cfg.pop("y", None)
        save_config(self.cfg)

    def do(self, action, arg):
        if action == "compact":
            self.on_button()
        elif action == "open":
            self.follow = False  # stay on the tree you opened
            self.set_focus(arg)
            self.view = "focus"
        elif action == "grove":
            self.view = "grove"
            self.follow = True
        self.hover_key = None
        self.draw()

    def motion(self, e):
        self.set_hover(self.hit_at(e.x, e.y))

    def set_hover(self, key):
        if key != self.hover_key:
            self.hover_key = key
            self.label.configure(cursor="hand2" if key else "fleur")
            self.draw()

    def menu(self, e):
        m = tk.Menu(self.root, tearoff=0)
        m.add_checkbutton(label="Keep on top", variable=self.topvar, command=self.toggle_top)
        m.add_checkbutton(label="Pin this session", variable=self.pinvar, command=self.toggle_pin)
        themes = tk.Menu(m, tearoff=0)
        for name in THEMES:
            themes.add_radiobutton(label=name, value=name, variable=self.themevar, command=self.change_theme)
        m.add_cascade(label="Theme", menu=themes)
        if len(self.order) > 1 and self.view == "focus":
            m.add_command(label="Show grove", command=lambda: self.do("grove", None))
        m.add_separator()
        m.add_command(label="Preview compact animation", command=self.run_preview)
        m.add_command(label="Quit", command=self.root.destroy)
        m.tk_popup(e.x_root, e.y_root)

    def toggle_top(self):
        self.cfg["topmost"] = self.topvar.get()
        self.root.attributes("-topmost", self.cfg["topmost"])
        save_config(self.cfg)

    def change_theme(self):
        self.cfg["theme"] = self.themevar.get()
        set_theme(self.cfg["theme"])
        self.scene = Scene(self.W - 2 * self.pad)  # background is cached per theme
        self.grove_scene, self.grove_cache = None, {}
        self.tree_key = None
        self.root.configure(bg=C["panel"])
        self.label.configure(bg=C["panel"])
        save_config(self.cfg)
        self.draw()

    def toggle_pin(self):
        self.cfg["pinned"] = self.session.path if self.pinvar.get() else None
        save_config(self.cfg)


def focus_claude():
    """Bring the Claude desktop app to the front. Returns False if it isn't running."""
    from ctypes import wintypes
    user32, k32 = ctypes.windll.user32, ctypes.windll.kernel32
    user32.FindWindowW.restype = wintypes.HWND
    user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
    hwnd = user32.FindWindowW(None, "Claude")
    if not hwnd:
        return False
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    k32.OpenProcess.restype = wintypes.HANDLE
    h = k32.OpenProcess(0x1000, False, pid.value)  # PROCESS_QUERY_LIMITED_INFORMATION
    exe = ""
    if h:
        buf, size = ctypes.create_unicode_buffer(520), wintypes.DWORD(520)
        if k32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
            exe = buf.value
        k32.CloseHandle(h)
    if not exe.lower().endswith("claude.exe"):
        return False
    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, 9)  # SW_RESTORE
    user32.SetForegroundWindow(hwnd)
    return True


def ellipsize(d, text, fnt, maxw):
    if d.textlength(text, font=fnt) <= maxw:
        return text
    while text and d.textlength(text + "…", font=fnt) > maxw:
        text = text[:-1]
    return text + "…"


def font(name, size, fallback=None):
    for n in (name, fallback):
        if n:
            try:
                return ImageFont.truetype(FONTS + n, round(size))
            except OSError:
                pass
    return ImageFont.load_default()


def round_corners(root):
    """Windows 11 rounded corners for the borderless window."""
    try:
        hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
        pref = ctypes.c_int(2)  # DWMWCP_ROUND
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 33, ctypes.byref(pref), ctypes.sizeof(pref))
    except Exception:
        pass


def load_config():
    cfg = dict(DEFAULTS)
    try:
        with open(CONFIG, encoding="utf-8") as fh:
            cfg.update(json.load(fh))
    except (OSError, ValueError):
        pass
    return cfg


def save_config(cfg):
    try:
        with open(CONFIG, "w", encoding="utf-8") as fh:
            json.dump(cfg, fh, indent=2)
    except OSError:
        pass


def main():
    k32 = ctypes.windll.kernel32
    k32.CreateMutexW(None, False, "ContextBonsaiWidget")
    if k32.GetLastError() == 183:  # already running: launching again toggles it off
        hwnd = ctypes.windll.user32.FindWindowW(None, TITLE)
        if hwnd:
            ctypes.windll.user32.PostMessageW(hwnd, 0x0010, 0, 0)  # WM_CLOSE
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        pass
    Widget().root.mainloop()


if __name__ == "__main__":
    main()
