"""Hand-drawn whiteboard items for the blueprint cutaways.

Every mark is a jittered stroke revealed with partial_path, so it reads as drawn by
hand. Icon() is the neon icon family (20 glyphs, two glow passes, hot core).
"""
import math

import numpy as np
import skia

from engine import Item, ease_out_cubic, paint, partial_path, ramp, draw_text
from icons_painters import PAINTERS

CHALK = (232, 226, 210)       # warm white chalk
CHALK_DIM = (178, 186, 200)
WARM = (255, 213, 165)        # hand-label marker ink
REDC = (238, 96, 74)          # red pencil, legible on blueprint
TEALC = (140, 226, 220)
GOLDC = (240, 196, 92)
VIOLETC = (198, 160, 255)


def poly_path(points):
    """A plain polyline path (this skia build has no Path.MakeFromPolyline)."""
    p = skia.Path()
    p.moveTo(points[0][0], points[0][1])
    for x, y in points[1:]:
        p.lineTo(x, y)
    return p


def jit_path(points, seed, close=False, wob=9.0):
    rng = np.random.default_rng(seed)
    p = skia.Path()
    pts = []
    for i, (x, y) in enumerate(points):
        if i == 0:
            pts.append((x, y))
            continue
        n = max(2, int(math.hypot(x - points[i - 1][0], y - points[i - 1][1]) / 170))
        for j in range(1, n + 1):
            f = j / n
            pts.append((points[i - 1][0] + (x - points[i - 1][0]) * f + rng.uniform(-wob, wob),
                        points[i - 1][1] + (y - points[i - 1][1]) * f + rng.uniform(-wob, wob)))
    p.moveTo(*pts[0])
    for q in pts[1:]:
        p.lineTo(*q)
    if close:
        p.close()
    return p


class SketchRect(Item):
    """A hand-drawn wobbly rectangle, drawn on over `dur`."""
    z = 20

    def __init__(self, cx, cy, w, h, t_in, seed=1, rgb=CHALK, width=10, dur=0.55, t_out=None, sfx=False):
        super().__init__(t_in, t_out, None, sfx)
        x0, y0, x1, y1 = cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2
        self.p = jit_path([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], seed, close=True, wob=10)
        self.rgb, self.wd, self.dur = rgb, width, dur

    def bounds(self, res):
        return self.p.getBounds().makeOutset(80, 80)

    def draw(self, c, res, t):
        u = ease_out_cubic(ramp(t, self.t_in, self.dur))
        a = self.fade(t)
        if u <= 0 or a <= 0:
            return
        c.drawPath(partial_path(self.p, u), paint(self.rgb, 0.92 * a, stroke=self.wd))


class Stroke(Item):
    """A single wobbly drawn line (free polyline), revealed over `dur`."""
    z = 22

    def __init__(self, points, t_in, seed=5, rgb=CHALK, width=10, dur=0.4, wob=8.0,
                 t_out=None, sfx=False, arrow=False):
        super().__init__(t_in, t_out, None, sfx)
        rng = np.random.default_rng(seed)
        p = skia.Path()
        pts = list(points)
        dense = []
        for i in range(1, len(pts)):
            (x0, y0), (x1, y1) = pts[i - 1], pts[i]
            n = max(1, int(math.hypot(x1 - x0, y1 - y0) / 140))
            dense.append(pts[i - 1])
            for j in range(1, n + 1):
                f = j / n
                lim = 0 if j == n else 1
                dense.append((x0 + (x1 - x0) * f + rng.uniform(-wob, wob) * lim,
                              y0 + (y1 - y0) * f + rng.uniform(-wob, wob) * lim))
        p.moveTo(*dense[0])
        for q in dense[1:]:
            p.lineTo(*q)
        self.p, self.rgb, self.wd, self.dur, self.arrow = p, rgb, width, dur, arrow
        self.tip = (pts[-1], pts[-2])

    def bounds(self, res):
        return self.p.getBounds().makeOutset(80, 80)

    def draw(self, c, res, t):
        u = ease_out_cubic(ramp(t, self.t_in, self.dur))
        a = self.fade(t)
        if u <= 0 or a <= 0:
            return
        c.drawPath(partial_path(self.p, u), paint(self.rgb, 0.92 * a, stroke=self.wd))
        if self.arrow and u > 0.9:
            (x1, y1), (x0, y0) = self.tip
            ang = math.atan2(y1 - y0, x1 - x0)
            k = self.wd * 4.6
            for sgn in (-1, 1):
                c.drawLine(x1, y1, x1 - k * math.cos(ang + sgn * 0.62),
                           y1 - k * math.sin(ang + sgn * 0.62),
                           paint(self.rgb, 0.92 * a, stroke=self.wd))


