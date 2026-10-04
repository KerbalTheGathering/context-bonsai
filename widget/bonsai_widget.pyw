#!/usr/bin/env pythonw
"""Context Bonsai: a desktop widget that grows with the active Claude Code session's context.

Reads the newest transcript in ~/.claude/projects (no model calls, no usage).
Drag to move. Right-click for options. Launching it again while it runs closes it.
"""
import collections
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
import zlib
from datetime import datetime

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageTk

HOME = os.path.expanduser("~")
PROJECTS = os.path.join(HOME, ".claude", "projects")
SESSIONS = os.path.join(HOME, ".claude", "sessions")  # Claude Code writes <pid>.json here for each open session
HERE = os.path.dirname(os.path.abspath(__file__))
# settings and the compaction signal live in ~/.claude/widget, shared with the desktop app and the plugin
DATA = os.environ.get("BONSAI_DATA_DIR") or os.path.join(HOME, ".claude", "widget")
CONFIG = os.path.join(DATA, "bonsai.json")
SIGNAL = os.path.join(DATA, "signal.json")  # written by the plugin's PreCompact hook (precompact_signal.py)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "plugin", "hooks"))  # the rehydrate hook, for running_jobs
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
FOCUS_CROP = (30, -95, 570, 462)  # the card's scene: extra wall above the canopy for the % readout
GROVE_MINUTES = 30  # sessions active within this window get a tree
GROVE_MAX = 12
GROVE_PAGE = 4  # trees in view at once; the rest are a scroll of the carousel away
GROVE_SLIDE = 0.35  # seconds for the carousel to slide
LIVE_SECONDS = 15  # how often to re-read the open-session registry
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
    "Canyon": {
        "colors": {
            "panel": "#2A1D18", "wall": "#2E1F19", "wall2": "#3B2820", "ink": "#F1E4D8", "muted": "#B39A88",
            "line": "#4A3429", "pot": "#B5603A", "potDark": "#8A4528", "potHi": "#D88A63", "wood": "#6E4E3A",
            "woodDark": "#4E3628", "soil": "#2B1C15", "moss": "#6F7A4A", "bark": "#8A6A55", "barkHi": "#A88468",
            "ok": "#A3B86C", "warn": "#E2A04A", "crit": "#E06A4A"},
        "stops": [(0, 100, 30, 46), (0.5, 92, 22, 52), (0.7, 70, 22, 56), (0.8, 38, 52, 52),
                  (0.9, 22, 64, 48), (1.0, 10, 68, 44)]},
    "Clay": {
        "colors": {
            "panel": "#F5EFE6", "wall": "#F2EADF", "wall2": "#E7DCCB", "ink": "#2B2420", "muted": "#7A6D62",
            "line": "#DCCFBD", "pot": "#C96442", "potDark": "#9E4A30", "potHi": "#E08A6C", "wood": "#8B6B4E",
            "woodDark": "#6B5038", "soil": "#3B2E25", "moss": "#7E8A55", "bark": "#5C4636", "barkHi": "#7D6250",
            "ok": "#5E7D3A", "warn": "#B7791F", "crit": "#B5452E"},
        "stops": [(0, 82, 34, 42), (0.5, 88, 30, 35), (0.7, 96, 26, 30), (0.8, 40, 58, 44),
                  (0.9, 22, 66, 44), (1.0, 12, 68, 40)]},
    "Neon": {
        "colors": {
            "panel": "#140E24", "wall": "#120B22", "wall2": "#1E1336", "ink": "#F2E9FF", "muted": "#A08BC8",
            "line": "#2E2350", "pot": "#2B1F55", "potDark": "#1C143A", "potHi": "#7B5CFF", "wood": "#2A2245",
            "woodDark": "#1B1630", "soil": "#120D1F", "moss": "#3B2A6B", "bark": "#6B5B9A", "barkHi": "#8F7FD0",
            "ok": "#4DF0FF", "warn": "#FFD84D", "crit": "#FF4D8D"},
        "stops": [(0, 186, 95, 60), (0.5, 205, 90, 62), (0.7, 268, 88, 68), (0.8, 305, 90, 64),
                  (0.9, 332, 95, 62), (1.0, 350, 95, 60)]},
    "Pixel": {  # Moss colors, drawn at low resolution and scaled up without smoothing
        "pixel": True,
        "colors": {
            "panel": "#1A201F", "wall": "#151A19", "wall2": "#1D2422", "ink": "#E3E7E0", "muted": "#9AA39B",
            "line": "#2F3835", "pot": "#4E8990", "potDark": "#33616A", "potHi": "#78AEB4", "wood": "#7A5A40",
            "woodDark": "#59402D", "soil": "#2A221C", "moss": "#5E7A40", "bark": "#7A6552", "barkHi": "#9C8469",
            "ok": "#8DBA6E", "warn": "#E0A94A", "crit": "#E7795A"},
        "stops": [(0, 104, 52, 52), (0.5, 120, 48, 42), (0.7, 130, 44, 36), (0.8, 52, 74, 52),
                  (0.9, 26, 78, 50), (1.0, 8, 70, 46)]},
}
# Virtual themes resolve to a real palette each time they're applied.
SEASONS = {12: "Midnight", 1: "Midnight", 2: "Midnight", 3: "Sakura", 4: "Sakura", 5: "Sakura",
           6: "Moss", 7: "Moss", 8: "Moss", 9: "Canyon", 10: "Canyon", 11: "Canyon"}
THEME_NAMES = ["Auto", "Seasons"] + list(THEMES)
C = {}
STOPS = []
THEME_KEY = None  # identity of the applied palette, for caching scene backgrounds
PIXEL = False


def windows_theme():
    """(light mode?, accent '#rrggbb') from the Windows personalization settings."""
    light, accent = False, "#0078D4"
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as k:
            light = winreg.QueryValueEx(k, "AppsUseLightTheme")[0] == 1
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\DWM") as k:
            abgr = winreg.QueryValueEx(k, "AccentColor")[0]
            accent = "#{:02X}{:02X}{:02X}".format(abgr & 0xFF, (abgr >> 8) & 0xFF, (abgr >> 16) & 0xFF)
    except OSError:
        pass
    return light, accent


def shade(hexstr, factor):
    """Lighten (factor > 1) or darken (factor < 1) a color."""
    h = hexstr.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    if factor >= 1:
        r, g, b = (round(c + (255 - c) * (factor - 1)) for c in (r, g, b))
    else:
        r, g, b = (round(c * factor) for c in (r, g, b))
    return "#{:02X}{:02X}{:02X}".format(*(min(255, max(0, c)) for c in (r, g, b)))


def fluent_theme(light, accent):
    """Windows 11 neutrals with the system accent on the pot."""
    if light:
        colors = {"panel": "#F3F3F3", "wall": "#FAFAFA", "wall2": "#EAEAEA", "ink": "#1B1B1B", "muted": "#5F5F5F",
                  "line": "#D5D5D5", "ok": "#0F7B0F", "warn": "#9D5D00", "crit": "#C42B1C"}
        stops = THEMES["Paper"]["stops"]
    else:
        colors = {"panel": "#202020", "wall": "#1C1C1C", "wall2": "#2B2B2B", "ink": "#FFFFFF", "muted": "#A0A0A0",
                  "line": "#3A3A3A", "ok": "#6CCB5F", "warn": "#FCE100", "crit": "#FF99A4"}
        stops = THEMES["Moss"]["stops"]
    base = THEMES["Paper" if light else "Moss"]["colors"]
    colors.update({k: base[k] for k in ("wood", "woodDark", "soil", "moss", "bark", "barkHi")})
    colors.update({"pot": accent, "potDark": shade(accent, 0.7), "potHi": shade(accent, 1.35)})
    return {"colors": colors, "stops": stops}


def set_theme(name):
    global STOPS, THEME_KEY, PIXEL
    if name == "Auto":
        light, accent = windows_theme()
        key, theme = f"Auto-{'light' if light else 'dark'}-{accent}", fluent_theme(light, accent)
    else:
        if name == "Seasons":
            name = SEASONS[time.localtime().tm_mon]
        key, theme = name, THEMES.get(name) or THEMES["Moss"]
    if key == THEME_KEY:
        return
    THEME_KEY, PIXEL = key, bool(theme.get("pixel"))
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
def build_tree(seed=11, vary=False):
    """The mockup's tree for seed 11. With vary=True the seed also picks the tree's overall style
    (lean, trunk zigzag, height, branch length and spread, mirroring) so sessions look distinct."""
    r = mulberry(seed)
    segs, pads, shoots = [], [], []
    S = 1.45
    zig, lean, trunk_n, branch_mul, spread_mul, mirror = 0.34, 0.0, 6, 1.0, 1.0, False
    if vary:
        v = mulberry(seed ^ 0x5BD1E995)
        zig = 0.16 + v() * 0.32
        lean = (v() - 0.5) * 0.44
        trunk_n = 5 + int(v() * 3)
        branch_mul = 0.8 + v() * 0.28
        spread_mul = 0.8 + v() * 0.5
        mirror = v() < 0.5
        S = 1.32 + v() * 0.18

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
            spread = (-1 if k == 0 else 1) * (0.34 + r() * 0.3) * spread_mul
            na = a + spread
            if math.sin(na) > 0.2:
                na = a + spread * 0.25
            branch(ex, ey, na, ln * (0.62 + r() * 0.12), w * 0.68, depth + 1, end + 0.005 + r() * 0.025)
        pads.append(make_pad(ex, ey, end + (0.005 if depth == 0 else 0.04), 0.7 if depth == 0 else 0.85))

    x, y, w, side = 300, 398, 30, 1
    seg_scale = 6 / trunk_n  # taller trunks get shorter segments so the tree stays in frame
    for i in range(trunk_n):
        ln = (46 - i * 4 * seg_scale) * S * seg_scale
        a = -math.pi / 2 + (1 if i % 2 else -1) * zig + lean * (i + 1) / trunk_n + (r() - 0.5) * 0.08
        nx, ny = x + math.cos(a) * ln, y + math.sin(a) * ln
        birth = i * 0.03
        segs.append({"x1": x, "y1": y, "x2": nx, "y2": ny, "w1": w, "w2": w * 0.83, "birth": birth,
                     "dur": 0.04, "trunk": True})
        if i >= 1:
            side = -side
            ba = -0.16 - r() * 0.22 if side > 0 else math.pi + 0.16 + r() * 0.22
            branch(nx, ny, ba, (66 - i * 7 * seg_scale + r() * 12) * S * branch_mul, w * 0.42, 0, birth + 0.02)
        x, y, w = nx, ny, w * 0.83
    branch(x, y, -math.pi / 2 + lean + (r() - 0.5) * 0.4, 26 * S, w * 0.85, 1, trunk_n * 0.03 + 0.02)

    for p in pads:
        if r() < 0.5:
            a = -math.pi / 2 + (r() - 0.5) * 2.0
            ln = (28 + r() * 36) * S
            leaves = [{"t": 0.35 + r() * 0.65, "s": 0.5 + r() * 0.4, "turn": r() * 0.12,
                       "side": -1 if r() < 0.5 else 1, "rot": r() * TAU} for _ in range(5)]
            shoots.append({"x": p["x"], "y": p["y"], "a": a, "len": ln, "bend": (r() - 0.5) * 0.6,
                           "birth": 0.64 + r() * 0.26, "leaves": leaves})
    if mirror:  # flip around the pot's center line
        for s in segs:
            s["x1"], s["x2"] = 600 - s["x1"], 600 - s["x2"]
        for p in pads:
            p["x"] = 600 - p["x"]
            for l in p["leaves"]:
                l["dx"] = -l["dx"]
        for sh in shoots:
            sh["x"], sh["a"], sh["bend"] = 600 - sh["x"], math.pi - sh["a"], -sh["bend"]
            for l in sh["leaves"]:
                l["side"] = -l["side"]
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


