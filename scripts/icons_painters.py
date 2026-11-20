"""20 neon icon painters, stroke-based, from the exploit_agent icon sheet.

Each painter draws one glyph at (cx, cy) with radius r into any Skia canvas.
board_items.Icon() adds the two glow passes and the hot core.
"""
import skia


def path_of(pts, close=False):
    p = skia.Path()
    p.moveTo(*pts[0])
    for pt in pts[1:]:
        p.lineTo(*pt)
    if close:
        p.close()
    return p


def circle(cv, cx, cy, r, p, rr_scale=1.0, rr_scale_y=None):
    cv.drawOval(skia.Rect.MakeXYWH(cx - r * rr_scale, cy - r * (rr_scale_y or rr_scale),
                                   2 * r * rr_scale, 2 * r * (rr_scale_y or rr_scale)), p)


def i_terminal(cv, cx, cy, r, p):
    cv.drawRoundRect(skia.Rect.MakeXYWH(cx-r, cy-r*0.72, 2*r, 1.44*r), 10, 10, p)
    cv.drawPath(path_of([(cx-r*0.58, cy-r*0.28), (cx-r*0.12, cy), (cx-r*0.58, cy+r*0.28)]), p)
    cv.drawLine(cx+r*0.08, cy+r*0.30, cx+r*0.55, cy+r*0.30, p)

def i_bug(cv, cx, cy, r, p):
    circle(cv, cx, cy+r*0.08, r*0.62, p)
    cv.drawLine(cx, cy-r*0.5, cx, cy+r*0.66, p)
    for sx in (-1, 1):
        cv.drawLine(cx+sx*r*0.55, cy-r*0.15, cx+sx*r*0.95, cy-r*0.5, p)
        cv.drawLine(cx+sx*r*0.62, cy+r*0.12, cx+sx*r*1.0, cy+r*0.12, p)
        cv.drawLine(cx+sx*r*0.55, cy+r*0.4, cx+sx*r*0.95, cy+r*0.7, p)
    cv.drawLine(cx-r*0.3, cy-r*0.82, cx+r*0.3, cy-r*0.82, p)

def i_shield(cv, cx, cy, r, p):
    p2 = skia.Path()
    p2.moveTo(cx, cy-r); p2.lineTo(cx+r*0.8, cy-r*0.62); p2.lineTo(cx+r*0.8, cy+r*0.1)
    p2.cubicTo(cx+r*0.8, cy+r*0.7, cx+r*0.4, cy+r*0.95, cx, cy+r*1.05)
    p2.cubicTo(cx-r*0.4, cy+r*0.95, cx-r*0.8, cy+r*0.7, cx-r*0.8, cy+r*0.1)
    p2.lineTo(cx-r*0.8, cy-r*0.62); p2.close()
    cv.drawPath(p2, p)
    cv.drawPath(path_of([(cx-r*0.42, cy+r*0.02), (cx-r*0.1, cy+r*0.35), (cx+r*0.5, cy-r*0.32)]), p)

def i_robot(cv, cx, cy, r, p):
    cv.drawRoundRect(skia.Rect.MakeXYWH(cx-r*0.72, cy-r*0.45, 1.44*r, 1.15*r), 9, 9, p)
    cv.drawLine(cx, cy-r*0.45, cx, cy-r*0.78, p)
    cv.drawLine(cx-r*0.32, cy-r*0.95, cx+r*0.32, cy-r*0.95, p)
    circle(cv, cx-r*0.34, cy+r*0.12, r*0.11, p)
    circle(cv, cx+r*0.34, cy+r*0.12, r*0.11, p)
    cv.drawLine(cx-r*0.34, cy+r*0.45, cx+r*0.34, cy+r*0.45, p)
    cv.drawLine(cx-r*0.98, cy-r*0.1, cx-r*0.72, cy-r*0.1, p)
    cv.drawLine(cx+r*0.72, cy-r*0.1, cx+r*0.98, cy-r*0.1, p)

def i_rocket(cv, cx, cy, r, p):
    b = skia.Path()
    b.moveTo(cx, cy-r); b.cubicTo(cx+r*0.62, cy-r*0.45, cx+r*0.62, cy+r*0.25, cx+r*0.3, cy+r*0.55)
    b.lineTo(cx-r*0.3, cy+r*0.55); b.cubicTo(cx-r*0.62, cy+r*0.25, cx-r*0.62, cy-r*0.45, cx, cy-r); b.close()
    cv.drawPath(b, p)
    circle(cv, cx, cy-r*0.12, r*0.17, p)
    cv.drawLine(cx-r*0.3, cy+r*0.55, cx-r*0.5, cy+r*0.95, p)
    cv.drawLine(cx, cy+r*0.55, cx, cy+r*1.05, p)
    cv.drawLine(cx+r*0.3, cy+r*0.55, cx+r*0.5, cy+r*0.95, p)