class ScribbleRows(Item):
    """Rows of wavy hand-scrawled 'code' lines inside a window, revealed row by row."""
    z = 24

    def __init__(self, cx, y_top, w, rows, t_in, seed=3, row_h=95, gap=42, rgb=CHALK_DIM,
                 width=9, dur=0.09, stagger=0.085, highlight_row=None, highlight_rgb=REDC,
                 t_out=None, sfx=False):
        super().__init__(t_in, t_out, None, sfx)
        rng = np.random.default_rng(seed)
        self.rows, self.dur, self.stagger, self.times = [], dur, stagger, []
        for i in range(rows):
            lw = w * (0.52 + rng.uniform(0, 0.4))
            lx = cx - w / 2 + 60
            y0 = y_top + i * (row_h + gap) + row_h / 2
            pts = [(lx, y0)]
            for j in range(1, 13):
                pts.append((lx + lw * j / 12, y0 + rng.uniform(-7, 7)))
            self.rows.append((pts, i == highlight_row))
            self.times.append(t_in + i * stagger)
        self.rgb, self.width, self.highlight_rgb = rgb, width, highlight_rgb

    def bounds(self, res):
        return None

    def draw(self, c, res, t):
        a = self.fade(t)
        for i, (pts, hot) in enumerate(self.rows):
            u = ease_out_cubic(ramp(t, self.times[i], self.dur + 0.12))
            if u <= 0:
                continue
            p = skia.Path()
            p.moveTo(*pts[0])
            for q in pts[1:]:
                p.lineTo(*q)
            c.drawPath(partial_path(p, u), paint(self.highlight_rgb if hot else self.rgb,
                                                 0.9 * a, stroke=self.width + (2 if hot else 0)))


class CheckMark(Item):
    z = 26

    def __init__(self, x, y, t_in, size=150, rgb=GOLDC, dur=0.4, t_out=None, sfx=False, cross=False):
        super().__init__(t_in, t_out, None, sfx)
        self.x, self.y, self.size, self.rgb, self.dur, self.cross = x, y, size, rgb, dur, cross

    def bounds(self, res):
        return skia.Rect.MakeXYWH(self.x - self.size, self.y - self.size, self.size * 2, self.size * 2)

    def draw(self, c, res, t):
        u = ease_out_cubic(ramp(t, self.t_in, self.dur))
        if u <= 0:
            return
        a = self.fade(t)
        p = skia.Path()
        s = self.size
        if self.cross:
            p.moveTo(self.x - s * 0.55, self.y - s * 0.55)
            p.lineTo(self.x + s * 0.55, self.y + s * 0.55)
            p.moveTo(self.x + s * 0.55, self.y - s * 0.55)
            p.lineTo(self.x - s * 0.55, self.y + s * 0.55)
        else:
            p.moveTo(self.x - s * 0.55, self.y + s * 0.05)
            p.lineTo(self.x - s * 0.12, self.y + s * 0.42)
            p.lineTo(self.x + s * 0.62, self.y - s * 0.45)
        c.drawPath(partial_path(p, u), paint(self.rgb, 0.95 * a, stroke=max(12, s * 0.13)))