def leaf_color(g, alpha=255, dl=0):
    """Leaf color for a context fill level; dl shifts lightness (light from the top left)."""
    g = clamp(g, 0, 1)
    i = 0
    while i < len(STOPS) - 2 and g > STOPS[i + 1][0]:
        i += 1
    a, b = STOPS[i], STOPS[i + 1]
    t = clamp((g - a[0]) / (b[0] - a[0]), 0, 1)
    dh = (b[1] - a[1] + 540) % 360 - 180  # blend hue the short way round the color wheel
    h, s, l = (a[1] + dh * t) % 360, lerp(a[2], b[2], t), clamp(lerp(a[3], b[3], t) + dl, 4, 96)
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


def each_leaf(g, tree=None):
    """Yield (x, y, size, rot, color_g, birth) for every visible leaf at growth g."""
    tree = tree or TREE
    lush = lushness(g)
    for p in tree["pads"]:
        f = clamp((g - p["birth"]) / 0.12, 0, 1)
        if f <= 0:
            continue
        R = p["size"] * lush * (0.45 + 0.55 * f)
        for l in p["leaves"]:
            if l["order"] <= f:
                yield p["x"] + l["dx"] * R, p["y"] + l["dy"] * R, l["s"], l["rot"], g + l["turn"], p["birth"]
    for sh in tree["shoots"]:
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
        self.pixel = PIXEL
        self.ss = 0.34 if PIXEL else SS  # pixel style draws small, then scales up without smoothing
        self.bg = self._background()

    def P(self, x, y):
        return ((x - self.crop[0]) * self.k * self.ss, (y - self.crop[1]) * self.k * self.ss)

    def L(self, v):
        return v * self.k * self.ss

    def _background(self):
        W, H = max(1, round(self.w * self.ss)), max(1, round(self.h * self.ss))
        img = Image.new("RGBA", (W, H))
        d = ImageDraw.Draw(img)
        a, b = rgb(C["wall"]), rgb(C["wall2"])
        shelf = self.P(0, 452)[1]
        for yy in range(H):
            t = yy / H
            d.line([(0, yy), (W, yy)], fill=tuple(int(lerp(a[i], b[i], t)) for i in range(3)))
        d.rectangle([0, shelf, W, H], fill=C["wall2"])
        d.rectangle([0, shelf, W, shelf + self.L(1.5)], fill=C["line"])
        # stand: plank with a lit top edge, legs
        self.rect(d, 140, 446, 14, 10, C["woodDark"])
        self.rect(d, 446, 446, 14, 10, C["woodDark"])
        self.rect(d, 116, 438, 368, 10, C["wood"])
        self.rect(d, 116, 438, 368, 1.6, shade(C["wood"], 1.3))
        self.rect(d, 116, 446, 368, 2, C["woodDark"])
        # the pot's soft shadow on the stand
        sh = Image.new("RGBA", img.size)
        self.ellipse(ImageDraw.Draw(sh), 306, 438.5, 142, 5, (0, 0, 0, 110 if is_light() else 150))
        img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(max(0.5, self.L(3.5)))))
        d = ImageDraw.Draw(img)
        # pot: feet, then a body lit from the left and shadowed on the right, rim with a highlight
        self.rect(d, 192, 430, 22, 8, C["potDark"])
        self.rect(d, 386, 430, 22, 8, C["potDark"])
        hi, mid, lo = rgb(C["potHi"]), rgb(C["pot"]), rgb(C["potDark"])
        xa, xb = self.P(172, 0)[0], self.P(428, 0)[0]
        top, bot = self.P(0, 402)[1], self.P(0, 432)[1]
        for px in range(int(xa), int(xb) + 1):
            vx = self.crop[0] + px / (self.k * self.ss)
            t = clamp((vx - 172) / 256, 0, 1)
            col = (tuple(round(lerp(h, m, t / 0.3)) for h, m in zip(hi, mid)) if t < 0.3 else
                   tuple(round(lerp(m, l, (t - 0.3) / 0.7)) for m, l in zip(mid, lo)))
            # the sides slope in: 172 -> 188 at the bottom-left, 428 -> 412 at the bottom-right
            edge = min(1.0, (vx - 172) / 16, (428 - vx) / 16)
            yb = top + (bot - top) * clamp(edge if edge < 1 else 1, 0, 1) if edge < 1 else bot
            d.line([(px, top), (px, yb)], fill=col)
        self.rect(d, 180, 409, 240, 1.6, shade(C["pot"], 1.18))  # a thrown ring around the body
        self.rect(d, 166, 395, 268, 9, C["potDark"])  # rim
        self.rect(d, 168, 395.6, 264, 1.5, shade(C["potHi"], 1.15))
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

    def taper(self, d, x1, y1, x2, y2, w1, w2, fill):
        """A branch that narrows from w1 to w2, with a rounded joint at its base."""
        dx, dy = x2 - x1, y2 - y1
        n = math.hypot(dx, dy) or 1e-6
        nx, ny = -dy / n, dx / n
        d.polygon([self.P(x1 + nx * w1 / 2, y1 + ny * w1 / 2), self.P(x2 + nx * w2 / 2, y2 + ny * w2 / 2),
                   self.P(x2 - nx * w2 / 2, y2 - ny * w2 / 2), self.P(x1 - nx * w1 / 2, y1 - ny * w1 / 2)], fill=fill)
        for (x, y), w in (((x1, y1), w1), ((x2, y2), w2)):
            cx, cy = self.P(x, y)
            r = max(0.5, self.L(w / 2))
            d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=fill)

    def trunk(self, d, tree, g, thick):
        """A smooth, tapered trunk with a root flare, shaded from a light at the top left."""
        segs = [s for s in tree["segs"] if s.get("trunk")]
        pts, ws = [], []
        for i, s in enumerate(segs):
            p = clamp((g - s["birth"]) / s["dur"], 0, 1)
            if p <= 0 and i > 0:
                break
            pp = max(p, 0.35) if i == 0 else p
            if not pts:
                pts.append((s["x1"], s["y1"]))
                ws.append(s["w1"])
            pts.append((lerp(s["x1"], s["x2"], pp), lerp(s["y1"], s["y2"], pp)))
            ws.append(lerp(s["w1"], s["w2"], pp))
            if p < 1:
                break
        wmul = thick * (0.55 + 0.45 * clamp(g / 0.5, 0, 1))

        def cr(a, b, c, e, t):  # Catmull-Rom through the joints, so the trunk curves instead of kinking
            return 0.5 * (2 * b + (c - a) * t + (2 * a - 5 * b + 4 * c - e) * t * t + (3 * b - a - 3 * c + e) * t ** 3)

        line = []
        for i in range(len(pts) - 1):
            p0, p1, p2, p3 = pts[max(0, i - 1)], pts[i], pts[i + 1], pts[min(len(pts) - 1, i + 2)]
            for k in range(8):
                t = k / 8
                line.append((cr(p0[0], p1[0], p2[0], p3[0], t), cr(p0[1], p1[1], p2[1], p3[1], t),
                             lerp(ws[i], ws[i + 1], t)))
        line.append((pts[-1][0], pts[-1][1], ws[-1]))
        out = []
        for j, (x, y, w) in enumerate(line):
            u = j / max(1, len(line) - 1)
            flare = 1 + 1.15 * max(0.0, 1 - u / 0.14) ** 2  # roots spreading into the soil
            out.append((x, y, max(1.2, w * wmul * flare)))
        right, left, nrm = [], [], []
        for j, (x, y, w) in enumerate(out):
            a, b = out[max(0, j - 1)], out[min(len(out) - 1, j + 1)]
            tx, ty = b[0] - a[0], b[1] - a[1]
            n = math.hypot(tx, ty) or 1e-6
            nx, ny = -ty / n, tx / n  # points to screen-right while the trunk climbs
            nrm.append((nx, ny))
            right.append((x + nx * w / 2, y + ny * w / 2))
            left.append((x - nx * w / 2, y - ny * w / 2))
        P = self.P
        d.polygon([P(*q) for q in right + left[::-1]], fill=C["bark"])
        shaded = [(x + nx * w * 0.06, y + ny * w * 0.06) for (x, y, w), (nx, ny) in zip(out, nrm)]
        d.polygon([P(*q) for q in shaded + right[::-1]], fill=shade(C["bark"], 0.8))
        lit_a = [(x - nx * w * 0.36, y - ny * w * 0.36) for (x, y, w), (nx, ny) in zip(out, nrm)]
        lit_b = [(x - nx * w * 0.16, y - ny * w * 0.16) for (x, y, w), (nx, ny) in zip(out, nrm)]
        d.polygon([P(*q) for q in lit_a + lit_b[::-1]], fill=C["barkHi"])
        fissure = shade(C["bark"], 0.68)  # bark texture: broken lines running along the trunk
        for off, start in ((0.1, 2), (0.3, 5), (-0.05, 9)):
            for j in range(start, len(out) - 3, 9):
                run = [P(x + nx * w * off, y + ny * w * off) for (x, y, w), (nx, ny) in zip(out[j:j + 4], nrm[j:j + 4])]
                d.line(run, fill=fissure, width=max(1, round(self.L(0.9))))
        x, y, w = out[-1]
        cx, cy = P(x, y)
        r = self.L(w / 2)
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=C["bark"])

    def render(self, g, cc, pile, tree=None, sway=None):
        tree = tree or TREE
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

        def drift(x, y):  # breeze: leaves higher up sway further, neighbors slightly out of step
            if sway is None:
                return 0.0
            return 2.4 * math.sin(sway + x * 0.025 + y * 0.02) * clamp((398 - y) / 260, 0, 1.2)

        layer = Image.new("RGBA", img.size)  # the tree on its own layer, so it can cast a shadow
        ld = ImageDraw.Draw(layer)
        thick = 1 + 0.08 * min(cc, 6)
        bwmul = 0.6 + 0.4 * clamp(g / 0.6, 0, 1)
        for s in tree["segs"]:
            if s.get("trunk"):
                continue
            p = clamp((g - s["birth"]) / s["dur"], 0, 1)
            if p <= 0:
                continue
            x2, y2 = lerp(s["x1"], s["x2"], p), lerp(s["y1"], s["y2"], p)
            w1 = max(1.2, s["w1"] * bwmul)
            w2 = max(0.9, lerp(s["w1"], s["w2"], p) * bwmul)
            self.taper(ld, s["x1"], s["y1"], x2, y2, w1, w2, C["bark"])
        for sh in tree["shoots"]:
            f = clamp((g - sh["birth"]) / 0.08, 0, 1)
            if f <= 0:
                continue
            pts = [self.P(sh["x"], sh["y"])] + [self.P(*shoot_point(sh, i / 12 * f)) for i in range(1, 13)]
            ld.line(pts, fill=C["bark"], width=max(1, round(self.L(1.5))), joint="curve")
        self.trunk(ld, tree, g, thick)
        # foliage: a darker dome under each pad, then leaves lit from the top left
        lush = lushness(g)
        for p in tree["pads"]:
            f = clamp((g - p["birth"]) / 0.12, 0, 1)
            if f <= 0:
                continue
            R = p["size"] * lush * (0.45 + 0.55 * f)
            self.ellipse(ld, p["x"] + drift(p["x"], p["y"]), p["y"] + R * 0.02, R * 0.86, R * 0.4,
                         leaf_color(g, 255, -15))
        for p in tree["pads"]:
            f = clamp((g - p["birth"]) / 0.12, 0, 1)
            if f <= 0:
                continue
            R = p["size"] * lush * (0.45 + 0.55 * f)
            for l in sorted(p["leaves"], key=lambda l: l["dy"], reverse=True):  # back/bottom leaves first
                if l["order"] > f:
                    continue
                x, y = p["x"] + l["dx"] * R, p["y"] + l["dy"] * R
                lift = (-l["dy"] * 14 - l["dx"] * 3 + (l["turn"] - 0.06) * 40) * (1 if is_light() else 0.75)
                dx = drift(x, y)
                self.leaf(ld, x + dx, y, l["s"], l["rot"] + dx * 0.06, leaf_color(g + l["turn"], 255, lift))
        for sh in tree["shoots"]:
            f = clamp((g - sh["birth"]) / 0.08, 0, 1)
            if f <= 0:
                continue
            perp = sh["a"] + math.pi / 2
            for l in sh["leaves"]:
                if l["t"] <= f:
                    px, py = shoot_point(sh, l["t"])
                    x, y = px + math.cos(perp) * 4 * l["side"], py + math.sin(perp) * 4 * l["side"]
                    self.leaf(ld, x + drift(x, y), y, l["s"], l["rot"], leaf_color(g + l["turn"], 255, 3))
        # a soft shadow on the wall behind, falling down and to the right
        alpha = layer.getchannel("A").filter(ImageFilter.GaussianBlur(max(0.6, self.L(6))))
        strength = 0.2 if is_light() else 0.38
        cast = Image.new("RGBA", img.size, (12, 16, 14, 0) if is_light() else (0, 0, 0, 0))
        cast.putalpha(alpha.point(lambda v: int(v * strength)))
        moved = Image.new("RGBA", img.size)
        moved.paste(cast, (round(self.L(10)), round(self.L(7))))
        img.alpha_composite(moved)
        img.alpha_composite(layer)
        return img.resize((self.w, self.h), Image.NEAREST if self.pixel else Image.LANCZOS)


