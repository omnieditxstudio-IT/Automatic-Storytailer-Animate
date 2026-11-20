"""The storyboard: two looks, one continuous world, drawn from beats.json + plan.json.

The generated scene.py calls build_film(doc). Alternation is already decided by
director.py: a board block gets a full-bleed blueprint panel behind hand-drawn chalk
items; a photo block stays on the night evidence wall with pinned photos, cards and
stamped documents. Every layout is driven by the line's own words, so a new voice or
script re-plans the film without touching this file.
"""
import json
import math
import pathlib
import re

import skia
import engine
from engine import (BigText, Card, Counter, DotField, Film, Item, PaperDoc, Print, Stamp,
                    paint, ramp, tile_image)

_orig_draw_text = engine.draw_text
_orig_text_width = engine.text_width

def _patched_draw_text(c, res, text, x, y, size, font="serif", rgb=engine.CREAM, a=1.0, track=0.0, align="left", reveal=None):
    if any(ord(ch) > 127 for ch in text):
        f = res.font(font, size)
        n = len(text) if reveal is None else int(reveal)
        shown = text[:n]
        if not shown:
            return 0
        total = f.measureText(shown)
        x0 = x - total / 2 if align == "center" else x - total if align == "right" else x
        p = engine.paint(rgb, a)
        blob = skia.TextBlob.MakeFromShapedText(shown, f)
        if blob:
            c.drawTextBlob(blob, x0, y, p)
        else:
            c.drawString(shown, x0, y, f, p)
        return total
    return _orig_draw_text(c, res, text, x, y, size, font, rgb, a, track, align, reveal)

def _patched_text_width(res, text, size, font="serif", track=0.0):
    if any(ord(ch) > 127 for ch in text):
        f = res.font(font, size)
        return f.measureText(text) + track * size * max(0, len(text) - 1)
    return _orig_text_width(res, text, size, font, track)

engine.draw_text = _patched_draw_text
engine.text_width = _patched_text_width

from board_items import (CHALK, CHALK_DIM, GOLDC, REDC, TEALC, WARM, CheckMark, HandGraph,
                         Icon, LoopPulse, ScribbleRows, SketchRect, StickFigure, Stroke)
from director import INK_RGB, content_words, words_of
import paths

# world units are 4K screen px at zoom 1; these sizes are tuned for zoom 0.42-0.55
KICK = 118
HEAD = 250
BIG = 430
NUM = 820
SUB = 210
ICON_R = 300
LW = 26

BOARD_ZOOM = {"title": 0.46, "chain": 0.44, "split": 0.44, "window": 0.46,
              "check": 0.44, "quote": 0.48, "stat": 0.55, "end": 0.42,
              "graph": 0.54, "stick": 0.44}
PHOTO_ZOOM = {"station": 0.48, "duo": 0.42, "doc": 0.47, "stat": 0.54,
              "graph": 0.49, "stick": 0.46, "quote": 0.45, "chain": 0.42,
              "check": 0.44}


class StylePanel(Item):
    """An opaque blueprint sheet under one board block (above the global board, below ink)."""
    z = -90

    def __init__(self, cx, cy, w, h, t_in, t_out, texture="blueprint.png"):
        super().__init__(t_in, t_out, None, False)
        self.cx, self.cy, self.w, self.h, self.texture = cx, cy, w, h, texture

    def bounds(self, res):
        return skia.Rect.MakeXYWH(self.cx - self.w / 2, self.cy - self.h / 2, self.w, self.h)

    def draw(self, c, res, t):
        a = ramp(t, self.t_in - 0.2, 0.25) * (1 - ramp(t, self.t_out, 0.3)) * self.fade(t)
        if a <= 0:
            return
        rect = skia.Rect.MakeXYWH(self.cx - self.w / 2, self.cy - self.h / 2, self.w, self.h)
        p = skia.Paint(AntiAlias=True)
        p.setAlphaf(a)
        try:
            img = res.image(self.texture, 1024)
            tile_image(c, img, rect, 2048, p, clip=False)
        except SystemExit:                    # prep_assets.py not run: draw the sheet in code
            c.drawRect(rect, paint((18, 44, 84), a))
            gp = paint((120, 160, 200), 0.16 * a, stroke=2)
            step = 256
            x = math.floor(rect.left() / step) * step
            while x < rect.right():
                c.drawLine(x, rect.top(), x, rect.bottom(), gp)
                x += step
            y = math.floor(rect.top() / step) * step
            while y < rect.bottom():
                c.drawLine(rect.left(), y, rect.right(), y, gp)
                y += step