class LoopPulse(Item):
    """Expanding scan rings from a centre point, repeating."""
    z = 18

    def __init__(self, x, y, t_in, period=1.6, count=2, rgb=TEALC, max_r=850, t_out=None, sfx=False):
        super().__init__(t_in, t_out, None, sfx)
        self.x, self.y, self.period, self.count, self.rgb, self.max_r = x, y, period, count, rgb, max_r

    def bounds(self, res):
        r = self.max_r
        return skia.Rect.MakeXYWH(self.x - r, self.y - r, 2 * r, 2 * r)

    def draw(self, c, res, t):
        if t < self.t_in:
            return
        for i in range(self.count):
            ph = ((t - self.t_in) / self.period - i / self.count) % 1.0
            r = 130 + (self.max_r - 130) * ph
            a = 0.5 * (1 - ph) ** 1.6 * self.fade(t)
            if a > 0.02:
                c.drawCircle(self.x, self.y, r, paint(self.rgb, a, stroke=7))


class HandGraph(Item):
    """A hand-drawn bar chart. Bars grow one by one, each at its own t_at, and the value
    above counts up with the growth, so the number lands when the narrator says it.

    bars: [(label, value, t_at), ...]; fmt controls the printed value ("{:.0f}%", "{:.0f}").
    strike: indices crossed out in red (a claim to knock down).
    """
    z = 28

    def __init__(self, x, y, w, h, bars, t_in=0.0, rgb=CHALK, ink=(72, 226, 255),
                 fmt="{:.0f}%", max_value=None, dur=0.75, seed=3, t_out=None, sfx=False,
                 strike=(), label_size=104):
        super().__init__(t_in, t_out, None, sfx)
        self.x, self.y, self.w, self.h = x, y, w, h
        self.bars, self.rgb, self.ink, self.fmt = list(bars), rgb, ink, fmt
        self.dur, self.seed, self.strike = dur, seed, set(strike)
        top = max([v for _, v, _ in self.bars] + [1e-6])
        self.maxv = max_value or top * 1.18
        self.label_size = label_size

    def bounds(self, res):
        return skia.Rect.MakeXYWH(self.x - self.w, self.y - self.h, self.w * 2, self.h * 2)

    def draw(self, c, res, t):
        a = self.fade(t)
        if a <= 0:
            return
        x0, base = self.x - self.w / 2, self.y + self.h / 2
        x1, top = self.x + self.w / 2, self.y - self.h / 2
        # axes draw on first, in chalk
        ax = ease_out_cubic(ramp(t, self.t_in, 0.45))
        if ax > 0:
            c.drawPath(partial_path(poly_path([(x0, base), (x0, top)]), ax),
                       paint(self.rgb, 0.85 * a, stroke=10))
            c.drawPath(partial_path(poly_path([(x0, base), (x1, base)]), ax),
                       paint(self.rgb, 0.85 * a, stroke=10))
        n = len(self.bars)
        slot = (x1 - x0) * 0.94 / max(1, n)
        bw = slot * 0.56
        for i, (label, value, t_at) in enumerate(self.bars):
            u = ease_out_cubic(ramp(t, t_at, self.dur))
            if u <= 0:
                continue
            cx = x0 + slot * (i + 0.5)
            bh = (self.h * 0.86) * (value / self.maxv) * u
            rect = skia.Rect.MakeXYWH(cx - bw / 2, base - bh, bw, bh)
            c.drawRect(rect, paint(self.ink, 0.20 * a))
            c.drawRect(rect, paint(self.ink, 0.85 * a, stroke=9))
            shown = value * u
            txt = self.fmt.format(shown)
            draw_text(c, res, txt, cx, base - bh - 46, 132, "cond", self.rgb, 0.95 * a,
                      0.02, "center")
            if label:
                draw_text(c, res, label.upper(), cx, base + 86, self.label_size, "mono",
                          self.rgb, 0.7 * a, 0.12, "center")
            if i in self.strike and u > 0.95:
                c.drawLine(cx - bw * 0.62, base - bh * 0.55, cx + bw * 0.62, base - bh * 0.42,
                           paint(REDC, 0.95 * a, stroke=14))