def i_globe(cv, cx, cy, r, p):
    circle(cv, cx, cy, r*0.92, p)
    cv.drawOval(skia.Rect.MakeXYWH(cx-r*0.4, cy-r*0.92, r*0.8, 1.84*r), p)
    cv.drawLine(cx-r*0.92, cy, cx+r*0.92, cy, p)

def i_target(cv, cx, cy, r, p):
    for rr in (0.9, 0.55, 0.2):
        circle(cv, cx, cy, r*rr, p)
    cv.drawLine(cx-r*1.18, cy, cx-r*0.72, cy, p); cv.drawLine(cx+r*0.72, cy, cx+r*1.18, cy, p)
    cv.drawLine(cx, cy-r*1.18, cx, cy-r*0.72, p); cv.drawLine(cx, cy+r*0.72, cx, cy+r*1.18, p)

def i_lock(cv, cx, cy, r, p):
    cv.drawRoundRect(skia.Rect.MakeXYWH(cx-r*0.72, cy-r*0.1, 1.44*r, 1.0*r), 8, 8, p)
    a = skia.Path()
    a.moveTo(cx-r*0.42, cy-r*0.1); a.lineTo(cx-r*0.42, cy-r*0.45)
    a.cubicTo(cx-r*0.42, cy-r*1.05, cx+r*0.42, cy-r*1.05, cx+r*0.42, cy-r*0.45); a.lineTo(cx+r*0.42, cy-r*0.1)
    cv.drawPath(a, p)
    circle(cv, cx, cy+r*0.38, r*0.13, p)

def i_eye(cv, cx, cy, r, p):
    e = skia.Path()
    e.moveTo(cx-r, cy); e.cubicTo(cx-r*0.4, cy-r*0.75, cx+r*0.4, cy-r*0.75, cx+r, cy)
    e.cubicTo(cx+r*0.4, cy+r*0.75, cx-r*0.4, cy+r*0.75, cx-r, cy); e.close()
    cv.drawPath(e, p)
    circle(cv, cx, cy, r*0.34, p)

def i_warn(cv, cx, cy, r, p):
    t = path_of([(cx, cy-r*0.95), (cx+r*0.9, cy+r*0.62), (cx-r*0.9, cy+r*0.62)], close=True)
    cv.drawPath(t, p)
    cv.drawLine(cx, cy-r*0.42, cx, cy+r*0.12, p)
    circle(cv, cx, cy+r*0.38, r*0.05, p)

def i_chip(cv, cx, cy, r, p):
    cv.drawRoundRect(skia.Rect.MakeXYWH(cx-r*0.6, cy-r*0.6, 1.2*r, 1.2*r), 7, 7, p)
    cv.drawRoundRect(skia.Rect.MakeXYWH(cx-r*0.28, cy-r*0.28, 0.56*r, 0.56*r), 4, 4, p)
    for i in (-0.36, 0.0, 0.36):
        cv.drawLine(cx+i*r, cy-r*0.95, cx+i*r, cy-r*0.6, p)
        cv.drawLine(cx+i*r, cy+r*0.6, cx+i*r, cy+r*0.95, p)
        cv.drawLine(cx-r*0.95, cy+i*r, cx-r*0.6, cy+i*r, p)
        cv.drawLine(cx+r*0.6, cy+i*r, cx+r*0.95, cy+i*r, p)

def i_search(cv, cx, cy, r, p):
    circle(cv, cx-r*0.14, cy-r*0.14, r*0.62, p)
    cv.drawLine(cx+r*0.35, cy+r*0.35, cx+r*0.95, cy+r*0.95, p)

def i_key(cv, cx, cy, r, p):
    circle(cv, cx-r*0.55, cy-r*0.55, r*0.4, p)
    cv.drawLine(cx-r*0.25, cy-r*0.25, cx+r*0.85, cy+r*0.85, p)
    cv.drawLine(cx+r*0.45, cy+r*0.45, cx+r*0.72, cy+r*0.18, p)
    cv.drawLine(cx+r*0.66, cy+r*0.66, cx+r*0.92, cy+r*0.40, p)