# ---------- session data ----------
def parse_ts(ts):
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
    except (AttributeError, ValueError):
        return None


class Stats:
    """Running totals for one session, fed one transcript entry at a time."""
    EDIT_TOOLS = ("Edit", "Write", "MultiEdit", "NotebookEdit")

    def __init__(self):
        self.usage = {}  # message id -> usage (a message's content blocks share one id and usage)
        self.tool_ids = set()
        self.tools = collections.Counter()
        self.errors = 0
        self.files = set()
        self.prompts = 0
        self.last_prompt = None
        self.subagents = 0
        self.started = None
        self._totals = None

    def add(self, d):
        ts = parse_ts(d.get("timestamp"))
        if ts and self.started is None:
            self.started = ts
        m = d.get("message") or {}
        content = m.get("content")
        if d.get("type") == "assistant":
            if m.get("id") and m.get("usage"):
                self.usage[m["id"]] = m["usage"]
                self._totals = None
            for c in content if isinstance(content, list) else []:
                if not isinstance(c, dict) or c.get("type") != "tool_use" or c.get("id") in self.tool_ids:
                    continue
                self.tool_ids.add(c.get("id"))
                name = c.get("name") or "?"
                self.tools[name] += 1
                if name in ("Agent", "Task"):
                    self.subagents += 1
                inp = c.get("input") or {}
                fp = inp.get("file_path") or inp.get("notebook_path")
                if fp and name in self.EDIT_TOOLS:
                    self.files.add(os.path.normcase(fp))
        elif d.get("type") == "user" and not d.get("isMeta") and not d.get("isCompactSummary"):
            if isinstance(content, str):
                texts = [content]
            else:
                blocks = [c for c in content or [] if isinstance(c, dict)]
                self.errors += sum(1 for c in blocks if c.get("type") == "tool_result" and c.get("is_error"))
                if any(c.get("type") == "tool_result" for c in blocks):
                    return
                texts = [c.get("text") or "" for c in blocks if c.get("type") == "text"]
            # a real prompt has some text that isn't a command echo, caveat or system note
            if any(t.strip() and not t.lstrip().startswith("<") for t in texts):
                self.prompts += 1
                self.last_prompt = ts or self.last_prompt

    @property
    def totals(self):
        if self._totals is None:
            inp = cread = cwrite = out = think = peak = 0
            series = []  # context size of each API call, in order
            for u in self.usage.values():
                i, r, w = (u.get("input_tokens", 0), u.get("cache_read_input_tokens", 0),
                           u.get("cache_creation_input_tokens", 0))
                inp, cread, cwrite = inp + i, cread + r, cwrite + w
                out += u.get("output_tokens", 0)
                think += (u.get("output_tokens_details") or {}).get("thinking_tokens", 0)
                peak = max(peak, i + r + w)
                series.append(i + r + w)
            total = inp + cread + cwrite
            self._totals = {"cache": cread / total if total else None, "out": out, "think": think,
                            "peak": peak, "calls": len(self.usage), "series": series,
                            "avg": total / len(series) if series else 0, "total": total + out}
        return self._totals


class Session:
    def __init__(self, cfg, path=None):
        self.cfg = cfg
        self.fixed = path  # follow this transcript only; None = pinned or newest
        self.path = None
        self.offset = 0
        self.seen_cc = None  # compaction / restore counts the window has already reacted to
        self.seen_restores = None
        self.title = None
        self.stats = Stats()
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

    @property
    def tree(self):
        """Each session grows its own tree shape, seeded from its transcript name."""
        key = os.path.basename(self.path or "")
        if getattr(self, "_tree_key", None) != key:
            self._tree_key = key
            self._tree = build_tree(zlib.crc32(key.encode()), vary=True) if key else TREE
        return self._tree

    def refresh(self, git=True):
        """Returns True when the data changed. git=False skips the branch/changes check (grove-only trees)."""
        path = self.pick()
        if not path:
            return False
        switched = path != self.path
        if switched:
            self.path, self.offset, self.compactions, self.last_pre = path, 0, 0, None
            self.last_duration, self.restores, self.restored_msg, self.title = None, 0, None, None
            self.stats = Stats()
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
        if git and self.cwd and time.time() - self.git_at > 10:
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
            if b'"type":"assistant"' in raw or b'"type":"user"' in raw:
                try:
                    d = json.loads(raw)
                except ValueError:
                    d = None
                if isinstance(d, dict) and not d.get("isSidechain"):
                    self.stats.add(d)
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


def process_alive(pid, started=None):
    """True if pid is running and (when known) was started at FILETIME `started`, so a reused pid doesn't count."""
    from ctypes import wintypes
    k32 = ctypes.windll.kernel32
    h = k32.OpenProcess(0x1000, False, int(pid))  # PROCESS_QUERY_LIMITED_INFORMATION
    if not h:
        return False
    try:
        code = wintypes.DWORD()
        if not k32.GetExitCodeProcess(h, ctypes.byref(code)) or code.value != 259:  # STILL_ACTIVE
            return False
        if started:
            times = [wintypes.FILETIME() for _ in range(4)]
            if k32.GetProcessTimes(h, *[ctypes.byref(t) for t in times]):
                made = (times[0].dwHighDateTime << 32) | times[0].dwLowDateTime
                return abs(made - int(started)) < 10_000_000  # within a second
        return True
    finally:
        k32.CloseHandle(h)