POSES = {
    #        head        shoulders  hands (dx,dy from shoulder)     feet
    "idle":   dict(lean=0.0, hand_l=(-0.30, 0.52), hand_r=(0.30, 0.52), foot_l=(-0.22, 0.0), foot_r=(0.22, 0.0)),
    "watch":  dict(lean=0.04, hand_l=(-0.26, 0.50), hand_r=(0.66, 0.30), foot_l=(-0.24, 0.0), foot_r=(0.24, 0.0)),
    "phone":  dict(lean=0.10, hand_l=(-0.34, 0.34), hand_r=(0.30, 0.06), foot_l=(-0.20, 0.0), foot_r=(0.24, 0.0)),
    "camera": dict(lean=-0.04, hand_l=(-0.34, 0.06), hand_r=(0.34, 0.06), foot_l=(-0.28, 0.0), foot_r=(0.28, 0.0)),
    "build":  dict(lean=0.02, hand_l=(-0.40, 0.24), hand_r=(0.40, 0.24), foot_l=(-0.24, 0.0), foot_r=(0.24, 0.0)),
    "walk":   dict(lean=0.06, hand_l=(-0.22, 0.44), hand_r=(0.34, 0.40), foot_l=(-0.34, 0.0), foot_r=(0.30, 0.0)),
}