def split_lines(text, max_chars=17):
    words, lines, cur = text.split(), [], ""
    for w in words:
        if cur and len(cur) + 1 + len(w) > max_chars:
            lines.append(cur); cur = w
        else:
            cur = (cur + " " + w).strip()
    if cur:
        lines.append(cur)
    return lines[:3]


def headline_lines(film, b, x, y, size, color, max_chars=17, t=None, type_on=0.35,
                   gap=1.08, grunge=True):
    lines = split_lines(b["headline"], max_chars)
    t0 = b["start"] + 0.04 if t is None else t
    for i, ln in enumerate(lines):
        film.add(BigText(ln, x, y + i * size * gap, size, t0 + i * 0.10, rgb=color,
                         font="cond", track=0.02, grunge=grunge, type_on=type_on))
    return len(lines)


def kicker(film, b, x, y, color=(126, 146, 190)):
    if b.get("kicker"):
        film.add(BigText(b["kicker"], x, y, KICK, b["start"] - 0.10, font="mono", rgb=color,
                         track=0.16, grunge=False, shadow=False))


def rule(film, b, x, y, w, rgb, t=None, width=LW):
    film.add(Stroke([(x - w / 2, y), (x, y + 14), (x + w / 2, y)], b["start"] + 0.24 if t is None else t,
                    seed=b["id"] * 13 + 5, rgb=rgb, width=width, wob=5, dur=0.55))


def split_sides(text, points):
    """(left, right) words for a comparison: the words either side of versus/before/after."""
    toks = words_of(text)
    low = [re.sub(r"[^a-z0-9]", "", t.lower()) for t in toks]
    for key in ("versus", "vs", "compared", "comparison", "difference", "instead"):
        if key in low:
            i = low.index(key)
            left = content_words(" ".join(toks[:i]))[-1:]
            right = content_words(" ".join(toks[i + 1:]))[:1]
            if left and right:
                return left[0].upper(), right[0].upper()
    if "before" in low and "after" in low:
        bi, ai = low.index("before"), low.index("after")
        left = content_words(" ".join(toks[max(0, bi - 4):bi]))[-1:]
        right = content_words(" ".join(toks[ai + 1:ai + 5]))[:1]
        if left and right:
            return left[0].upper(), right[0].upper()
    if "not" in low:
        # "sales, not cash": the two words either side of the negation
        i = low.index("not")
        left = content_words(" ".join(toks[:i]))[-1:]
        right = content_words(" ".join(toks[i + 1:]))[:1]
        if left and right:
            return left[0].upper(), right[0].upper()
    pts = (list(points) + ["", ""])[:2]
    return pts[0].upper() if pts[0] else "A", pts[1].upper() if pts[1] else "B"


def is_comparison(text):
    low = text.lower()
    return bool(re.search(r"\b(versus|vs\.?|compared|comparison|difference|changed|instead|not)\b", low)
                or ("before" in low and "after" in low))