def open_transcripts():
    """Transcripts of the Claude Code sessions that are open right now, from ~/.claude/sessions."""
    found = []
    for f in glob.glob(os.path.join(SESSIONS, "*.json")):
        try:
            with open(f, encoding="utf-8") as fh:
                d = json.load(fh)
            sid, pid = d.get("sessionId"), d.get("pid")
            if not sid or not pid or not process_alive(pid, d.get("procStart")):
                continue
        except (OSError, ValueError, TypeError):
            continue
        found += glob.glob(os.path.join(PROJECTS, "*", glob.escape(sid) + ".jsonl"))[:1]
    return found


def stage_for(g):
    if g < 0.35:
        return "New growth", "ok", "plenty of room"
    if g < 0.66:
        return "Full canopy", "ok", "still comfortable"
    if g < 0.80:
        return "Wild shoots", "warn", "old detail piling up"
    if g < 0.92:
        return "Leaves turning", "warn", "finish this step, then compact"
    return "Dropping leaves", "crit", "compact now"


def fmt_k(t):
    return f"{t / 1e6:.2g}M" if t >= 1e6 else f"{round(t / 1000)}k"


def fmt_tok(t):
    return f"{t / 1e6:.1f}M" if t >= 1e6 else f"{round(t / 1000)}k"


def plural(n, word):
    return f"{word}" if n == 1 else f"{word}s"