class StickFigure(Item):
    """A chalk stickman with a prop, drawn on stroke by stroke, then breathing gently.

    pose: idle | watch | phone | camera | build | walk
    prop: chart | phone | camera | box | None
    h: figure height in world px (1200 reads at zoom 0.46)
    """
    z = 32

    def __init__(self, x, y, h, t_in, pose="idle", prop=None, rgb=CHALK,
                 accent=(72, 226, 255), dur=0.9, t_out=None, sfx=False):
        super().__init__(t_in, t_out, None, sfx)
        self.x, self.y, self.h = x, y, h
        self.pose = POSES.get(pose, POSES["idle"])
        self.prop, self.rgb, self.accent, self.dur = prop, rgb, accent, dur

    def bounds(self, res):
        h = self.h
        return skia.Rect.MakeXYWH(self.x - h, self.y - h * 1.2, h * 2, h * 1.33)

    def draw(self, c, res, t):
        a = self.fade(t)
        if a <= 0:
            return
        u = ease_out_cubic(ramp(t, self.t_in, self.dur))
        if u <= 0:
            return
        bob = math.sin((t - self.t_in) * 1.7) * self.h * 0.008
        h = self.h
        cx, fy = self.x, self.y + bob
        p = self.pose
        head_c = (cx + p["lean"] * h, fy - h * 0.86)
        neck = (cx + p["lean"] * h, fy - h * 0.70)
        hip = (cx, fy - h * 0.36)
        sh_l = (neck[0] - h * 0.10, neck[1] + h * 0.03)
        sh_r = (neck[0] + h * 0.10, neck[1] + h * 0.03)
        hand_l = (sh_l[0] + p["hand_l"][0] * h, sh_l[1] + p["hand_l"][1] * h)
        hand_r = (sh_r[0] + p["hand_r"][0] * h, sh_r[1] + p["hand_r"][1] * h)
        foot_l = (cx + p["foot_l"][0] * h, fy)
        foot_r = (cx + p["foot_r"][0] * h, fy)
        w = max(10.0, h * 0.016)

        def seg(a_pt, b_pt, u0, u1, rgb=None, wd=None):
            uu = max(0.0, min(1.0, (u - u0) / max(1e-6, (u1 - u0))))
            if uu <= 0:
                return
            path = poly_path([a_pt, b_pt])
            c.drawPath(partial_path(path, uu), paint(rgb or self.rgb, 0.95 * a, stroke=wd or w))

        # head, torso, limbs draw in sequence
        hu = max(0.0, min(1.0, (u - 0.0) / 0.34))
        if hu > 0:
            c.drawArc(skia.Rect.MakeXYWH(head_c[0] - h * 0.115, head_c[1] - h * 0.115,
                                         h * 0.23, h * 0.23), -90, 360 * hu, False,
                      paint(self.rgb, 0.95 * a, stroke=w))
        seg(neck, hip, 0.30, 0.55)
        # arms bend at an elbow midpoint
        for sh, hand, u0 in ((sh_l, hand_l, 0.40), (sh_r, hand_r, 0.46)):
            elbow = ((sh[0] + hand[0]) / 2 + (hand[0] - sh[0]) * 0.12,
                     (sh[1] + hand[1]) / 2 + h * 0.10)
            seg(sh, elbow, u0, u0 + 0.12)
            seg(elbow, hand, u0 + 0.10, u0 + 0.24)
        seg(hip, foot_l, 0.58, 0.78)
        seg(hip, foot_r, 0.62, 0.82)
        seg((foot_l[0], foot_l[1]), (foot_l[0] - h * 0.06, foot_l[1]), 0.76, 0.84)
        seg((foot_r[0], foot_r[1]), (foot_r[0] + h * 0.06, foot_r[1]), 0.78, 0.86)
        # ground line
        g = max(0.0, min(1.0, (u - 0.5) / 0.4))
        if g > 0:
            c.drawPath(partial_path(poly_path(
                [(cx - h * 0.55, fy + 6), (cx + h * 0.55, fy + 6)]), g),
                paint(self.rgb, 0.35 * a, stroke=max(5.0, w * 0.5)))

        if self.prop == "chart":
            px, py = cx + h * 0.74, fy - h * 0.55
            pw, ph = h * 0.40, h * 0.34
            pu = max(0.0, min(1.0, (u - 0.55) / 0.35))
            if pu > 0:
                c.drawRect(skia.Rect.MakeXYWH(px - pw / 2, py - ph / 2, pw, ph),
                           paint(self.rgb, 0.30 * a, stroke=max(5.0, w * 0.6)))
                for i, f in enumerate((0.45, 0.7, 0.95)):
                    bu = max(0.0, min(1.0, (u - 0.65 - i * 0.06) / 0.3))
                    bh = ph * 0.72 * f * bu
                    c.drawRect(skia.Rect.MakeXYWH(px - pw * 0.32 + i * pw * 0.26,
                                                  py + ph * 0.36 - bh, pw * 0.16, bh),
                               paint(self.accent, 0.55 * a))
        elif self.prop == "phone":
            px, py = hand_r[0] + h * 0.02, hand_r[1] - h * 0.06
            pw, ph = h * 0.12, h * 0.21
            pu = max(0.0, min(1.0, (u - 0.55) / 0.3))
            if pu > 0:
                c.drawRect(skia.Rect.MakeXYWH(px - pw / 2, py - ph / 2, pw, ph),
                           paint(self.accent, 0.22 * a))
                c.drawRect(skia.Rect.MakeXYWH(px - pw / 2, py - ph / 2, pw, ph),
                           paint(self.accent, 0.9 * a, stroke=max(5.0, w * 0.55)))
                for i in range(3):
                    sc = ((t - self.t_in) * 0.8 + i * 0.37) % 1.0
                    yy = py + ph * 0.35 - sc * ph * 0.7
                    c.drawLine(px - pw * 0.30, yy, px + pw * 0.30, yy,
                               paint(self.rgb, 0.55 * a * (1 - abs(sc - 0.5) * 1.2),
                                     stroke=max(4.0, w * 0.4)))
        elif self.prop == "camera":
            px, py = hand_r[0] + h * 0.10, (hand_l[1] + hand_r[1]) / 2
            cw, ch = h * 0.30, h * 0.20
            pu = max(0.0, min(1.0, (u - 0.55) / 0.3))
            if pu > 0:
                c.drawRect(skia.Rect.MakeXYWH(px - cw / 2, py - ch / 2, cw, ch),
                           paint(self.rgb, 0.85 * a, stroke=max(6.0, w * 0.7)))
                c.drawCircle(px + cw * 0.62, py, ch * 0.36,
                             paint(self.accent, 0.9 * a, stroke=max(6.0, w * 0.7)))
                c.drawCircle(px + cw * 0.62, py, ch * 0.16, paint(self.accent, 0.55 * a))
                on = 0.5 + 0.5 * math.sin((t - self.t_in) * 7.0)
                c.drawCircle(px - cw * 0.36, py - ch * 0.28, h * 0.016,
                             paint(REDC, (0.4 + 0.6 * on) * a))
        elif self.prop == "box":
            px, py = cx + h * 0.42, fy - h * 0.12
            bw, bh2 = h * 0.34, h * 0.26
            pu = max(0.0, min(1.0, (u - 0.55) / 0.3))
            if pu > 0:
                c.drawRect(skia.Rect.MakeXYWH(px - bw / 2, py - bh2 / 2, bw, bh2),
                           paint(self.rgb, 0.30 * a, stroke=max(6.0, w * 0.7)))
                c.drawLine(px, py - bh2 / 2, px, py + bh2 / 2,
                           paint(self.accent, 0.7 * a, stroke=max(5.0, w * 0.5)))