# ------------------------------------------------------------------ board looks
def board_beat(film, b):
    x, y = b["x"], b["y"]
    ink = INK_RGB[b["ink"]]
    lay = b["layout"]
    if lay == "end":
        kicker(film, b, x, y - 1640)
    else:
        kicker(film, b, x, y - 1330)

    if lay == "title":
        n = headline_lines(film, b, x, y - 790, BIG, CHALK, max_chars=16, gap=1.02)
        rule(film, b, x, y - 790 + n * BIG * 1.02 - 120, 3000, ink)
        film.add(Icon(b["icon"], x, y + 640, ICON_R + 20, b["start"] + 0.55, rgb=ink))
        film.add(LoopPulse(x, y + 640, b["start"] + 0.5, period=2.2, count=2, rgb=ink, max_r=520))

    elif lay == "chain":
        film.add(Icon(b["icon"], x + 2300, y - 880, ICON_R - 90, b["start"] + 0.10, rgb=ink))
        headline_lines(film, b, x, y - 560, HEAD, CHALK, max_chars=22)
        pts = b["points"] + [""] * (3 - len(b["points"]))
        for i, off in enumerate((-1900, 0, 1900)):
            film.add(SketchRect(x + off, y + 60, 1320, 640, b["start"] + 0.22 + i * 0.18,
                                seed=b["id"] * 10 + i, width=LW - 4))
            if pts[i]:
                film.add(BigText(pts[i], x + off, y + 90, 176, b["start"] + 0.42 + i * 0.18,
                                 rgb=CHALK, font="cond", grunge=False, type_on=0.25))
        for i, (a, c) in enumerate(((-1240, -620), (620, 1240))):
            film.add(Stroke([(x + a, y + 60), (x + c, y + 60)], b["start"] + 0.55 + i * 0.22,
                            seed=b["id"] * 10 + 5 + i, rgb=WARM, width=LW - 6, arrow=True))

    elif lay == "split":
        headline_lines(film, b, x, y - 860, HEAD, CHALK, max_chars=26)
        labels = split_sides(b.get("caption") or b["headline"], b["points"])
        for i, off in enumerate((-1450, 1450)):
            film.add(SketchRect(x + off, y + 80, 2500, 900, b["start"] + 0.14 + i * 0.20,
                                seed=b["id"] * 10 + i, width=LW))
            film.add(BigText(labels[i], x + off, y + 100, 196, b["start"] + 0.38 + i * 0.20,
                             rgb=CHALK, font="cond", grunge=False, type_on=0.25))
        film.add(Stroke([(x, y - 620), (x + 40, y - 300), (x - 30, y + 30), (x + 40, y + 360),
                         (x, y + 700)], b["start"] + 0.5, seed=b["id"] * 10 + 7,
                        rgb=CHALK_DIM, width=LW - 10, wob=16))

    elif lay == "window":
        headline_lines(film, b, x, y - 1080, HEAD, CHALK, max_chars=20)
        wx = x - 300
        film.add(SketchRect(wx, y + 140, 3600, 1500, b["start"] + 0.10, seed=b["id"] * 10 + 1, width=LW))
        film.add(Stroke([(wx - 1800, y - 470), (wx + 1800, y - 470)], b["start"] + 0.34,
                        seed=b["id"] * 10 + 2, rgb=CHALK_DIM, width=LW - 12))
        for i, dx in enumerate((-1660, -1500, -1340)):
            film.add(CheckMark(wx + dx, y - 530, b["start"] + 0.40 + i * 0.05, size=26,
                               rgb=REDC if i == 0 else GOLDC, dur=0.2, cross=False))
        film.add(ScribbleRows(wx, y - 400, 3300, 7, b["start"] + 0.42, seed=b["id"] * 10 + 3,
                              row_h=105, gap=38, highlight_row=3, highlight_rgb=REDC,
                              rgb=CHALK_DIM, width=LW - 16))
        if b["points"]:
            film.add(BigText(b["points"][0], wx + 1180, y + 590, 116,
                             b["start"] + 0.75, font="mono", rgb=TEALC, grunge=False, track=0.10))
        film.add(Icon(b["icon"], x + 2250, y - 1180, ICON_R - 90, b["start"] + 0.55, rgb=ink))

    elif lay == "check":
        headline_lines(film, b, x, y - 930, HEAD, CHALK, max_chars=26)
        pts = b["points"]
        # advice lines get ticks, "don't do this" lines get red crosses
        bad = bool(re.match(r"\s*(don'?t|do not|never)\b", b["caption"], re.I))
        mark = REDC if bad else GOLDC
        for i, yy in enumerate((-470, -30, 410)):
            if i >= len(pts):
                break
            film.add(CheckMark(x - 900, yy, b["start"] + 0.22 + i * 0.20, size=150,
                               rgb=mark, cross=bad))
            film.add(BigText(pts[i], x + 250, yy + 50, 210, b["start"] + 0.36 + i * 0.20,
                             rgb=CHALK, font="cond", grunge=False, type_on=0.22))
        film.add(Icon(b["icon"], x + 1850, y - 900, ICON_R - 70, b["start"] + 0.4, rgb=ink))

    elif lay == "quote":
        n = headline_lines(film, b, x, y - 620, BIG - 60, CHALK, max_chars=15, gap=1.06)
        rule(film, b, x, y - 620 + (n - 1) * (BIG - 60) * 1.06 + 160, 2700, ink)
        film.add(Icon(b["icon"], x, y + 800, ICON_R - 40, b["start"] + 0.5, rgb=ink))

    elif lay == "graph":
        # the line's own numbers, drawn as bars that grow while the value counts up
        bars = b.get("bars") or []
        n = headline_lines(film, b, x, y - 1250, 300, CHALK, max_chars=24)
        rule(film, b, x, y - 1250 + n * HEAD * 1.08 + 100, 2400, CHALK_DIM, width=LW - 10)
        nt = b.get("number_t", b["start"])
        film.add(HandGraph(x, y + 520, 3400, 1650,
                           [(bar["label"], bar["value"],
                             b["start"] + (bar["at"] if bar.get("at") is not None
                                           else max(0.3, nt - b["start"])))
                            for bar in bars],
                           t_in=b["start"] + 0.02, rgb=CHALK, ink=ink,
                           fmt="{:,.0f}%" if b.get("number_suffix") == "%" else "{:,.0f}",
                           strike=b.get("strike") or (), seed=b["id"] * 7 + 3,
                           label_size=120))
        film.add(Icon(b["icon"], x + 2300, y - 1100, 200, b["start"] + 0.6, rgb=ink))

    elif lay == "stick":
        # a chalk person lives on the board, with the line in a speech bubble
        film.add(StickFigure(x - 1250, y + 1080, 1600, b["start"] + 0.05,
                             pose=b.get("pose", "idle"), prop=b.get("prop"),
                             rgb=CHALK, accent=ink))
        bx, by = x + 850, y + 160
        film.add(SketchRect(bx, by, 1850, 1130, b["start"] + 0.16, seed=b["id"] * 10 + 2, width=LW - 4))
        film.add(Stroke([(x - 520, y - 120), (x - 220, by + 260)], b["start"] + 0.30,
                        seed=b["id"] * 10 + 6, rgb=CHALK_DIM, width=LW - 8))
        lines = split_lines(b["headline"], 12)[:3]
        size = 210 if len(lines) <= 2 else 168
        y0 = by - (len(lines) - 1) * size * 0.55
        for i, ln in enumerate(lines):
            film.add(BigText(ln, bx, y0 + i * size * 1.06, size, b["start"] + 0.35 + i * 0.10,
                             rgb=CHALK, font="cond", grunge=False, type_on=0.25))

    elif lay == "stat":
        val = b.get("number_value") or 0
        if val:
            # the number rolls up and lands on the word that says it
            nt = b.get("number_t", b["start"] + 0.4)
            t_in = max(b["start"] + 0.08, nt - 0.55)
            film.add(Counter(x, y - 300, NUM if val < 10000 else NUM * 0.70, int(val),
                             t_in, dur=min(1.0, max(0.4, nt - t_in)),
                             suffix=b.get("number_suffix") or "", rgb=ink, sfx=False))
        else:
            num = b.get("number") or (b["points"][0] if b["points"] else "1")
            film.add(BigText(num[:6], x, y - 300, NUM, b.get("number_t", b["start"] + 0.05),
                             rgb=ink, font="cond", type_on=0.30, hit=0.8))
        headline_lines(film, b, x, y + 330, HEAD, CHALK, max_chars=28)
        rule(film, b, x, y + 120, 2200, CHALK_DIM, width=LW - 10)
        film.add(Icon(b["icon"], x + 2050, y - 780, ICON_R - 90, b["start"] + 0.5, rgb=ink))

    elif lay == "end":
        film.add(Icon(b["icon"], x, y - 940, ICON_R + 60, b["start"] + 0.05, rgb=ink))
        n = headline_lines(film, b, x, y - 160, BIG, CHALK, max_chars=16, gap=1.02)
        rule(film, b, x, y - 160 + n * BIG * 1.02 - 120, 2900, ink)
        film.add(BigText("SOURCES IN CREDITS", x, y + 700, 96, b["start"] + 0.9, font="mono",
                         rgb=(150, 168, 205), track=0.18, grunge=False, shadow=False))