def fmt_dur(sec):
    m = int(sec // 60)
    if m < 1:
        return "<1m"
    if m < 60:
        return f"{m}m"
    if m < 48 * 60:
        return f"{m // 60}h {m % 60}m"
    return f"{m // 1440}d {m % 1440 // 60}h"


def fmt_since(sec):
    return "just now" if sec < 60 else fmt_dur(sec) + " ago"


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

    SHARED_KEYS = ("theme", "project_themes", "pinned", "ambient", "zen", "topmost", "window")

    def __init__(self):
        self.cfg = load_config()
        self.cfg_seen = config_mtime()
        set_theme(self.cfg["theme"])
        self.root = tk.Tk()
        self.root.withdraw()
        self.f = self.root.winfo_fpixels("1i") / 96
        self.W = round(self.BASE_W * self.f)
        self.pad = round(14 * self.f)
        self.make_scenes()
        self.sessions = {}  # transcript path -> Session, one per tree in the grove
        self.order = []  # grove order, oldest tree first so trees don't jump around
        self.focus_path = None
        self.follow = True  # focus follows the newest session until the user picks a tree
        self.resume_follow = False
        self.view = "focus"  # "focus" = one full card, "grove" = a tree per active session
        self.grove_first = 0  # carousel: index of the first tree in view
        self.grove_x = 0.0  # where the carousel is drawn, in trees (slides toward grove_first)
        self.grove_slide = None  # (from, to, start time) while sliding
        self.live, self.live_at = set(), 0  # transcripts of the sessions open right now, and when we last looked
        self._empty = Session(self.cfg, path="")
        self.grove_cache = {}
        self.chrome = self.cfg["theme"]
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
            "light": font("segoeuil.ttf", 34 * self.f, "segoeui.ttf"), "sub": font("segoeui.ttf", 10.5 * self.f),
            "num": font("seguisb.ttf", 11 * self.f), "icon": font("SegoeIcons.ttf", 12 * self.f, "segmdl2.ttf"),
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
        self.edge, self.edge_i = [], 0
        self.can_at = 0
        self.leaf_cache = (None, [])
        self.sway_cache = {}
        self.card = None  # (key, image) of the last full session card, reused by ambient frames
        self.card_scene = (0, "#000000")
        self.amb = []  # ambient particles: motes in the breeze, fireflies at night
        self.tint = ((255, 255, 255), 0.0)
        self.next_mote = self.next_leaf = 0
        self.dt = 50
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
        self.inside = False  # pointer over the widget (zen mode shows its % tag then)
        self.label.bind("<Enter>", lambda e: self.set_inside(True))
        self.label.bind("<Leave>", lambda e: self.set_inside(False))
        self.label.bind("<Double-Button-1>", self.toggle_zen)
        self.label.bind("<Button-3>", self.menu)
        self.label.bind("<MouseWheel>", lambda e: self.scroll_grove(-1 if e.delta > 0 else 1))
        self.topvar = tk.BooleanVar(value=self.cfg["topmost"])
        self.pinvar = tk.BooleanVar(value=bool(self.cfg.get("pinned")))
        self.themevar = tk.StringVar(value=self.cfg["theme"] if self.cfg["theme"] in THEME_NAMES else "Moss")
        self.zenvar = tk.BooleanVar(value=bool(self.cfg.get("zen")))
        self.ambvar = tk.BooleanVar(value=self.cfg.get("ambient", True))
        self.projvar = tk.StringVar(value="")
        self.viewvar = tk.StringVar(value=self.view)

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
        """Open sessions and transcripts touched in the last GROVE_MINUTES, newest first
        (the newest overall if none)."""
        now, found = time.time(), []
        if now - self.live_at > LIVE_SECONDS:
            self.live_at = now
            try:
                self.live = {os.path.normcase(p) for p in open_transcripts()}
            except Exception:
                self.live = set()
        for p in glob.glob(os.path.join(PROJECTS, "*", "*.jsonl")):
            try:
                found.append((os.path.getmtime(p), p))
            except OSError:
                pass
        found.sort(reverse=True)
        active = [p for m, p in found if now - m < GROVE_MINUTES * 60 or os.path.normcase(p) in self.live]
        return active[:GROVE_MAX] or [p for _, p in found[:1]]

    def rescan(self):
        """Look for open sessions again and re-read every transcript's stats from the start."""
        self.live_at = 0
        self.sessions.clear()
        self.grove_cache, self.sway_cache, self.tree_key = {}, {}, None
        self.refresh_sessions()
        self.g = self.session.g
        self.tween = None
        n = len(self.order)
        self.caption = (f"Found {n} {plural(n, 'active session')}.", "muted", time.time() + 6)
        if self.view == "grove" and n <= 1:
            self.view = "focus"
        self.draw()

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
                s.refresh(git=p == focus)
                s.seen_cc, s.seen_restores = s.compactions, s.restores
            else:
                s.g_before = s.g
                s.refresh(git=p == focus)
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

    def reload_config(self):
        """Pick up settings the desktop app changed in the shared config file."""
        m = config_mtime()
        if m == self.cfg_seen:
            return
        self.cfg_seen = m
        disk = load_config()
        if all(disk.get(k) == self.cfg.get(k) for k in self.SHARED_KEYS):
            return
        for k in self.SHARED_KEYS:
            self.cfg[k] = disk.get(k)
        self.topvar.set(bool(self.cfg["topmost"]))
        self.root.attributes("-topmost", bool(self.cfg["topmost"]))
        self.pinvar.set(bool(self.cfg.get("pinned")))
        self.themevar.set(self.cfg["theme"] if self.cfg["theme"] in THEME_NAMES else "Moss")
        self.zenvar.set(bool(self.cfg.get("zen")))
        self.ambvar.set(self.cfg.get("ambient", True))
        self.grove_cache, self.sway_cache, self.tree_key, self.card = {}, {}, None, None

    def step(self):
        now = time.time()
        self.reload_config()
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
        if self.phase == "idle" and self.tween is None and abs(s.g - self.g) > 0.002:
            self.tween = (self.g, s.g, now, 1.2)  # grow (or settle) smoothly to the new context size
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
        if phase == "compacting":
            self.edge, self.edge_i = [], 0
        if phase != "idle":
            self.caption = None

    def start_prune(self, frm, to):
        self.prune(frm, to)
        self.set_phase("pruned")

    def prune(self, frm, to):
        falling = [l for l in each_leaf(frm, self.session.tree) if l[5] > BASELINE]
        for x, y, s, rot, gl, _ in random.sample(falling, min(130, len(falling))):
            self.spawn(x, y, s, rot, leaf_color(gl), burst=True)
        dropped = max(0.0, frm - to)
        self.pile = make_pile(dropped * 110, 100 + self.session.compactions)
        self.tween = (frm, to, time.time() + 0.2, 0.9)

    def water(self, msg):
        """Rehydrate: a watering can tips in and pours onto the soil, ripples, then new buds open."""
        self.set_phase("watering")
        self.pending_restore = None
        self.can_at = time.time()
        for i in range(30):  # positioned at the spout when they appear
            self.particles.append({"kind": "pour", "x": None, "y": None, "vx": -(0.15 + random.random() * 0.08),
                                   "vy": random.random() * 0.03, "life": 1.0, "wait": 450 + i * 55})
        leaves = list(each_leaf(min(1.0, max(self.session.g, BASELINE) + 0.15), self.session.tree))  # next growth
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
        key = (self.focus_path, round(g, 3))
        if self.leaf_cache[0] != key:
            self.leaf_cache = (key, list(each_leaf(g, self.session.tree)))
        return self.leaf_cache[1]

    # --- ambient: what the session is doing, shown in the scene ---
    def ambient_on(self):
        return self.cfg.get("ambient", True) and not (self.view == "grove" and len(self.order) > 1)

    def working(self):
        """Claude is mid-turn: the session's log changed in the last few seconds."""
        s = self.session
        return bool(s.path) and time.time() - s.mtime < 8

    def sleeping(self):
        s = self.session
        return bool(s.path) and time.time() - s.mtime > 1800

    def sky(self):
        """Target tint over the scene: (rgb, alpha), from the clock, deeper when the session sleeps."""
        if self.sleeping():
            return (10, 14, 36), 0.4
        lt = time.localtime()
        h = lt.tm_hour + lt.tm_min / 60
        if 5 <= h < 8:
            return (255, 160, 110), 0.12 * (1 - abs(h - 6.5) / 1.5)
        if 8 <= h < 17:
            return (255, 255, 255), 0.0
        if 17 <= h < 19:
            return (255, 130, 70), 0.10 * (h - 17) / 2
        if 19 <= h < 21:
            t = (h - 19) / 2
            return tuple(round(lerp(a, b, t)) for a, b in zip((255, 130, 70), (25, 35, 80))), lerp(0.10, 0.22, t)
        return (25, 35, 80), 0.22

    def night(self):
        h = time.localtime().tm_hour
        return self.sleeping() or h >= 21 or h < 5

    def update_ambient(self, dt):
        """Returns True while something in the ambience is moving."""
        if not self.ambient_on():
            self.amb = []
            return False
        now = time.time()
        rgb_t, a_t = self.sky()
        c, a = self.tint
        a2 = a + (a_t - a) * 0.08
        c2 = tuple(round(lerp(x, y, 0.08)) for x, y in zip(c, rgb_t))
        moving = abs(a2 - a) > 0.002
        self.tint = (c2, a2)
        working, sleeping = self.working(), self.sleeping()
        top = self.scene.crop[1]
        if working and self.phase == "idle" and now >= self.next_mote:  # drifting motes in the breeze
            self.next_mote = now + 0.25 + random.random() * 0.25
            self.amb.append({"kind": "mote", "x": self.scene.crop[0] - 4, "y": random.uniform(top + 40, 380),
                             "vx": 0.04 + random.random() * 0.05, "ph": random.random() * TAU, "life": 1.0})
        flies = [p for p in self.amb if p["kind"] == "fly"]
        if sleeping and len(flies) < 7:
            self.amb.append({"kind": "fly", "x": random.uniform(160, 440), "y": random.uniform(140, 380),
                             "vx": 0.0, "vy": 0.0, "ph": random.random() * TAU, "life": 1.0})
        for p in self.amb:
            if p["kind"] == "mote":
                p["x"] += p["vx"] * dt
                p["y"] += math.sin(p["ph"] + p["x"] * 0.03) * 0.012 * dt
                if p["x"] > self.scene.crop[2] + 4:
                    p["life"] = 0
            else:  # fireflies wander and fade out once the session wakes
                p["vx"] = clamp(p["vx"] + random.uniform(-0.002, 0.002) * dt, -0.03, 0.03)
                p["vy"] = clamp(p["vy"] + random.uniform(-0.002, 0.002) * dt, -0.03, 0.03)
                p["x"], p["y"] = p["x"] + p["vx"] * dt, p["y"] + p["vy"] * dt
                if not 130 < p["x"] < 470:
                    p["vx"] = -p["vx"]
                if not 110 < p["y"] < 390:
                    p["vy"] = -p["vy"]
                if not sleeping:
                    p["life"] -= dt / 1500
        self.amb = [p for p in self.amb if p["life"] > 0]
        # while waiting on you, an occasional single leaf lets go
        if not working and not sleeping and self.phase == "idle" and self.g > 0.2 and now >= self.next_leaf:
            self.next_leaf = now + 9 + random.random() * 8
            pool = self.leaves_at(self.g)
            if pool:
                x, y, s, rot, gl, _ = random.choice(pool)
                self.spawn(x, y, s, rot, leaf_color(gl), burst=False)
        return moving or bool(self.amb) or working

    def spout(self):
        """Watering can pivot, tilt and spout tip, in scene units."""
        t = time.time() - self.can_at
        if t < 0.4:
            tilt = -0.6 * (1 - (1 - t / 0.4) ** 2)
        elif t < 2.5:
            tilt = -0.6
        else:
            tilt = -0.6 * max(0.0, 1 - (t - 2.5) / 0.5)
        px, py = 482, self.scene.crop[1] + 46
        sx, sy = -40 * 1.5, -16 * 1.5
        return px, py, tilt, (px + sx * math.cos(tilt) - sy * math.sin(tilt), py + sx * math.sin(tilt) + sy * math.cos(tilt))

    def canopy_edge(self):
        """Outer leaves from left to right over the top, for the shears to work along."""
        pool = self.leaves_at(self.g)
        if not pool:
            return []
        cx = sum(l[0] for l in pool) / len(pool)
        cy = sum(l[1] for l in pool) / len(pool)
        far = {}
        for l in pool:
            a = math.atan2(l[1] - cy, l[0] - cx)  # screen y points down: the top half is negative
            if a > math.pi - 0.35:
                a -= TAU  # just below horizontal on the left counts as the start of the sweep
            if a > 0.35:
                continue  # skip the underside
            b = int((a + math.pi + 0.35) * 8)
            d2 = (l[0] - cx) ** 2 + (l[1] - cy) ** 2
            if b not in far or d2 > far[b][0]:
                far[b] = (d2, l)
        return [far[b][1] for b in sorted(far)]  # left -> over the top -> right

    def tick(self):
        try:
            self.animate()
        finally:  # an error in one frame must not stop the animation loop
            self.root.after(self.dt, self.tick)

    def animate(self):
        now = time.time()
        dt = self.dt
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
                if not self.edge:
                    self.edge, self.edge_i = self.canopy_edge(), 0
                if self.edge:  # work along the canopy edge, left to right over the top
                    x, y, *_r = self.edge[self.edge_i % len(self.edge)]
                    self.edge_i += 2
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
        ambient_moving = self.update_ambient(dt)
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
            elif kind == "pour":  # from the can's spout, arcing down onto the soil
                if p["x"] is None:
                    p["x"], p["y"] = self.spout()[3]
                p["vy"] += 0.00145 * dt
                p["x"] += p["vx"] * dt
                p["y"] += p["vy"] * dt
                if p["y"] >= 395:
                    p["kind"], p["y"], p["life"] = "ripple", 396, 1.0
            elif kind == "ripple":
                p["life"] -= dt / 650
            elif kind == "bud":
                p["life"] -= dt / 1100
        self.particles = [p for p in self.particles if p["life"] > 0]
        can_out = self.phase == "watering" or now - self.can_at < 3.2
        if self.grove_slide:
            frm, to, t0 = self.grove_slide
            t = clamp((now - t0) / GROVE_SLIDE, 0, 1)
            self.grove_x = lerp(frm, to, 1 - (1 - t) ** 3)
            if t >= 1:
                self.grove_slide = None
            active = True
        busy = active or self.particles or can_out
        if busy or ambient_moving:
            self.draw(scene_only=not busy)
        # full speed for compaction effects, a calmer pace for ambience, slow polling otherwise
        self.dt = 50 if busy else (250 if self.sleeping() else 125) if ambient_moving else 250

    # --- drawing ---
    def make_scenes(self):
        self.scene_cache = {}
        self.tree_key = None
        self.scene = self.get_scene("card")

    def get_scene(self, kind, width=None):
        """Scene backgrounds are cached per palette, so each theme in use keeps its own."""
        if kind == "card":  # edge to edge, with headroom above the canopy for the % readout
            width, crop = self.W, FOCUS_CROP
        elif kind == "zen":
            width, crop = self.W - 2 * self.pad, CROP
        else:
            crop = GROVE_CROP
        key = (THEME_KEY, kind, width)
        if key not in self.scene_cache:
            self.scene_cache[key] = Scene(width, crop)
        return self.scene_cache[key]

    def theme_for(self, s):
        """A project's own theme if one is set for it, otherwise the widget's theme."""
        per = self.cfg.get("project_themes") or {}
        return per.get(s.name.lower()) or self.cfg["theme"]

    def tree(self):
        s = self.session
        sway = None
        if self.ambient_on() and self.working() and self.phase == "idle" and not self.tween:
            frame = int(time.time() * 7) % 8  # a looping 8-frame breeze, rendered on demand
            sway = frame / 8 * TAU
        key = (id(self.scene), s.path, round(self.g, 3), s.compactions, len(self.pile), sway)
        if key != self.tree_key:
            cached = self.sway_cache.get(key)
            if cached is None:
                cached = self.scene.render(self.g, s.compactions, self.pile, s.tree, sway)
                if sway is not None:
                    if len(self.sway_cache) > 24:
                        self.sway_cache.clear()
                    self.sway_cache[key] = cached
            self.tree_key, self.tree_img = key, cached
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
        if self.ambient_on():
            self.draw_ambient(d, size)
        for p in self.particles:
            if p.get("wait", 0) > 0 or p.get("x") is None:
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
            elif p["kind"] in ("drop", "pour"):
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
        if self.phase == "watering" or time.time() - self.can_at < 3.2:
            self.draw_can(d)
        return layer

    def draw_ambient(self, d, size):
        """Clock/sleep tint over the scene, the moon at night, fireflies, breeze motes."""
        k = self.scene.k
        (r, g, b), a = self.tint
        if a > 0.003:
            d.rectangle([0, 0, size[0], size[1]], fill=(r, g, b, int(255 * a)))
        if self.night():
            mx, my = self.V(self.scene.crop[2] - 72, self.scene.crop[1] + 52)
            for rr, al in ((26, 18), (19, 34)):
                d.ellipse([mx - rr * k, my - rr * k, mx + rr * k, my + rr * k], fill=(240, 236, 214, al))
            rr = 12 * k
            d.ellipse([mx - rr, my - rr, mx + rr, my + rr], fill=(240, 236, 214, 235))
            for cx, cy, cr in ((-4, -3, 2.6), (3, 4, 1.8), (5, -4, 1.3)):  # craters
                d.ellipse([mx + (cx - cr) * k, my + (cy - cr) * k, mx + (cx + cr) * k, my + (cy + cr) * k],
                          fill=(214, 208, 184, 235))
        now = time.time()
        mote = (90, 96, 100) if is_light() else (232, 232, 214)
        for p in self.amb:
            x, y = self.V(p["x"], p["y"])
            if p["kind"] == "mote":
                rr = 2.0 * k
                d.ellipse([x - rr * 2.2, y - rr * 2.2, x + rr * 2.2, y + rr * 2.2], fill=mote + (34,))
                d.ellipse([x - rr, y - rr, x + rr, y + rr], fill=mote + (170,))
            else:
                glow = 0.5 + 0.5 * math.sin(now * 2.2 + p["ph"])
                al = clamp(p["life"], 0, 1) * glow
                for rr, f_ in ((7, 0.22), (3.5, 0.5), (1.6, 1.0)):
                    d.ellipse([x - rr * k, y - rr * k, x + rr * k, y + rr * k], fill=(222, 246, 140, int(255 * al * f_)))

    def draw_can(self, d):
        """A watering can at the top right, tipping its spout down toward the pot."""
        k = self.scene.k
        px, py, tilt, _tip = self.spout()
        s = 1.5
        ca, sa = math.cos(tilt), math.sin(tilt)

        def P(x, y):
            return self.V(px + (x * ca - y * sa) * s, py + (x * sa + y * ca) * s)

        light = is_light()
        body = (128, 138, 144) if light else (176, 186, 192)
        dark = (88, 96, 102) if light else (120, 130, 136)
        d.polygon([P(-12, -4), P(-40, -18), P(-40, -13), P(-12, 4)], fill=dark)  # spout
        hx, hy = P(-41, -15.5)
        rr = 3.2 * s * k
        d.ellipse([hx - rr, hy - rr, hx + rr, hy + rr], fill=dark)  # rose
        d.polygon([P(-16, -12), P(18, -12), P(16, 13), P(-14, 13)], fill=body)  # body
        d.line([P(-17, -12), P(19, -12)], fill=dark, width=max(1, round(2.4 * k)))  # rim
        d.line([P(-15, 4), P(17, 4)], fill=rgb(C["pot"]), width=max(1, round(3.2 * k)))  # band
        hc = P(24, 0)
        rr = 9 * s * k
        d.arc([hc[0] - rr, hc[1] - rr, hc[0] + rr, hc[1] + rr], start=-100 + math.degrees(tilt),
              end=100 + math.degrees(tilt), fill=dark, width=max(2, round(2.6 * k)))  # handle

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

    def draw(self, scene_only=False):
        grove = self.view == "grove" and len(self.order) > 1
        # a session's card takes its project's theme; the grove's frame uses the widget theme
        self.chrome = self.cfg["theme"] if grove else self.theme_for(self.session)
        set_theme(self.chrome)
        self.scene = self.get_scene("zen" if self.cfg.get("zen") else "card")
        card_key = (THEME_KEY, self.focus_path, round(self.g, 3))
        if (scene_only and not self.cfg.get("zen") and not grove and self.card
                and self.card[0] == card_key):
            img = self.card[1].copy()  # ambient frame: only the scene band changes
            ty, col = self.card_scene
            self.paint_scene(img, ty, self.g, col)
            ImageDraw.Draw(img).rectangle([0, 0, img.width - 1, img.height - 1], outline=C["line"])
        else:
            self.hits = []
            if self.cfg.get("zen"):
                img = self.render_zen()
            elif grove:
                img = self.render_grove()
            else:
                img = self.render_focus()
                self.card = (card_key, img)
        if self.label.cget("bg") != C["panel"]:
            self.root.configure(bg=C["panel"])
            self.label.configure(bg=C["panel"])
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

    def grove_per(self):
        return min(len(self.order), GROVE_PAGE)

    def grove_clamp(self):
        """Keep the carousel in range after sessions come and go."""
        last = max(0, len(self.order) - self.grove_per())
        if self.grove_first > last:
            self.grove_first = last
        if not self.grove_slide:
            self.grove_x = float(self.grove_first)

    def grove_go(self, first, animate=True):
        first = clamp(first, 0, max(0, len(self.order) - self.grove_per()))
        if first == self.grove_first:
            return
        self.grove_first = first
        if animate:
            self.grove_slide = (self.grove_x, float(first), time.time())
        else:
            self.grove_slide, self.grove_x = None, float(first)
        self.hover_key = None
        self.draw()

    def scroll_grove(self, step):
        """A page left or right, wrapping around at either end."""
        if self.view != "grove" or len(self.order) <= GROVE_PAGE:
            return
        per, last = self.grove_per(), len(self.order) - self.grove_per()
        if step > 0:
            self.grove_go(0 if self.grove_first >= last else self.grove_first + per)
        else:
            self.grove_go(last if self.grove_first <= 0 else self.grove_first - per)

    def grove_page(self):
        """(current page, page count) for the carousel dots."""
        per = self.grove_per()
        return math.ceil(self.grove_first / per), math.ceil(len(self.order) / per)

    def grove_tree(self, s, width):
        """One grove tree in its session's theme (cached), leaving the frame's theme applied afterwards."""
        set_theme(self.theme_for(s))
        key = (THEME_KEY, width, round(s.g, 3), s.compactions)
        cached = self.grove_cache.get(s.path)
        if not cached or cached[0] != key:
            img = self.get_scene("grove", width).render(s.g, s.compactions, [], s.tree)
            cached = self.grove_cache[s.path] = (key, img)
        set_theme(self.chrome)
        return cached[1]

    def render_grove(self):
        """A carousel of trees, GROVE_PAGE at a time: arrows in the header, page dots below, or scroll the wheel."""
        f, F, pad = self.f, self.fonts, self.pad
        now = time.time()
        self.grove_clamp()
        paths = self.order
        n, per = len(paths), max(1, self.grove_per())
        paged = n > per
        gap = 10 * f
        W = max(self.W, round(2 * pad + per * 104 * f + (per - 1) * gap))
        cell = (W - 2 * pad - (per - 1) * gap) / per
        scene = self.get_scene("grove", int(cell))
        info_h = 8 * f + 16 * f + 14 * f + 22 * f + 10 * f + 14 * f  # title, project, %, meter, status
        H = round(pad + 30 * f + scene.h + info_h + 22 * f + pad)
        img = Image.new("RGBA", (W, H), C["panel"])
        d = ImageDraw.Draw(img)
        d.rectangle([0, 0, W - 1, H - 1], outline=C["line"])
        d.text((pad, pad), "Grove", font=F["title"], fill=C["ink"])
        if paged:
            first = round(self.grove_x)
            count = f"{first + 1}–{min(n, first + per)} of {n}"
            xr = W - pad
            for arrow, step in (("›", 1), ("‹", -1)):
                bw_ = d.textlength(arrow, font=F["title"]) + 12 * f
                rect = (xr - bw_, pad - 3 * f, xr, pad + 19 * f)
                hovered = self.hover_key == ("scroll", step)
                if hovered:
                    d.rounded_rectangle(rect, radius=6 * f, fill=C["line"])
                d.text((xr - bw_ + 6 * f, pad - 2 * f), arrow, font=F["title"], fill=C["ink"] if hovered else C["muted"])
                self.hits.append((rect, "scroll", step))
                xr -= bw_ + 2 * f
                if step == 1:
                    xr -= d.textlength(count, font=F["mono"]) + 6 * f
                    d.text((xr + 3 * f, pad + 4 * f), count, font=F["mono"], fill=C["muted"])
        else:
            count = f"{n} active"
            d.text((W - pad - d.textlength(count, font=F["mono"]), pad + 4 * f), count, font=F["mono"], fill=C["muted"])
        y0 = pad + 30 * f
        # the trees go on their own layer, clipped to the viewport, so they slide in and out at its edges
        vx0, vx1 = round(pad - 6 * f), round(W - pad + 6 * f)
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        main, img, d = (img, d), layer, ImageDraw.Draw(layer)
        for i, p in enumerate(paths):
            x = pad + (i - self.grove_x) * (cell + gap)
            if x + cell + 5 * f < vx0 or x - 5 * f > vx1:
                continue
            s = self.sessions[p]
            g = s.g
            rect = (x - 5 * f, y0 - 5 * f, x + cell + 5 * f, y0 + scene.h + info_h)
            if not self.grove_slide and rect[0] >= vx0 - 1 and rect[2] <= vx1 + 1:
                self.hits.append((rect, "open", p))
            if self.hover_key == ("open", p):
                d.rounded_rectangle(rect, radius=8 * f, fill=C["line"])
            t = self.grove_tree(s, int(cell))
            img.paste(t, (round(x), round(y0)), t)
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
        (img, d), layer = main, layer.crop((vx0, 0, vx1, H))
        img.alpha_composite(layer, (vx0, 0))
        if paged:  # page dots, each one jumps to its page
            page, pages = self.grove_page()
            r, step = 3.5 * f, 16 * f
            cy = H - pad - 7 * f
            x = (W - (pages - 1) * step) / 2
            for k in range(pages):
                hovered = self.hover_key == ("grove_page", k)
                fill = C["ink"] if k == page else (C["muted"] if hovered else C["line"])
                d.ellipse([x - r, cy - r, x + r, cy + r], fill=fill)
                self.hits.append(((x - step / 2, cy - 9 * f, x + step / 2, cy + 9 * f), "grove_page", k))
                x += step
        else:
            hint = "Click a tree to open it"
            d.text(((W - d.textlength(hint, font=F["small"])) / 2, H - pad - 14 * f), hint, font=F["small"],
                   fill=C["muted"])
        return img

    def render_zen(self):
        """Just the bonsai: no text, a small tag on hover. A row of trees when several sessions are active."""
        f, F = self.f, self.fonts
        m = round(6 * f)
        if self.view == "grove" and len(self.order) > 1:
            self.grove_clamp()
            cell = int(110 * f)
            scene, n, per = self.get_scene("grove", cell), len(self.order), self.grove_per()
            W = 2 * m + per * cell + (per - 1) * m
            img = Image.new("RGBA", (W, 2 * m + scene.h), C["panel"])
            strip = Image.new("RGBA", (W - 2 * m, scene.h), (0, 0, 0, 0))  # clips trees sliding past the edges
            for i, p in enumerate(self.order):
                x = round((i - self.grove_x) * (cell + m))
                if -cell < x < strip.width:
                    t = self.grove_tree(self.sessions[p], cell)
                    strip.paste(t, (x, 0), t)
            img.alpha_composite(strip, (m, m))
            d = ImageDraw.Draw(img)
            for i, p in enumerate(self.order[self.grove_first:self.grove_first + per]):
                s, x = self.sessions[p], m + i * (cell + m)
                if self.grove_slide:
                    continue
                self.hits.append(((x, m, x + cell, m + scene.h), "open", p))
                if self.hover_key == ("open", p):
                    self.tag(d, x + 5 * f, m + 5 * f, f"{round(s.g * 100)}% · {s.title or s.name}", cell - 10 * f)
            if n > per and self.inside:  # small arrows at the edges while hovered; the wheel scrolls too
                for step, x in ((-1, m + 4 * f), (1, W - m - 26 * f)):
                    rect = (x, m + scene.h / 2 - 11 * f, x + 22 * f, m + scene.h / 2 + 11 * f)
                    hovered = self.hover_key == ("scroll", step)
                    d.rounded_rectangle(rect, radius=11 * f, fill=C["line"] if hovered else C["panel"], outline=C["line"])
                    arrow = "‹" if step < 0 else "›"
                    d.text((rect[0] + (22 * f - d.textlength(arrow, font=F["title"])) / 2, rect[1] - 1 * f), arrow,
                           font=F["title"], fill=C["ink"])
                    self.hits.append((rect, "scroll", step))
        else:
            tree = self.tree().copy()
            tree.alpha_composite(self.overlay(tree.size))
            img = Image.new("RGBA", (tree.width + 2 * m, tree.height + 2 * m), C["panel"])
            d = ImageDraw.Draw(img)
            img.paste(tree, (m, m), tree)
            if self.inside:
                label = f"{round(self.g * 100)}%"
                if self.phase in PHASE_TEXT:
                    label += " · " + PHASE_TEXT[self.phase][0].lower()
                self.tag(d, m + 6 * f, m + 6 * f, label, tree.width - 12 * f)
        d.rectangle([0, 0, img.width - 1, img.height - 1], outline=C["line"])
        return img

    def tag(self, d, x, y, text, maxw):
        F, f = self.fonts, self.f
        text = ellipsize(d, text, F["small"], maxw - 14 * f)
        w = d.textlength(text, font=F["small"]) + 14 * f
        d.rounded_rectangle([x, y, x + w, y + 20 * f], radius=10 * f, fill=C["panel"], outline=C["line"])
        d.text((x + 7 * f, y + 3 * f), text, font=F["small"], fill=C["ink"])

    def toggle_zen(self, e=None):
        if e is not None and not self.cfg.get("zen") and self.hit_at(e.x, e.y):
            return  # double-clicking a button or tab shouldn't also switch modes
        self.cfg["zen"] = not self.cfg.get("zen")
        self.zenvar.set(self.cfg["zen"])
        self.cfg_seen = save_config(self.cfg, "zen")
        self.hover_key = None
        self.draw()

    def render_focus(self):
        """The session card: identity, the tree with its readout, status, tokens, then grouped stats."""
        s, f, F, pad, W = self.session, self.f, self.fonts, self.pad, self.W
        now = time.time()
        g = self.g
        label, state, advice = stage_for(g)
        if self.phase in PHASE_TEXT:
            label, state = PHASE_TEXT[self.phase]
        col = C[state]
        img = Image.new("RGBA", (W, round(self.scene.h + 420 * f)), C["panel"])  # cropped to fit at the end
        d = ImageDraw.Draw(img)

        # identity: session title, then project · branch · changes
        y = pad
        x = pad
        if len(self.order) > 1:  # back to the grove
            back = f"‹ {len(self.order)}"
            bw_ = d.textlength(back, font=F["title"]) + 10 * f
            hovered = self.hover_key == ("grove", None)
            rect = (pad - 5 * f, y - 3 * f, pad + bw_ - 3 * f, y + 19 * f)
            if hovered:
                d.rounded_rectangle(rect, radius=6 * f, fill=C["line"])
            d.text((pad, y - 2 * f), back, font=F["title"], fill=C["ink"] if hovered else C["muted"])
            self.hits.append((rect, "grove", None))
            x = pad + bw_ + 2 * f
        ago = now - s.mtime if s.mtime else 9e9
        live = ago < 60
        idle = "" if live else fmt_ago(ago).replace("idle ", "")
        iw = d.textlength(idle, font=F["sub"]) + (6 * f if idle else 0)
        r = 3.5 * f
        d.ellipse([W - pad - 2 * r, y + 4 * f, W - pad, y + 4 * f + 2 * r], fill=C["ok"] if live else C["muted"])
        if idle:
            d.text((W - pad - 2 * r - iw, y + 1 * f), idle, font=F["sub"], fill=C["muted"])
        title = s.title or (s.name if s.cwd else "No session")
        d.text((x, y - 2 * f), ellipsize(d, title, F["title"], W - x - pad - 2 * r - iw - 8 * f), font=F["title"],
               fill=C["ink"])
        y += 20 * f
        branch, dirty = s.git
        parts = [s.name] if s.cwd and s.title and s.title != s.name else []
        if branch:
            parts.append("⎇")
            parts.append(f"{branch}  ·  " + (f"{dirty} changed" if dirty else "clean"))
        x = pad
        for i, part in enumerate(parts):
            if part == "⎇":
                d.text((x, y - 1 * f), part, font=F["symbol"], fill=C["muted"])
                x += d.textlength(part, font=F["symbol"]) + 3 * f
                continue
            text = part + ("  ·  " if i + 1 < len(parts) and parts[i + 1] != "⎇" else ("  ·  " if i + 1 < len(parts) else ""))
            text = ellipsize(d, text, F["sub"], W - pad - x)
            d.text((x, y), text, font=F["sub"], fill=C["muted"])
            x += d.textlength(text, font=F["sub"])
        y = round(52 * f)

        ty = y
        th = self.paint_scene(img, ty, g, col)
        d = ImageDraw.Draw(img)
        self.card_scene = (ty, col)
        y = ty + th + 10 * f
        return self.render_focus_lower(img, d, y, s, label, advice, col, now)

    def paint_scene(self, img, ty, g, col):
        """The tree edge to edge, readout on the wall, the shelf edge doubling as the meter.
        Ambient frames repaint just this band over the last full card."""
        s, f, F, pad, W = self.session, self.f, self.fonts, self.pad, self.W
        now = time.time()
        tree = self.tree().copy()
        tree.alpha_composite(self.overlay(tree.size))
        img.paste(tree, (0, ty), tree)
        d = ImageDraw.Draw(img)
        wall = rgb(C["wall"])
        if self.ambient_on() and self.tint[1] > 0.003:  # match the tinted wall so the outline doesn't show
            wall = tuple(round(lerp(c, t, self.tint[1])) for c, t in zip(wall, self.tint[0]))
        halo = {"stroke_width": max(1, round(3 * f)), "stroke_fill": wall}
        pct = f"{round(g * 100)}%"
        d.text((pad, ty + 2 * f), pct, font=F["light"], fill=C["ink"], **halo)
        pw = d.textlength(pct, font=F["light"])
        if s.after_compact:
            tok = "compacted, waiting for a reply"
        elif s.tokens is not None:
            tok = f"{fmt_tok(s.tokens)} of {fmt_k(self.cfg['window'])}"
        else:
            tok = ""
        d.text((pad + pw + 8 * f, ty + 24 * f), tok, font=F["sub"], fill=C["muted"], **halo)
        shelf = ty + (452 - self.scene.crop[1]) * self.scene.k
        mh = 4 * f
        d.rectangle([0, shelf - mh / 2, W, shelf + mh / 2], fill=C["line"])
        if self.phase == "compacting":  # a shimmer slides along the shelf while compacting
            span = W * 0.3
            a = (W + span) * ((now * 0.6) % 1) - span
            d.rectangle([max(0, a), shelf - mh / 2, min(W, a + span), shelf + mh / 2], fill=col)
        else:
            d.rectangle([0, shelf - mh / 2, W * clamp(g, 0, 1), shelf + mh / 2], fill=col)
            tx = W * 0.85
            d.rectangle([tx - f, shelf - 5 * f, tx + f, shelf + 5 * f], fill=C["muted"])
        return tree.height

    def render_focus_lower(self, img, d, y, s, label, advice, col, now):
        f, F, pad, W = self.f, self.fonts, self.pad, self.W
        # status: stage (or compaction progress) and the compact button
        text, tcol = advice, "muted"
        if self.phase == "armed":
            text = "copied: Ctrl+V, Enter in Claude" if self.found_app else "copied /compact: paste it in Claude"
            tcol = "warn"
        elif self.phase == "compacting":
            exp = s.last_duration
            text = f"{int(now - self.phase_at)}s" + (f" of ~{round(exp)}s" if exp else "")
        elif self.phase in ("pruned", "watering"):
            text = "restoring state…"
        elif self.caption and now < self.caption[2]:
            text, tcol = self.caption[0], self.caption[1]
        d.ellipse([pad, y + 6 * f, pad + 7 * f, y + 13 * f], fill=col)
        d.text((pad + 13 * f, y + 1 * f), label, font=F["num"], fill=C["ink"])
        lw = d.textlength(label, font=F["num"])
        bx0 = self.draw_button(d, y - 3 * f)
        d.text((pad + 13 * f + lw, y + 1 * f), ellipsize(d, "  ·  " + text, F["body"], bx0 - 8 * f - (pad + 13 * f + lw)),
               font=F["body"], fill=C[tcol])
        y += 32 * f
        if s.jobs:  # only while something is running
            n = len(s.jobs)
            desc = s.jobs[0].get("desc") or ""
            jt = ellipsize(d, f"{n} {plural(n, 'job')} running" + (f" · {desc}" if desc else ""), F["small"],
                           W - 2 * pad - 36 * f)
            jw = d.textlength(jt, font=F["small"]) + 34 * f
            d.rounded_rectangle([pad, y - 4 * f, pad + jw, y + 16 * f], radius=10 * f, outline=C["warn"],
                                width=max(1, round(f)))
            d.text((pad + 9 * f, y - 1 * f), "", font=F["icon"], fill=C["warn"])
            d.text((pad + 26 * f, y - 1 * f), jt, font=F["small"], fill=C["warn"])
            y += 26 * f

        # tokens: context per call over the session, then peak / avg / total
        st, tot = s.stats, s.stats.totals
        d.line([(pad, y), (W - pad, y)], fill=C["line"], width=max(1, round(f)))
        y += 10 * f
        if len(tot["series"]) >= 2:
            self.sparkline(img, pad, y, W - 2 * pad, 34 * f, tot["series"], col)
            d = ImageDraw.Draw(img)
            y += 40 * f
            self.runs(d, pad, y, [(fmt_tok(tot["peak"]), "n"), (" peak · ", "u"), (fmt_tok(tot["avg"]), "n"),
                                  (" avg · ", "u"), (fmt_tok(tot["total"]), "n"), (" total", "u")])
        else:
            d.text((pad, y), "No replies yet", font=F["body"], fill=C["muted"])
        y += 24 * f

        # grouped stats: context, work, time
        d.line([(pad, y), (W - pad, y)], fill=C["line"], width=max(1, round(f)))
        y += 10 * f
        cache = tot["cache"]
        cstyle = "n" if cache is None or cache >= 0.8 else "warn" if cache >= 0.5 else "crit"
        calls = sum(st.tools.values())
        estyle = "warn" if calls and st.errors / calls > 0.1 else "n"
        sep = " · "
        rows = [
            ("", [("–" if cache is None else f"{cache:.0%}", cstyle), (" cache" + sep, "u"),
                        (str(s.compactions), "n"), (" " + plural(s.compactions, "compact") + sep, "u"),
                        (str(tot["calls"]), "n"), (" " + plural(tot["calls"], "call"), "u")]),
            ("", [(str(calls), "n"), (" " + plural(calls, "tool") + sep, "u"), (str(st.errors), estyle),
                        (" " + plural(st.errors, "error") + sep, "u"), (str(len(st.files)), "n"),
                        (" " + plural(len(st.files), "file"), "u")]),
        ]
        time_row = []
        if st.started and s.mtime:
            time_row += [(fmt_dur(s.mtime - st.started), "n"), (sep, "u")]
        if st.last_prompt:
            since = now - st.last_prompt
            time_row += ([("just now", "n")] if since < 60 else [("asked ", "u"), (fmt_dur(since), "n"), (" ago", "u")])
            time_row += [(sep, "u")]
        time_row += [(str(st.prompts), "n"), (" " + plural(st.prompts, "prompt"), "u")]
        rows.append(("", time_row))
        for icon, parts in rows:
            d.text((pad, y + 2 * f), icon, font=F["icon"], fill=C["muted"])
            self.runs(d, pad + 22 * f, y, parts)
            y += 22 * f
        y += pad - 6 * f
        img = img.crop((0, 0, W, round(y)))
        d = ImageDraw.Draw(img)
        d.rectangle([0, 0, W - 1, img.height - 1], outline=C["line"])
        return img

    def runs(self, d, x, y, parts):
        """Left-to-right text runs: numbers bold in ink (or warn/crit), words muted. Stops at the edge."""
        F = self.fonts
        for text, style in parts:
            if style == "u":
                fnt, color = F["body"], C["muted"]
            else:
                fnt, color = F["num"], C["ink"] if style == "n" else C[style]
            w = d.textlength(text, font=fnt)
            if x + w > self.W - self.pad:
                return
            d.text((x, y), text, font=fnt, fill=color)
            x += w

    def sparkline(self, img, x0, y0, w, h, series, col):
        """Context per API call: filled area, dashed average, dot on the peak."""
        f = self.f
        if len(series) > w:  # one point per pixel is plenty; keep each bucket's max so peaks survive
            step = len(series) / w
            series = [max(series[int(i * step):max(int(i * step) + 1, int((i + 1) * step))]) for i in range(int(w))]
        top = max(series) * 1.12 or 1
        pts = [(x0 + w * i / (len(series) - 1), y0 + h - h * v / top) for i, v in enumerate(series)]
        layer = Image.new("RGBA", img.size)
        ImageDraw.Draw(layer).polygon([(x0, y0 + h)] + pts + [(x0 + w, y0 + h)], fill=rgb(col) + (52,))
        img.alpha_composite(layer)
        d = ImageDraw.Draw(img)
        d.line(pts, fill=col, width=max(1, round(1.4 * f)), joint="curve")
        avg = self.session.stats.totals["avg"]
        ay = y0 + h - h * avg / top
        x = x0
        while x < x0 + w:
            d.line([(x, ay), (min(x + 4 * f, x0 + w), ay)], fill=C["muted"], width=max(1, round(f)))
            x += 8 * f
        i = max(range(len(series)), key=series.__getitem__)
        px, py = pts[i]
        r = 3 * f
        d.ellipse([px - r, py - r, px + r, py + r], fill=C["ink"], outline=C["panel"], width=max(1, round(f)))

    def draw_button(self, d, y):
        """Round ✂ compact button at the right of the status line. Returns its left edge."""
        f, F = self.f, self.fonts
        busy = self.phase in ("compacting", "pruned", "watering")
        armed = self.phase == "armed"
        bd = 26 * f
        x0 = self.W - self.pad - bd
        if not busy:
            self.hits.append(((x0, y, x0 + bd, y + bd), "compact", None))
        hovered = self.hover_key == ("compact", None) and not busy
        d.ellipse([x0, y, x0 + bd, y + bd], fill=C["line"] if hovered else None,
                  outline=C["line"] if busy else (C["warn"] if armed else C["muted"]), width=max(1, round(f)))
        glyph = "✕" if armed else "✂"
        gw = d.textlength(glyph, font=F["symbol"])
        d.text((x0 + (bd - gw) / 2, y + 4 * f), glyph, font=F["symbol"],
               fill=C["muted"] if busy else (C["warn"] if armed else C["crit"]))
        return x0

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
        self.cfg_seen = save_config(self.cfg, "right", "bottom", drop=("x", "y"))

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
            if self.focus_path in self.order:  # open on the page with the tree you were looking at
                self.grove_go(self.order.index(self.focus_path) // self.grove_per() * self.grove_per(),
                              animate=False)
        elif action == "scroll":
            self.scroll_grove(arg)
            return
        elif action == "grove_page":
            self.grove_go(arg * self.grove_per())
            return
        elif action == "page":
            self.cfg["page"] = arg
            self.cfg_seen = save_config(self.cfg, "page")
        self.hover_key = None
        self.draw()

    def motion(self, e):
        self.set_hover(self.hit_at(e.x, e.y))

    def set_inside(self, on):
        self.inside = on
        if not on:
            self.hover_key = None
            self.label.configure(cursor="fleur")
        self.draw()

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
        for name in THEME_NAMES:
            label = {"Auto": "Auto (follows Windows)", "Seasons": "Seasons (changes with the date)"}.get(name, name)
            themes.add_radiobutton(label=label, value=name, variable=self.themevar, command=self.change_theme)
            if name == "Seasons":
                themes.add_separator()
        m.add_cascade(label="Theme", menu=themes)
        s = self.session
        if s.cwd:  # a theme just for this session's project
            per = self.cfg.get("project_themes") or {}
            self.projvar.set(per.get(s.name.lower(), ""))
            proj = tk.Menu(m, tearoff=0)
            proj.add_radiobutton(label="Same as the widget", value="", variable=self.projvar,
                                 command=self.change_project_theme)
            proj.add_separator()
            for name in THEME_NAMES:
                proj.add_radiobutton(label=name, value=name, variable=self.projvar, command=self.change_project_theme)
            m.add_cascade(label=f"Theme for {ellipsize_plain(s.name, 28)}", menu=proj)
        views = tk.Menu(m, tearoff=0)
        self.viewvar.set(self.view)
        views.add_radiobutton(label="Focus (one session)", value="focus", variable=self.viewvar,
                              command=self.change_view)
        several = len(self.order) > 1
        views.add_radiobutton(label="Grove (every active session)" if several else "Grove (only one session active)",
                              value="grove", variable=self.viewvar, command=self.change_view,
                              state="normal" if several else "disabled")
        m.add_cascade(label="View", menu=views)
        m.add_checkbutton(label="Zen mode", variable=self.zenvar, command=self.toggle_zen)
        m.add_checkbutton(label="Ambient animation", variable=self.ambvar, command=self.toggle_ambient)
        m.add_command(label="Rescan sessions", command=self.rescan)
        if self.view == "focus" and self.phase in ("idle", "armed"):
            m.add_command(label="Cancel compact" if self.phase == "armed" else "Compact",
                          command=lambda: self.do("compact", None))
        m.add_separator()
        m.add_command(label="Preview compact animation", command=self.run_preview)
        m.add_command(label="Quit", command=self.root.destroy)
        m.tk_popup(e.x_root, e.y_root)

    def change_view(self):
        if self.viewvar.get() == "grove":
            self.do("grove", None)
        elif self.view != "focus":
            self.do("open", self.focus_path)

    def toggle_top(self):
        self.cfg["topmost"] = self.topvar.get()
        self.root.attributes("-topmost", self.cfg["topmost"])
        self.cfg_seen = save_config(self.cfg, "topmost")

    def change_theme(self):
        self.cfg["theme"] = self.themevar.get()
        self.retheme()

    def change_project_theme(self):
        per = dict(self.cfg.get("project_themes") or {})
        name = self.session.name.lower()
        if self.projvar.get():
            per[name] = self.projvar.get()
        else:
            per.pop(name, None)
        self.cfg["project_themes"] = per
        self.retheme()

    def retheme(self):
        self.grove_cache, self.sway_cache, self.tree_key = {}, {}, None
        self.cfg_seen = save_config(self.cfg, "theme", "project_themes")
        self.draw()

    def toggle_ambient(self):
        self.cfg["ambient"] = self.ambvar.get()
        self.cfg_seen = save_config(self.cfg, "ambient")
        self.draw()

    def toggle_pin(self):
        self.cfg["pinned"] = self.session.path if self.pinvar.get() else None
        self.cfg_seen = save_config(self.cfg, "pinned")


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


def ellipsize_plain(text, n):
    return text if len(text) <= n else text[:n - 1] + "…"


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


def save_config(cfg, *keys, drop=()):
    """Write just these keys into the config file, keeping whatever else is there: the desktop app
    shares the file, so writing our whole (possibly stale) copy would undo its changes."""
    disk = {}
    try:
        with open(CONFIG, encoding="utf-8") as fh:
            disk = json.load(fh)
    except (OSError, ValueError):
        pass
    for k in keys:
        disk[k] = cfg.get(k)
    for k in drop:
        disk.pop(k, None)
    try:
        tmp = CONFIG + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(disk, fh, indent=2)
        os.replace(tmp, CONFIG)
    except OSError:
        pass
    return config_mtime()


def config_mtime():
    try:
        return os.path.getmtime(CONFIG)
    except OSError:
        return 0


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