class Icon(Item):
    """A neon icon: two blurred glow passes, a crisp tube and a white-hot core.

    kind is any key in icons_painters.PAINTERS (terminal, bug, shield, robot, rocket,
    globe, target, lock, eye, warn, chip, search, key, folder, wifi, news, pin,
    finger, clock, vs).
    """
    z = 34

    def __init__(self, kind, cx, cy, r, t_in, rgb=(72, 226, 255), dur=0.5, t_out=None,
                 sfx=False, pulse=True):
        super().__init__(t_in, t_out, None, sfx)
        if kind not in PAINTERS:
            raise ValueError(f"unknown icon {kind!r}; choose from {sorted(PAINTERS)}")
        self.fn, self.cx, self.cy, self.r, self.rgb = PAINTERS[kind], cx, cy, r, rgb
        self.dur, self.pulse = dur, pulse

    def bounds(self, res):
        r = self.r * 2
        return skia.Rect.MakeXYWH(self.cx - r, self.cy - r, 2 * r, 2 * r)

    def draw(self, c, res, t):
        u = ease_out_cubic(ramp(t, self.t_in - 0.05, self.dur))
        a = u * self.fade(t)
        if a <= 0:
            return
        s = 0.80 + 0.20 * u
        pulse = (0.90 + 0.10 * math.sin((t - self.t_in) * 2.4)) if self.pulse else 1.0
        w = max(3.0, self.r * 0.13)
        r = self.r * s
        cx, cy = self.cx, self.cy
        for blur, al in ((16, 0.72), (34, 0.36)):
            p = paint(self.rgb, al * a * pulse, stroke=w, blur=blur)
            p.setStrokeCap(skia.Paint.kRound_Cap)
            self.fn(c, cx, cy, r, p)
        cp = paint(self.rgb, a, stroke=w * 0.55)
        cp.setStrokeCap(skia.Paint.kRound_Cap)
        self.fn(c, cx, cy, r, cp)
        hp = paint((255, 255, 255), 0.5 * a, stroke=w * 0.20)
        hp.setStrokeCap(skia.Paint.kRound_Cap)
        self.fn(c, cx, cy, r, hp)