def i_folder(cv, cx, cy, r, p):
    f = skia.Path()
    f.moveTo(cx-r*0.9, cy-r*0.62); f.lineTo(cx-r*0.15, cy-r*0.62); f.lineTo(cx+r*0.1, cy-r*0.32)
    f.lineTo(cx+r*0.9, cy-r*0.32); f.lineTo(cx+r*0.9, cy+r*0.62); f.lineTo(cx-r*0.9, cy+r*0.62); f.close()
    cv.drawPath(f, p)
    cv.drawLine(cx-r*0.9, cy-r*0.1, cx+r*0.9, cy-r*0.1, p)

def i_wifi(cv, cx, cy, r, p):
    for rr in (0.35, 0.65, 0.95):
        rect = skia.Rect.MakeXYWH(cx-r*rr, cy-r*0.25-r*rr, 2*r*rr, 2*r*rr)
        cv.drawArc(rect, 205, 130, False, p)
    circle(cv, cx, cy+r*0.78, r*0.07, p)

def i_news(cv, cx, cy, r, p):
    cv.drawRoundRect(skia.Rect.MakeXYWH(cx-r*0.9, cy-r*0.6, 1.8*r, 1.2*r), 6, 6, p)
    cv.drawLine(cx-r*0.6, cy-r*0.28, cx-r*0.05, cy-r*0.28, p)
    cv.drawLine(cx-r*0.6, cy+r*0.02, cx+r*0.6, cy+r*0.02, p)
    cv.drawLine(cx-r*0.6, cy+r*0.32, cx+r*0.6, cy+r*0.32, p)

def i_pin(cv, cx, cy, r, p):
    m = skia.Path()
    m.moveTo(cx, cy+r*0.95); m.cubicTo(cx-r*0.75, cy+r*0.1, cx-r*0.7, cy-r*0.2, cx-r*0.7, cy-r*0.25)
    m.cubicTo(cx-r*0.7, cy-r*0.85, cx+r*0.7, cy-r*0.85, cx+r*0.7, cy-r*0.25)
    m.cubicTo(cx+r*0.7, cy-r*0.2, cx+r*0.75, cy+r*0.1, cx, cy+r*0.95); m.close()
    cv.drawPath(m, p)
    circle(cv, cx, cy-r*0.22, r*0.2, p)

def i_finger(cv, cx, cy, r, p):
    for rr, a0, sw in ((0.95, -50, 1.0), (0.68, -55, 1.0), (0.42, -60, 1.0)):
        rect = skia.Rect.MakeXYWH(cx-r*rr, cy-r*rr, 2*r*rr, 2*r*rr)
        cv.drawArc(rect, 235, 140, False, p)
    cv.drawArc(skia.Rect.MakeXYWH(cx-r*0.2, cy+r*0.35, r*0.4, r*0.75), 160, 130, False, p)

def i_clock(cv, cx, cy, r, p):
    circle(cv, cx, cy, r*0.92, p)
    cv.drawLine(cx, cy, cx, cy-r*0.55, p)
    cv.drawLine(cx, cy, cx+r*0.4, cy+r*0.18, p)

def i_vs(cv, cx, cy, r, p):
    circle(cv, cx-r*0.5, cy, r*0.42, p)
    circle(cv, cx+r*0.5, cy, r*0.42, p)
    cv.drawLine(cx-r*0.5, cy, cx-r*0.5, cy, p)  # placeholder tiny
    for body in (-1, 1):
        bx = cx + body*r*0.5
        cv.drawLine(bx-r*0.13, cy-r*0.13, bx+r*0.13, cy+r*0.13, p)
        cv.drawLine(bx-r*0.13, cy+r*0.13, bx+r*0.13, cy-r*0.13, p)

PAINTERS = {
    "terminal": i_terminal,
    "bug": i_bug,
    "shield": i_shield,
    "robot": i_robot,
    "rocket": i_rocket,
    "globe": i_globe,
    "target": i_target,
    "lock": i_lock,
    "eye": i_eye,
    "warn": i_warn,
    "chip": i_chip,
    "search": i_search,
    "key": i_key,
    "folder": i_folder,
    "wifi": i_wifi,
    "news": i_news,
    "pin": i_pin,
    "finger": i_finger,
    "clock": i_clock,
    "vs": i_vs,
}