# ------------------------------------------------------------------ photo look
def info_card(film, x, y, w, h, t_in, title, points, ink, rgb=(246, 243, 236),
              text_rgb=(30, 32, 38)):
    """A card whose title cannot outgrow the panel (Card itself does not wrap)."""
    title = (title or "").strip()
    if len(title) > 27:
        title = title[:26].rstrip() + "."
    film.add(Card(x, y, w, h, t_in, title=title, lines=tuple(points[:3]), accent=ink,
                  rgb=rgb, text_rgb=text_rgb,
                  title_size=min(124.0, h * 0.115), body_size=min(96.0, h * 0.068)))


def photo_beat(film, b, photos, sizes):
    x, y = b["x"], b["y"]
    ink = INK_RGB[b["ink"]]
    lay = b["layout"]
    caption = b["caption"]
    bad = bool(re.match(r"\s*(don'?t|do not|never)\b", caption, re.I))

    def label_for(pid, compact=False):
        meta = photos.get(pid) or {}
        what = (meta.get("what") or meta.get("query") or "").strip()
        if compact:
            return what[:18].upper() if what else None
        lic = (meta.get("license") or "").strip()
        return f"{what[:26]} | {lic}" if what else None

    def print_at(pid, cx, cy, w, rot, t_in, compact=True):
        s = sizes.get(pid) or {}
        aspect = (s.get("w") or 3) / max(1, (s.get("h") or 2))
        film.add(Print(pid, cx, cy, min(w, w * max(0.8, aspect)), rot=rot, t_in=t_in,
                       label=label_for(pid, compact), label_t=t_in + 0.45, sfx=False))

    def top_head(size=210, yy=-1400, chars=24):
        nn = headline_lines(film, b, x, yy, size, (248, 246, 240), max_chars=chars)
        rule(film, b, x, yy + (nn - 1) * size * 1.08 + size * 0.82, 2200, ink, width=LW - 10)

    # only the card-like layouts carry the standing top bar; the others compose their own
    if lay in ("station", "doc", "stat"):
        kicker(film, b, x, y - 1660, color=(132, 152, 198))
        n = headline_lines(film, b, x, y - 1350, 230, (248, 246, 240), max_chars=22)
        rule(film, b, x, y - 1210 + (n - 1) * 235, 2400, ink)
        if lay != "stat":
            film.add(Icon(b["icon"], x + 2350, y - 1300, 210, b["start"] + 0.30, rgb=ink))

    if lay == "station":
        pid = b.get("photo")
        if pid and pid in photos:
            s = sizes.get(pid) or {}
            aspect = (s.get("w") or 3) / max(1, (s.get("h") or 2))
            w = min(2500.0, 1820.0 * max(0.8, aspect))
            film.add(Print(pid, x - 1350, y + 20, w, rot=-1.3,
                           t_in=b["start"] + 0.10, label=label_for(pid),
                           label_t=b["start"] + 0.55, sfx=False))
            info_card(film, x + 1500, y + 60, 2400, 1080, b["start"] + 0.28,
                      b["headline"], b["points"], ink)
        else:
            info_card(film, x, y + 30, 3200, 1500, b["start"] + 0.15,
                      b["headline"], b["points"], ink)
            film.add(Icon(b["icon"], x - 1950, y - 1250, 190, b["start"] + 0.4, rgb=ink))

    elif lay == "doc":
        film.add(PaperDoc(x - 1250, y + 40, 2050, 1900, rot=-1.3, t_in=b["start"] + 0.08,
                          header=[((b["kicker"] or "REPORT")[:22], 120, "cond")],
                          rows=13, sentence=" ".join(b["points"])[:90], sentence_row=6,
                          sentence_size=60, pin=True))
        film.add(Stamp(b["headline"].split()[0][:12] if b["headline"] else "REPORT",
                       x + 1250, y - 380, size=170, rot=-7, t_in=b["start"] + 0.55, rgb=ink))
        info_card(film, x + 1450, y + 430, 2100, 950, b["start"] + 0.38,
                  "", b["points"], ink)

    elif lay == "quote":
        # one line at poster scale, with a small pinned photo for evidence
        pid = b.get("photo")
        if pid and pid in photos:
            print_at(pid, x - 1520, y + 1050, 760, -3.2, b["start"] + 0.10)
        lines = split_lines(b["headline"], 10)[:3]
        size = 350 if len(lines) <= 2 else 270
        y0 = y - 220 - (len(lines) - 1) * size * 0.55
        for i, ln in enumerate(lines):
            film.add(BigText(ln, x + 260, y0 + i * size * 1.04, size,
                             b["start"] + 0.04 + i * 0.12, rgb=(248, 246, 240),
                             font="cond", track=0.01, grunge=False, type_on=0.30))

    elif lay == "chain":
        # a photo strip: three pinned frames in a row, arrows between them
        top_head(200, y - 1450, 20)
        ids = sorted(photos)
        pid = b.get("photo")
        i = ids.index(pid) if pid in ids else 0
        if ids:
            for k, dx in enumerate((-1320, 0, 1320)):
                pp = ids[(i + k) % len(ids)]
                print_at(pp, x + dx, y + 300, 1180, (-1.6, 1.2, -1.0)[k],
                         b["start"] + 0.10 + k * 0.16)
        for k, (a, c) in enumerate(((-620, -260), (760, 1120))):
            film.add(Stroke([(x + a, y + 300), (x + c, y + 300)], b["start"] + 0.55 + k * 0.12,
                            seed=b["id"] * 10 + 5 + k, rgb=ink, width=LW - 8, arrow=True))
        if b["points"]:
            film.add(BigText("  ·  ".join(p.upper() for p in b["points"][:3]),
                             x, y + 1180, 88, b["start"] + 0.60, font="mono",
                             rgb=(206, 210, 220), track=0.14, grunge=False, shadow=False))

    elif lay == "check":
        # advice on the wall: ticks, or red crosses for a "don't"
        top_head(210, y - 1400, 24)
        pts = b["points"]
        mark = REDC if bad else GOLDC
        for i, yy in enumerate((-420, 40, 500)):
            if i >= len(pts):
                break
            film.add(CheckMark(x - 850, yy, b["start"] + 0.20 + i * 0.18, size=150,
                               rgb=mark, cross=bad))
            film.add(BigText(pts[i], x + 260, yy + 54, 200, b["start"] + 0.34 + i * 0.18,
                             rgb=(248, 246, 240), font="cond", grunge=False, type_on=0.22))

    elif lay == "duo":
        top_head(210, y - 1450, 24)
        ids = sorted(photos)
        pid = b.get("photo")
        i = ids.index(pid) if pid in ids else 0
        if ids:
            for k, (pp, dx, rot) in enumerate(((ids[i % len(ids)], -1250, -2.0),
                                               (ids[(i + 1) % len(ids)], 1250, 1.8))):
                print_at(pp, x + dx, y + 240, 1400, rot, b["start"] + 0.08 + k * 0.22)
        if is_comparison(caption):
            left, right = split_sides(caption, b["points"])
            for k, (lbl, dx) in enumerate(((left, -1250), (right, 1250))):
                film.add(BigText(lbl, x + dx, y + 1780, 170, b["start"] + 0.62 + k * 0.10,
                                 rgb=ink, font="cond", grunge=False, type_on=0.25))
        elif b["points"]:
            film.add(BigText("  ·  ".join(p.upper() for p in b["points"][:3]),
                             x, y + 1780, 92, b["start"] + 0.60, font="mono",
                             rgb=(206, 210, 220), track=0.14, grunge=False, shadow=False))

    elif lay == "graph":
        top_head(200, y - 1420, 24)
        pid = b.get("photo")
        if pid and pid in photos:
            print_at(pid, x - 1220, y + 240, 1420, -1.8, b["start"] + 0.06)
        nt = b.get("number_t", b["start"] + 0.5)
        film.add(HandGraph(x + 980, y + 400, 2000, 1180,
                           [(bar["label"], bar["value"],
                             b["start"] + (bar["at"] if bar.get("at") is not None
                                           else max(0.3, nt - b["start"])))
                            for bar in (b.get("bars") or [])],
                           t_in=b["start"] + 0.02, rgb=(248, 246, 240), ink=ink,
                           fmt="{:,.0f}%" if b.get("number_suffix") == "%" else "{:,.0f}",
                           strike=b.get("strike") or (), seed=b["id"] * 7 + 5,
                           label_size=88))

    elif lay == "stick":
        top_head(200, y - 1420, 22)
        pid = b.get("photo")
        if pid and pid in photos:
            print_at(pid, x - 1300, y + 120, 1350, -1.6, b["start"] + 0.08)
        film.add(StickFigure(x + 1150, y + 1020, 1450, b["start"] + 0.12,
                             pose=b.get("pose", "idle"), prop=b.get("prop"),
                             rgb=(248, 246, 240), accent=ink))
        if b["points"]:
            film.add(BigText(b["points"][0], x + 1150, y + 1520, 96, b["start"] + 0.55,
                             font="mono", rgb=(206, 210, 220), track=0.14,
                             grunge=False, shadow=False))

    elif lay == "stat":
        val = b.get("number_value") or 0
        suffix = b.get("number_suffix") or ""
        if val:
            nt = b.get("number_t", b["start"] + 0.4)
            t_in = max(b["start"] + 0.08, nt - 0.55)
            film.add(Counter(x, y - 140, NUM if val < 10000 else NUM * 0.70, int(val),
                             t_in, dur=min(1.0, max(0.4, nt - t_in)),
                             suffix=suffix, rgb=ink, sfx=False))
        else:
            num = b.get("number") or (b["points"][0] if b["points"] else "1")
            film.add(BigText(num[:6], x, y - 140, NUM, b.get("number_t", b["start"] + 0.06),
                             rgb=ink, font="cond", type_on=0.30, hit=0.8, grunge=False))
        # a poster line under the numeral, not a near-empty white card: on the photo wall
        # the big-number beat is a caption plate, so the frame never reads as unfinished
        rule(film, b, x, y + 900, 2300, ink)
        pts = "  ·  ".join(p.upper() for p in b["points"][:3])
        if pts:
            film.add(BigText(pts, x, y + 1040, 92, b["start"] + 0.55, font="mono",
                             rgb=(206, 210, 220), track=0.16, grunge=False, shadow=False))

    else:                                    # anything unmapped: a safe card station
        info_card(film, x, y + 40, 3000, 1400, b["start"] + 0.15,
                  b["headline"], b["points"], ink)


# ------------------------------------------------------------------ film
def build_film(doc, project=None):
    proj = pathlib.Path(project or doc.dir)
    beats = paths.load_json(proj / "beats.json")
    plan = paths.load_json(proj / "plan.json")
    photos_spec = paths.load_json(proj / "photos.json", {"photos": []}) or {"photos": []}
    photos = {p["id"]: p for p in photos_spec.get("photos", []) if p.get("id")}

    film = Film(doc.duration, fps=plan.get("fps", 30), look="night")
    film.fade_in, film.fade_out = 0.7, 2.4
    film.auto_cues, film.auto_whoosh = False, False

    # faint dust across the wall: keeps wide shots from going flat
    span = plan["blocks"][-1]["x_last"] + 6000
    pts = [(1200 + (i * 7919) % span, -2600 + (i * 521) % 5200) for i in range(240)]
    film.add(DotField(pts, 0.2, min(doc.duration - 1.0, 40.0), seed=101, r=10,
                      rgb=(56, 66, 96), sfx=False))

    by_id = {b["id"]: b for b in beats["beats"]}
    # the last line becomes the end card: show the film's title, not the sentence's keywords
    if plan["blocks"]:
        last = by_id[plan["blocks"][-1]["beats"][-1]]
        last["headline"] = (plan.get("title") or last["headline"]).upper()[:30]
    prev_end = None
    for blk in plan["blocks"]:
        if blk["style"] == "board":
            film.add(StylePanel((blk["x0"] + blk.get("x_last", blk["x0"])) / 2, 0,
                                max(blk.get("x_last", blk["x0"]) - blk["x0"], 6000) + 14000, 22000,
                                blk["start"] - 0.18, blk["end"] + 0.30))
        for bid in blk["beats"]:
            b = by_id[bid]
            if blk["style"] == "board":
                board_beat(film, b)
            else:
                photo_beat(film, b, photos, doc.meta)
        # camera: a framed key at the start of each line and a slow drift until it ends,
        # so a cut to the next line reads as a cut, not a pan across empty board
        table = BOARD_ZOOM if blk["style"] == "board" else PHOTO_ZOOM
        for bid in blk["beats"]:
            b = by_id[bid]
            z = table.get(b["layout"], 0.46)
            if prev_end and prev_end[0] < b["start"] - 0.033:
                # hold on the previous station over the pause, so the cut between
                # blocks does not whip through empty world
                film.shot(b["start"] - 0.033, prev_end[1], prev_end[2], prev_end[3])
            film.shot(b["start"], b["x"], b["y"], z * 0.985)
            film.shot(max(b["start"] + 0.45, b["end"] - 0.05), b["x"] + 46, b["y"] - 12, z * 1.025)
            prev_end = (max(b["start"] + 0.45, b["end"] - 0.05), b["x"] + 46, b["y"] - 12, z * 1.025)

    return film
